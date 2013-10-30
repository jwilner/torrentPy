import messages, random, config, torrent_exceptions

'''Strategy objects would be chosen based on the current state of the
local torrent, while the strategy object makes decisions about actions for 
particular peers on a given go through the event loop'''

class Strategy(object):
    '''extensible class internalizing the strategy'''

    def __init__(self,torrent):
        self._torrent = torrent

    def act(self):
        pass

    def have_event(self,index):
        for peer in self._torrent.peers.values():
            self._torrent.dispatch(peer,messages.Have,index)

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

class RarestFirstStrategy(Strategy):

    def act(self):
        pieces = self._get_rarest_desirable_pieces() 
        priority_peers = self._get_under_ten_request_peers() 
        for peer in priority_peers:
            pass

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
