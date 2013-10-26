import logging, select, socket, config, requests
from io import BytesIO
from utils import debencode
from peer import Peer
from torrent import LiveTorrent
from collections import defaultdict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class UnhandledSocketEvent(Exception):
    pass

class BitTorrentClient(object):
    '''Object encapsulating central info for the process'''
    
    registered = []
    _MAX_LISTEN = config.MAX_LISTEN
    _handlers = defaultdict(dict)
    
    def __init__(self,port=config.PORT):
        self._data = {'client_id':config.CLIENT_ID,
                      'port':port}
        self._torrents = set() 

    def __repr__(self):
        return "<Joe's BitTorrent Client -- id: {0}>".format(self._data['client_id'])

    def __getattr__(self,key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError

    def run(self):
        s = socket.socket()
        s.bind(('',self.port))
        s.listen(self._MAX_LISTEN)
        self.register(s,read=self._accept_connection)
        
        self._run_loop()

    def start_torrent(self,filename):
        '''Takes a filename, processes it and returns a torrent'''
        t = LiveTorrent(filename,self)
        request_params = t.announce_params
        request_params['event'] = 'started'
        result = self._make_tracker_request(t.announce,request_params)
        
    def scrape_torrent(self,torrent):
        try:
            url = torrent.scrape_url
        



    def _make_tracker_request(self,url,data):
        r = requests.get(url,data=data)         
        r.raise_for_status()
        return debencode(BytesIO(r.content))

    def _accept_connection(self,s):
        socket, address = s.accept()

        # b/c no torrent included yet, will require handshake
        peer = Peer(socket,self)
        self.register(socket,peer.socket_handlers)

    def _run_loop(self):
        '''Main loop'''
        while True:
            self._select_sockets_and_handle()

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

    def register(self,socket,socket_handlers):
        '''Register sockets and handlers'''
        self._handlers[socket.getsockname()] = socket_handlers

