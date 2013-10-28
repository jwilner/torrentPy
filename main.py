import select, socket, config
from peer import Peer
from time import time
from torrent import Torrent
from collections import defaultdict
from requests_futures import FuturesSession
from requests.exceptions import HTTPError


class UnhandledSocketEvent(Exception):
    pass

class BitTorrentClient(object):
    '''Main object encapsulating central info and work flow for the 
    process'''
    
    registered = []
    _MAX_LISTEN = config.MAX_LISTEN
    _handlers = defaultdict(dict)
    
    def __init__(self,port=config.PORT):
        s = socket.socket()
        s.bind((s.gethostname(),self.port))
        s.listen(self._MAX_LISTEN)
        self.register(s,read=self._accept_connection)

        self._http_session = FuturesSession()
        self._data = {'client_id':config.CLIENT_ID, 'port':port}
        self._torrents = set() 

        self._run_loop()

    def __repr__(self):
        return "<Joe's BitTorrent Client -- id: {0}>".format(self._data['client_id'])

    def __getattr__(self,key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError

    def start_torrent(self,filename):
        '''Takes a filename for a torrent file, processes that file and 
        enqueues a request via socket.'''
        self._torrents.add(Torrent(filename,self))

    def register(self,socket,**socket_handlers):
        '''Register sockets and handlers'''
        self._handlers[socket.getsockname()].update(socket_handlers)

    def add_timer(self,interval,callback):
        '''Adds a callback to fire in a specified time'''
        self._timers.add((callback,time()+interval))

    def make_tracker_request(self,url,data,handler,e_handler):
        '''this instantiates a future object, while binding a handler that will
        be called on a bedecoded result and an error handler that will be called
        on an http error'''
        future = self._session.get(url,data)
        self._futures.add((future,handler,e_handler))

    def _accept_connection(self,s):
        socket, address = s.accept()

        # b/c no torrent included yet, will require handshake
        peer = Peer(socket,self)
        self.register(socket,peer.socket_handlers)

    def _run_loop(self):
        '''Main loop'''
        while True:
            self._check_timers()
            self._handle_http_requests()
            self._select_sockets_and_handle()

    def _check_timers(self):
        '''For time- and interval-sensitive callbacks'''
        now = time()
        ready_to_go = {(c,t) for (c,t) in self._timers if t >= now}

        for callback, timestamp in ready_to_go:
            callback()

        self._timers -= ready_to_go
                
    def _handle_http_requests(self):
        '''Checks futures and if complete, calls an appropriate handler'''             

        completed = {(f,h,e) for (f,h,e) in self._futures if f.done()}

        for future, handler, e_handler in completed: 
            response = future.result()
            try:
                response.raise_for_status()
            except HTTPError:
                e_handler(response)
            handler(response)

        self._futures -= completed

    def _select_sockets_and_handle(self):
        '''Use select interface to get prepared sockets, and then
        call the registered handlers.'''
        read, write, error = select.select(self.registered,
                                            self.registered,
                                            self.registered)
        for event,socktype in (('read',read),
                               ('write',write),
                               ('error',error)):
            for socket in socktype:
                try:
                    self._handlers[socket.getsockname()][event](socket)
                except KeyError:
                    raise UnhandledSocketEvent
                except Exception as e:
                    try:
                        self._exception_handlers[e](e)
                    except KeyError:
                        raise e

