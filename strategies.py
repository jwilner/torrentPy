import messages

'''Strategy objects would be chosen based on the current state of the
local torrent, while the strategy object makes decisions about actions for 
particular peers on a given go through the event loop'''

class Strategy(object):
    '''extensible class internalizing the strategy'''

    def __init__(self,torrent):
        self._torrent = torrent

    def act(self):
        pass

    def get_desirable_pieces(self):
        '''Outstanding pieces that are still required '''
        return sorted((i for i,f in enumerate(self._torrent.frequency) 
                                     if not self._torrent.have[i]),
                                key=lambda x:x[1],
                                reversed=True)

    def get_under_ten_request_peers(self):
        return {peer for peer in self.torrent.peers if len(peer.outstanding_requests) < 10 } 

class RarestFirstStrategy(Strategy):

    def act(self):
        pass

