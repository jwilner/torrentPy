import select
import socket
import config
import logging
import torrent_exceptions
import events
from peer import Peer
from time import time
from torrent import Torrent
from collections import defaultdict
from requests_futures.sessions import FuturesSession
from requests.exceptions import HTTPError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class BitTorrentClient(torrent_exceptions.ExceptionManager,
                       events.EventManager,
                       object):
    '''Main object encapsulating central info and work flow for the
    process'''

    _listen_to = set()
    _handlers = defaultdict(dict)
    waiting_to_write = set()  # peers register themselves in this set
    _dropped = set()  # peers to ignore

    _futures = set()  # pending http_requests
    torrents = set()
    _timers = set()  # timer tuple pairs -- callback,  timestamp

    def __init__(self, port=config.DEFAULT_PORT, client_id=config.CLIENT_ID):
        self.port,  self.client_id = port,  client_id
        logger.info('Starting up on port %d', port)

        s = socket.socket()
        s.bind((socket.gethostname(), self.port))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.listen(config.MAX_LISTEN)

        self._socket = s

        self.register(self, read=self._accept_connection)

        self._http_session = FuturesSession()

        self._exception_handlers = {
            torrent_exceptions.UnknownPeerHandshake:
            self._unknown_peer_callback
            }

        self._event_handlers = {
            events.PeerRegistration:
            lambda ev: self.register(ev.peer,
                                     read=ev.read,
                                     write=ev.write,
                                     error=ev.error),

            events.PeerReadyToSend:
            lambda ev: self.waiting_to_write.add(ev.peer),

            events.PeerDoneSending:
            lambda ev: self.waiting_to_write.discard(ev.peer)}

    def fileno(self):
        return self._socket.fileno()

    def __repr__(self):
        return "<Joe's BitTorrent Client--{0}>".format(self._data['client_id'])

    def start_torrent(self, filename):
        '''Takes a filename for a torrent file,  processes that file and
        enqueues a request via socket.'''

        logger.info('Adding torrent described by %s', filename)
        self.torrents.add(Torrent(filename, self))

    def register(self, sock_manager, **socket_handlers):
        '''Register socket_abstraction with fileno and handlers'''
        if 'read' in socket_handlers:
            self._listen_to.add(sock_manager)

        logger.info('Registering socket manager')

        self._handlers[sock_manager].update(socket_handlers)

    def unregister(self, sock_manager):
        logger.info('Unregistering socket')

        del self._handlers[sock_manager]
        self._listen_to.discard(sock_manager)
        self.waiting_to_write.discard(sock_manager)
        self._dropped.add(sock_manager)

    def add_timer(self, interval, callback, exception_handler):
        '''Adds a callback to fire in a specified time'''
        logger.info('Adding a callback in %d seconds: %s', interval, callback)
        self._timers.add((callback, time()+interval, exception_handler))

    def make_tracker_request(self, url, data, handler, e_handler):
        '''This instantiates a future object,  while binding a handler that
        will be called on a bedecoded result and an error handler that will be
        called on an http error'''

        logger.info('Making tracker request to %s', url)

        future = self._http_session.get(url, params=data)
        self._futures.add((future, handler, e_handler))

    def run_loop(self):
        '''Main loop'''
        logger.info('Beginning main loop...')
        while True:
            self._check_timers()
            self._handle_http_requests()
            self._select_sockets_and_handle()

    def _accept_connection(self):
        sock,  address = self._socket.accept()
        logger.info('Connecting at %s.', address)

         # b/c no torrent included yet,  will require handshake
        Peer(sock, self)  # __init__ registers peer with torrent

    def _check_timers(self):
        '''For time- and interval-sensitive callbacks'''
        now = time()
        ready_to_go = {(c, t, e) for (c, t, e) in self._timers if t <= now}

        for callback,  timestamp,  exception_handler in ready_to_go:
            logger.info('Running callback %s at %d', repr(callback), timestamp)
            try:
                callback()
            except Exception as e:
                exception_handler(e)

        self._timers -= ready_to_go

    def _handle_http_requests(self):
        '''Checks futures and if complete,  calls an appropriate handler'''

        logger.info('Checking HTTP requests...')
        completed = {(f, h, e) for (f, h, e) in self._futures if f.done()}

        for future,  handler,  e_handler in completed:
            response = future.result()

            try:
                response.raise_for_status()
            except HTTPError as e:
                e_handler(e)
            else:
                handler(response)

        self._futures -= completed

    def _select_sockets_and_handle(self):
        '''Use select interface to get prepared sockets,  and then
        call the registered handlers.'''
        logger.info('Checking sockets: %s %s',
                    len(self._listen_to),
                    len(self.waiting_to_write))

        read,  write,  error = select.select(self._listen_to,
                                             self.waiting_to_write,
                                             self._listen_to,
                                             config.SELECT_TIMEOUT)

        logger.info('Read %d; Write %d; Error %d',
                    len(read),
                    len(write),
                    len(error))

        for event, socktype in (('read', read),
                                ('write', write),
                                ('error', error)):
            for sock_manager in socktype:
                logger.info('Handling %s event', event)
                try:
                    self._handlers[sock_manager][event]()
                except KeyError:
                    raise torrent_exceptions.UnhandledSocketEvent
                except Exception as e:
                    sock_manager.handle_exception(e)

    def _unknown_peer_callback(self, e):
        peer,  msg = e.peer,  e.msg

        for t in self.torrents:
            if t.hashed_info == msg.info_hash:
                peer.torrent = t
                t.add_peer(peer)
                break
        else:
            # not interested in any of our torrents
            self.unregister(peer)
            peer.drop()

    def _socket_error_handler(self, e):
        '''What has to happen here?'''
        raise e

if __name__ == '__main__':
    import sys
    c = BitTorrentClient()
    try:
        c.start_torrent(sys.argv[1])
    except KeyError:
        logger.debug('No torrent file passed.')
    else:
        c.run_loop()
