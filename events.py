import torrent_exceptions


class EventManager(object):

    def handle_event(self, event, e_type=None):
        if e_type is None:
            e_type = type(event)

        try:
            self._event_handlers[e_type](event, e_type)
        except KeyError:
            try:
                self.event_observer.handle_event(event, e_type)
            except AttributeError:
                pass


class Event(object):
    required_keywords = {}

    def __init__(self, **kwargs):
        for kw in self.required_keywords:
            if kw not in kwargs:
                raise torrent_exceptions.InvalidEventCreated(
                    "{0} keyword not present in kwargs for {1}".format(
                        kw, type(self)))

        self._data = kwargs

    def __getattr_(self, key):
        try:
            return self._data[key]
        except KeyError:
            raise AttributeError


class TorrentEvent(Event):
    '''Parent class for all Torrent class events'''
    required_keywords = {'torrent'}
    pass


class HaveCompletePiece(TorrentEvent):
    '''Created with a piece index when a piece's download is completed'''
    pass


class UnknownPeerHandshake(TorrentEvent):
    '''Contains a peer and the handshake'''
    pass


class NewTorrentPeerCreated(TorrentEvent):
    '''Created with a peer as an argument when a peer has been created
    for a torrent'''
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


class PeerEvent(Event):
    '''Parent class for all peer events'''
    required_keywords = {'peer'}


class PeerRegistration(PeerEvent):
    '''Raised when new peer is instantiated.'''
    required_keywords = {'peer', 'read', 'write', 'error'}


class PeerReadyToSend(PeerEvent):
    '''Created when a peer is ready to send a message'''
    pass


class PeerDoneSending(TorrentEvent):
    '''Created when a peer is done sending messages'''
    pass


class TrackerEvent(TorrentEvent):
    required_keywords = {'tracker'}
    pass


class TrackerResponse(TrackerEvent):
    '''Created when a tracker responds to an announce'''
    pass


class TrackerFailure(TrackerEvent):
    '''Created when a tracker returns a warning or a failure'''
    pass


class TrackerRequest(TrackerEvent):
    '''Enqueues trakcer request with client'''
    pass
