import config, io, torrent_exceptions
from utils import debencode, parse_peer_string, prop_and_memo

class TrackerHandler(torrent_exceptions.ExceptionManager,object):
    '''Represents the http tracker server and handles interactions
    with it -- nested within a torrent object'''

    def __init__(self,torrent,announce_url):
        self.announce_url = announce_url
        self.torrent = torrent
        self.client = torrent.client
        self.data = {}
        self.active = False
        # if these keys are present in data, they will be included in queries
        self._optional_params = {'numwant','key','trackerid','tracker id'}

        # implementing exception handling
        self._exception_handlers = {
                }
        self._next_level = self._torrent

    def announce(self,event=None):
        '''Registers an HTTP request to the tracker server'''
        request_params = self.announce_params

        if event:
            request_params['event'] = event
            if event == 'started':
                self.active = True
            elif event == 'closed':
                self.active = False

        self.client.make_tracker_request(
                self.announce_url,
                request_params,
                self.handle_response, # valid response callback
                self.torrent.handle_tracker_error) # error handler

    def handle_response(self,response):
        '''Cannot simply raise exception for errors here because asynchronous
        handling means the exception would resolve to the client before the
        torrent'''

        info = debencode(io.BytesIO(response.content))
        if 'failure reason' in info or 'warning message' in info:
            self.torrent.handle_tracker_failure(self,info)
        else:
            self.act_on_response(info)

    def act_on_response(self,info):
        '''Separated out from handle_response so it can be used as a callback
        after a warning message mebbe?'''
        self.data.update(info)

        # register new announce with client at next appropriate time

        self.torrent.report_peer_addresses(self.peer_addresses)

        # is this the right place for this to happen?
        self.torrent.report_tracker_response(self)

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

    @property
    def announce_params(self):
        params = {'info_hash':self.torrent.hashed_info,
                'peer_id':self.client.client_id,
                'port':self.client.port,
                'uploaded':self.torrent.uploaded,
                'downloaded':self.torrent.downloaded,
                'left':self.torrent.total_length,
                'compact':1,
                'supportcrypto':1}

        for key in self._optional_params:
            try:
                params[key] = self.data[key]
            except KeyError:
                continue

        return params

    @prop_and_memo
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

