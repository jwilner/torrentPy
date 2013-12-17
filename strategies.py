import messages
import socket
import random
import config
import torrent_exceptions
import events
from peer import Peer
from torrent import Torrent

'''Strategy objects would be chosen based on the current state of the
local torrent,  while the strategy object makes decisions about actions for
particular peers on a given go through the event loop'''


class TorrentManager(events.EventManager,
                     torrent_exceptions.ExceptionManager,
                     object):

    def __init__(self, client_id, filename, events_strategies):
        '''Instantiates torrent object and strategy'''

        if not events_strategies:
            events_strategies = default_set

        self._torrent = Torrent(filename, client_id)
        self._events_strategies = events_strategies
        self._set_strategy(events.INIT_EVENT)

    def _set_strategy(self, ev):
        strategy_type = self._choose_strategy(ev)
        self._strategy = strategy_type(self._torrent)
        self._strategy.event_observer = self
        self._strategy.next_exception_level = self

    def _choose_strategy(self, ev):
        ev_type = type(ev)
        for event_type, strategy in self._events_strategies:
            if ev_type is event_type:
                return strategy
        raise torrent_exceptions.NoStrategyFound()

    def register_unknown_peer(self, peer):
        if self._strategy.want_peer(peer):
            self._establish_contact(peer)

    @property
    def hashed_info(self):
        return self._torrent.hashed_info


class Strategy(events.EventManager,
               torrent_exceptions.ExceptionManager,
               messages.MessageManager):
    '''extensible class internalizing the strategy'''

    _MAX_PEERS = 50

    def __init__(self, torrent):

        self._torrent = torrent
        torrent.next_message_level = self
        torrent.event_observer = self

        self._event_handlers = {
            events.TrackerResponse: self._tracker_response_callback,
            events.HaveCompletePiece: self._handle_have_event
            }

        # exception handling implementing ExceptionHandler
        self._exception_handlers = {
            torrent_exceptions.FatallyFlawedIncomingMessage:
            lambda e: self._drop_peer(e.peer),

            torrent_exceptions.FatallyFlawedOutgoingMessage:
            lambda e: self._drop_peer(e.peer),

            torrent_exceptions.MessageParsingError:
            lambda e: self._drop_peer(e.peer)
            }

        self._message_handlers = {
            messages.OUTGOING: {},
            messages.INCOMING: {}
            }

    def init_callback(self):
        '''Can use this function specifically to define different
        approaches to trackers -- e.g. load all at once,  or as needed'''
        for url in self._torrent.all_announce_urls:
            self._torrent.trackers.add(self.make_tracker(url))

    def have_event(self, index):
        for peer in self._torrent.peers.values():
            self._torrent.dispatch(peer, messages.Have, index)

    def want_peer(self, peer_address):
        '''All these tests must pass in order for a peer to be added'''
        return peer_address[0] != config.LOCAL_ADDRESS and \
            peer_address not in self._torrent.peers and \
            len(self._torrent.peers) <= self._MAX_PEERS

    def tracker_response_callback(self, ev):
        for adr in ev.new_peer_addresses:
            if self.want_peer(adr):
                s = socket.socket()
                s.connect(adr)
                peer = Peer(s)
                self._establish_contact(peer)

        # check back in at requested interval
        self.client \
            .add_timer(ev.tracker.interval,
                       lambda: self.make_tracker_announce_request(ev.tracker),
                       self.handle_exception)

    def _handle_have_event(self, event):
        pass

    def _establish_contact(self, peer):
        self._torrent.peers[peer.address] = peer
        msgs = [messages.Handshake]

        if any(self._torrent.have):
            msgs.append(messages.Bitfield)

        for msg in msgs:
            self._torrent.dispatch(peer, msg)

    def make_announce_request(self, tracker, event_type=None):
        announce_params = {
            'info_hash': self._torrent.hashed_info,
            'peer_id': self.client.client_id,
            'port': self.client.port,
            'uploaded': self.torrent.uploaded,
            'downloaded': self.torrent.downloaded,
            'left': self.torrent.total_length,
            'compact': 1,
            'supportcrypto': 1}

        if event_type is not None:
            announce_params['event'] = event_type

        announce_params.update(
            {p: tracker.data[p] for p in tracker.optional_params
                if p in tracker.data})

        self.client.make_tracker_request(tracker.announce_url,
                                         announce_params,
                                         tracker.handle_response,
                                         self.handle_exception)

    def _get_rarest_desirable_pieces(self):
        '''Outstanding pieces that are still required '''
        return sorted((i for i, f in enumerate(self._torrent.frequency)
                       if not self._torrent.have[i]),
                      key=lambda x: x[1], reversed=True)

    def _drop_peer(self, peer):
        self._torrent.drop_peer(peer)
        peer.drop()

    predicates = {
        'NON_CHOKING': lambda p: not p.choking_me,
        'UNDER_TEN_REQUESTS': lambda p: len(p.outstanding_requests) < 10,
        'WANTED_PIECES': lambda p: bool(p.wanted_pieces)
        }

    def _filter_peers(self, peers, predicates):
        return (peer for peer in peers if
                all(predicate(peer) for predicate in predicates))


class RandomPieceStrategy(Strategy):

    def act(self):
        for peer, pieces in self._get_interesting_peers():
            self._torrent.dispatch(peer, messages.Interested)

        for peer in self._get_priority_peers():
            for i, p_index in enumerate(peer.wanted_pieces):
                if self._torrent.piece_record[p_index]:
                    block_index = max(self._torrent
                                          .piece_record[p_index].keys(),
                                      key=lambda x: x[1])[1]
                else:
                    block_index = 0
                self._torrent.dispatch(peer, messages.Request, p_index,
                                       block_index, config.MAX_REQUEST_AMOUNT)

    def choose_random_piece(self, n):
        return random.shuffle([k for k, v in self._torrent.piece_record.items()
                               if v != self._torrent.piece_length])[:n]

default_set = ((events.INIT_EVENT,  RandomPieceStrategy), )
