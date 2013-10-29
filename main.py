import select, socket, config, logging
from peer import Peer
from time import time
from torrent import Torrent
from collections import defaultdict
from requests_futures.sessions import FuturesSession
from requests.exceptions import HTTPError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class UnhandledSocketEvent(Exception):
    pass

class BitTorrentClient(object):
    '''Main object encapsulating central info and work flow for the 
    process'''
    
    _listen_to = set()
    _handlers = defaultdict(dict)
    waiting_to_write = set() 
    _futures = set()
    torrents = set() 
    _timers = set()
    _dropped = set()
    
    def __init__(self,port=config.DEFAULT_PORT):
        self._data = {'client_id':config.CLIENT_ID, 'port':port}
        logger.info('Starting up on port %d',port)

        s = socket.socket()
        s.bind((socket.gethostname(),self.port))
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        s.listen(config.MAX_LISTEN)

        self.register(s,read=self._accept_connection)

        self._http_session = FuturesSession()
        self._exception_handlers = {
                socket.error : self._socket_error_handler}

    def __repr__(self):
        return "<Joe's BitTorrent Client -- id: {0}>".format(self._data['client_id'])

    @property
    def port(self):
        return self._data['port']

    @property
    def client_id(self):
        return self._data['client_id']

    def start_torrent(self,filename):
        '''Takes a filename for a torrent file, processes that file and 
        enqueues a request via socket.'''

        logger.info('Adding torrent described by %s',filename)
        self.torrents.add(Torrent(filename,self))

    def register(self,socket,**socket_handlers):
        '''Register sockets and handlers'''
        if 'read' in socket_handlers:
            self._listen_to.add(socket)
        logger.info('Registering socket')
        self._handlers[socket].update(socket_handlers)

    def unregister(self,socket):
        logger.info('Unregistering socket')
        del self._handlers[socket]
        self._listen_to.discard(socket)
        self.waiting_to_write.discard(socket)
        self._dropped.add(socket)

    def add_timer(self,interval,callback):
        '''Adds a callback to fire in a specified time'''
        logger.info('Adding a callback in %d seconds: %s',interval,callback)
        self._timers.add((callback,time()+interval))

    def make_tracker_request(self,url,data,handler,e_handler):
        '''this instantiates a future object, while binding a handler that will
        be called on a bedecoded result and an error handler that will be called
        on an http error'''
        logger.info('Making tracker request to %s',url)
        future = self._http_session.get(url,params=data)
        self._futures.add((future,handler,e_handler))

    def _accept_connection(self,s):
        socket, address = s.accept()
        logger.info('Connecting at %s.',address) 
        # b/c no torrent included yet, will require handshake
        peer = Peer(socket,self)
        self.register(socket,peer.socket_handlers)

    def run_loop(self):
        '''Main loop'''
        logger.info('Beginning main loop...')
        while True:
            self._check_timers()
            self._handle_http_requests()
            self._select_sockets_and_handle()

    def _check_timers(self):
        '''For time- and interval-sensitive callbacks'''
        now = time()
        ready_to_go = {(c,t) for (c,t) in self._timers if t <= now}

        for callback, timestamp in ready_to_go:
            logger.info('Running callback %s at %d',repr(callback),timestamp)
            callback()

        self._timers -= ready_to_go
                
    def _handle_http_requests(self):
        '''Checks futures and if complete, calls an appropriate handler'''             
        logger.info('Checking HTTP requests...')
        completed = {(f,h,e) for (f,h,e) in self._futures if f.done()}
        for future, handler, e_handler in completed: 
            response = future.result()
            try:
                response.raise_for_status()
            except HTTPError:
                logger.info('Unsuccessful request: %s.',repr(response))
                e_handler(response)
            logger.info('Got a successful request back: %s.',repr(response))
            handler(response)

        self._futures -= completed
        logger.info('Done checking HTTP requests...')

    def _select_sockets_and_handle(self):
        '''Use select interface to get prepared sockets, and then
        call the registered handlers.'''
        logger.info('Checking sockets')
        read, write, error = select.select(self._listen_to,
                                            self.waiting_to_write,
                                            self._listen_to,0.05)
        logger.info('Sockets found: %d',len(read))
        for event,socktype in (('read',read),
                               ('write',write)):
            for socket in socktype:
                logger.info('About to run %s for %s',self._handlers[socket][event],str(socket.getpeername()))
                try:
                    self._handlers[socket][event]()
                except KeyError:
                    raise UnhandledSocketEvent
                except Exception as e:
                    try:
                        self._exception_handlers[type(e)](e)
                    except KeyError:
                        raise e
        self.waiting_to_write = set() 

    def _socket_error_handler(self,e):
        print e

if __name__ == '__main__':
    import sys
    c = BitTorrentClient() 
    c.start_torrent(sys.argv[1])
    c.run_loop()