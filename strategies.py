import messages, random, config, torrent_exceptions, tracker

'''Strategy objects would be chosen based on the current state of the
local torrent, while the strategy object makes decisions about actions for 
particular peers on a given go through the event loop'''

INIT_EVENT = 'INIT_EVENT'
DOWNLOAD_DONE_EVENT = 'DOWNLOAD_DONE_EVENT'
SHUTDOWN_EVENT = 'SHUTDOWN_EVENT'

class StrategyManager(object):

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


class Strategy(object):
    '''extensible class internalizing the strategy'''

    _MAX_PEERS = 50
    
    def __init__(self,torrent):
        self._torrent = torrent
        self._exception_handlers = {
                torrent_exceptions.FatallyFlawedMessage : self._drop_peer_procedure
                }
        
    def init_callback(self,index):
        '''Can use this function specifically to define different
        approaches to trackers -- e.g. load all at once, or as needed'''
        for url in self._torrent.all_announce_urls:
            self._torrent.start_tracker(url)

    def handle_exception(self,e):
        '''Attempts to handle exception first with strategy, then with
        torrent, else let's it rise up'''
        exception_type = type(e)
        try:
            self._exception_handlers[exception_type](e)
        except KeyError:
            try:
                self._torrent._exception_handlers[exception_type](e)
            except KeyError:
                raise e

    def have_event(self,index):
        for peer in self._torrent.peers.values():
            self._torrent.dispatch(peer,messages.Have,index)

    def make_peer_test(self,peer_address):
        '''All these tests must pass in order for a peer to be added'''
        return all( peer_address[0] != config.LOCAL_ADDRESS,
                    peer_address not in self._torrent.peers,
                    len(self._torrent.peers) <= self._MAX_PEERS)
                    
    def new_peer_callback(self,peer):
        '''Defines behavior to call after creating a new peer'''
        for msg in (messages.Handshake,messages.Bitfield):
            self._torrent.dispatch(peer,msg)

    def download_completed(self,index):
        self._torrent._old_write_to_disk()
        raise torrent_exceptions.TorrentComplete    

    def _get_rarest_desirable_pieces(self):
        '''Outstanding pieces that are still required '''
        return sorted((i for i,f in enumerate(self._torrent.frequency) 
                                     if not self._torrent.have[i]),
                                key=lambda x:x[1],
                                reversed=True)
    
    def _get_non_choking_peers(self):
        return (peer for peer in self._torrent.peers.values() if not peer.choking_me)

    def _get_priority_peers(self):
        return (peer for peer in self._get_non_choking_peers() 
                                 if len(peer.outstanding_requests) < 10 )

    def _get_interesting_peers(self):
        return ((peer,pieces) for peer,pieces in 
                    ((peer,peer.wanted_pieces) for peer in self._torrent.peers.values() if peer.choking_me)
                        if pieces)


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

default_set = (
    (lambda x : True, RandomPieceStrategy)
        )
