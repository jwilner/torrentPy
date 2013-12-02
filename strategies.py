import messages, random, config, torrent_exceptions, events

'''Strategy objects would be chosen based on the current state of the
local torrent, while the strategy object makes decisions about actions for
particular peers on a given go through the event loop'''

class StrategyManager(events.EventManager):

    def __init__(self,rules_strategies):
        self._rules_strategies = rules_strategies
        self.current = None

    def update(self,torrent,event=None):
        try:
            self.current = self._parse_rules(
                torrent if event is None else event)
        except torrent_exceptions.NoStrategyFound:
            pass
        return self.current

    def _parse_rules(self,argument):
        for rule,strategy in self._rules_strategies:
            try:
                if rule(argument):
                    return strategy
            except:
                continue
        else:
            raise torrent_exceptions.NoStrategyFound


class Strategy(events.EventManager,
                torrent_exceptions.ExceptionManager,
                messages.MessageManager):
    '''extensible class internalizing the strategy'''

    _MAX_PEERS = 50

    def __init__(self,torrent):

        self._torrent = torrent

        self._event_handlers = {
            events.TrackerResponse : self._tracker_response_callback
            }

        # exception handling implementing ExceptionHandler
        self._next_exception_level = torrent.client
        self._exception_handlers = {
                torrent_exceptions.FatallyFlawedIncomingMessage :
                            lambda e : self._drop_peer(e.peer),
                torrent_exceptions.FatallyFlawedOutgoingMessage :
                            lambda e : self._drop_peer(e.peer),
                torrent_exceptions.MessageParsingError :
                            lambda e : self._drop_peer(e.peer)
                }


        self._message_handlers = {
            messages.OUTGOING : {
                },
            messages.INCOMING : {
                }
            }


    def init_callback(self):
        '''Can use this function specifically to define different
        approaches to trackers -- e.g. load all at once, or as needed'''
        for url in self._torrent.all_announce_urls:
            self._torrent.trackers.add(
                    self.make_tracker(url))

    def have_event(self,index):
        for peer in self._torrent.peers.values():
            self._torrent.dispatch(peer,messages.Have,index)

    def want_peer(self,peer_address):
        '''All these tests must pass in order for a peer to be added'''
        return (peer_address[0] != config.LOCAL_ADDRESS and
                peer_address not in self._torrent.peers and
                len(self._torrent.peers) <= self._MAX_PEERS)

    def new_peer_callback(self,peer):
        '''Defines behavior to call after creating a new peer'''
        msgs = [messages.Handshake]

        if any(self._torrent.have):
            msgs.append(messages.Bitfield)

        for msg in msgs:
            self._torrent.dispatch(peer,msg)

    def tracker_response_callback(self,event):

        for adr in event.new_peer_addresses:
            if self.want_peer(adr):
                self.make_peer(adr)

        # check back in at requested interval
        self.client.add_timer(
                event.tracker.interval,
                lambda : self.make_tracker_announce_request(event.tracker),
                self.handle_exception)

    def make_tracker_announce_request(self,tracker,event_type=None):
        announce_params = {
                'info_hash':self._torrent.hashed_info,
                'peer_id':self.client.client_id,
                'port':self.client.port,
                'uploaded':self.torrent.uploaded,
                'downloaded':self.torrent.downloaded,
                'left':self.torrent.total_length,
                'compact':1,
                'supportcrypto':1}

        if event_type is not None:
            announce_params['event'] = event_type

        announce_params.update(
                {p:tracker.data[p] for p in tracker.optional_params
                    if p in tracker.data})

        self.client.make_tracker_request(
                tracker.announce_url,
                announce_params,
                tracker.handle_response,
                self.handle_exception)

    def _get_rarest_desirable_pieces(self):
        '''Outstanding pieces that are still required '''
        return sorted((i for i,f in enumerate(self._torrent.frequency)
                                if not self._torrent.have[i]),
                            key=lambda x:x[1],
                            reversed=True)

    def _drop_peer(self,peer):
        self._torrent.client.drop_peer(peer)
        self._torrent.drop_peer(peer)
        peer.drop()

    predicates = {
        'NON_CHOKING' : lambda p : not p.choking_me,
        'UNDER_TEN_REQUESTS' : lambda p: len(p.outstanding_requests) < 10,
        'WANTED_PIECES' : lambda p: bool(p.wanted_pieces),
        'HAS_PIECE' : lambda p, i: p.has[i]
        }

    def _filter_peers(self,peers,predicates):
        return (peer for peer in peers if
                    all(predicate(peer) for predicate in predicates))

class RandomPieceStrategy(Strategy):

    def act(self):
        for peer,pieces in self._get_interesting_peers():
            self._torrent.dispatch(peer,messages.Interested)

        for peer in self._get_priority_peers():
            for i,p_index in enumerate(peer.wanted_pieces):
                if self._torrent.piece_record[p_index]:
                    block_index = max(self._torrent.piece_record[p_index].keys(),key=lambda x:x[1])[1]
                else:
                    block_index = 0
                self._torrent.dispatch(peer,messages.Request,
                                            p_index,block_index,config.MAX_REQUEST_AMOUNT)

    def choose_random_piece(self,n):
        return random.shuffle([k for k,v in self._torrent.piece_record.items()
                        if v != self._torrent.piece_length])[:n]

default_set = ((lambda x : True, RandomPieceStrategy),)
