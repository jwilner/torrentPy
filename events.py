
PROPOGATE = 'PROPOGATE'
NO_PROPOGATE = 'NO PROPOGATE'

class EventManager(object):
    def handle_event(self,event,e_type=None):
        if e_type is None:
            e_type = type(event)

        try:
            propogate,func = self._event_handlers
            func(event) 
        except KeyError:
            propogate = PROPOGATE

        if propogate == PROPOGATE:
            try:
                self._next_event_level.handle_event(event,e_type)
            except AttributeError:
                pass

class TorrentEvent(object):
    def __init__(self,**kwargs):
        self._data = kwargs

    def __getattr_(self,key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError

class HaveCompletePiece(TorrentEvent):
    '''Created with a piece index when a piece's download is completed''' 
    pass

class NewTorrentPeerCreated(TorrentEvent):
    '''Created with a peer as an argument when a peer has been created
    for a torrent''' 
    pass

class TrackerResponseEvent(TorrentEvent):
    '''Created when a tracker responds to an announce'''
    pass

class TorrentInitiated(TorrentEvent):
    '''Created at the end of a torrent's init function'''
    pass

class DownloadComplete(TorrentEvent):
    '''Created when the download of a whole torrent is complete'''
    pass

class Shutdown(TorrentEvent):
    '''Created when the program is instructed to shutdown'''
    pass
