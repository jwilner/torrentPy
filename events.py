
class EventManager(object):

    def handle_event(self,event,e_type=None):
        if e_type is None:
            e_type = type(event)

        try:
            targets,func = self._event_handlers[e_type]
            func(event)
        except KeyError:
            return

        try:
            for obj in targets:
                obj.handle_event(event,e_type)
        except AttributeError:
            return

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

class NewPeerRegistration(TorrentEvent):
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

class PeerReadyToSend(TorrentEvent):
    '''Created when a peer is ready to send a message'''
    pass

class PeerDoneSending(TorrentEvent):
    '''Created when a peer is done sending messages'''
    pass
