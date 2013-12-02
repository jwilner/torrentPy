import config, io, torrent_exceptions, events
from utils import debencode, parse_peer_string

class TrackerHandler(torrent_exceptions.ExceptionManager,object):
    '''Represents the http tracker server and handles interactions
    with it -- nested within a torrent object'''

    def __init__(self,torrent,announce_url):
        self.announce_url = announce_url
        self.data = {}
        self.active = False

        # if these keys are present in data, they should be included in queries
        self.optional_params = {'numwant','key','trackerid','tracker id'}

        # implementing exception handling
        self._exception_handlers = {}

    def handle_response(self,response):
        '''Cannot simply raise exception for errors here because asynchronous
        handling means the exception would resolve to the client before the
        torrent'''

        info = debencode(io.BytesIO(response.content))
        if 'failure reason' in info or 'warning message' in info:
            # raise event here instead
            self.handle_event(
                    events.TrackerFailure(tracker=self,info=info))
        else:
            old_peers = set(self.peer_addresses)
            self.data.update(info)
            new_peers = set(self.peer_addresses) - old_peers

            self.handle_event(
                    events.TrackerResponse(
                        tracker=self,new_peer_addresses=new_peers))

    @property
    def interval(self):
        try:
            return self.data['min interval']
        except KeyError:
            try:
                return self.data['interval']
            except KeyError:
                return config.DEFAULT_ANNOUNCE_INTERVAL

    @property
    def peer_addresses(self):
        peer_info = self.data['peers']
        if type(peer_info) is str:
            peers = parse_peer_string(peer_info)
        else:
            peers = ((p['ip'],p['port']) for p in peer_info)
        return peers

    def scrape_url(self):
        '''Calculates the url to scrape torrent status info from'''
        # find last slash in announce url. if text to right is announce,
        # replace it with 'scrape' for the scrape URL else AttributeError
        ind = self.announce_url.rindex('/') + 1
        end = ind+8
        if self.announce_url[ind:end] is 'announce':
            return self.announce_url[:ind]+'scrape'+self.announce_url[end:]
        else:
            raise AttributeError

