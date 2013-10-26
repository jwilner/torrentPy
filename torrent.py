import datetime, io, config, socket
from hashlib import sha1
from peer import Peer
from utils import memo, bencode, debencode, prop_and_memo, parse_peer_string

class TrackerHandler(object):
    '''Represents the http tracker server and handles interactions
    with it -- nested within a torrent object'''

    def __init__(self,torrent,announce_url):
        self.announce_url = announce_url
        self._torrent = torrent
        self.client = torrent.client
        self.data = {}
        
        # if these keys are present in data, they will be included in queries
        self._optional_params = {'numwant','key','trackerid',
                'tracker id'}

    def announce_to_tracker(self,event=None):
        '''Registers an HTTP request to the tracker server'''
        request_params = self.announce_params

        if event:
            request_params['event'] = event

        self.client.make_tracker_request(
                self.announce_url,
                request_params,
                self.handle_response,
                self.torrent.handle_tracker_error)

    def handle_response(self,response):
        '''Cannot simply raise exception for errors here because asynchronous
        handling means the exception would resolve to the client before the 
        torrent'''

        info = debencode(io.BytesIO(response.content)) 
        if 'failure reason' or 'warning message' in info:
            self.torrent.handle_tracker_failure(self,info) 
        else:
            self.act_on_response(info)

    def act_on_response(self,info):
        self.data.update(info)
         
        # register new announce with client at next appropriate time
        self.client.add_timer(self.interval,self.announce_to_tracker)
        self.torrent.report_peer_addresses(self.peer_addresses)
                                
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
        if self.announce_url[ind:end] == 'announce':
            return self.announce_url[:ind]+'scrape'+self.announce_url[end:]
        else:
            raise AttributeError


class Torrent(object):
    '''Wraps torrent metadata and keeps track of processes'''

    def __init__(self,filename,client):
        '''Opens file with context manager'''
        self.client = client
        self.peers = {}

        with io.open(filename,'rb') as f:
            self._data = debencode(f)

        self.file_mode = 'multi' if 'files' in self.info else 'single'
        self.downloaded = 0
        self.uploaded = 0

        self.trackers = {TrackerHandler(self,self.announce)} 
        self.trackers += self._parse_announce_list(self.announce_list)

        for t in self.trackers:
            t.announce_to_tracker('started')

    def __hash__(self):
        return self._hashed_info

    def __str__(self):
        return '<Torrent tracked at {0}>'.format(self.announce)

    def update_data(self,new_data):
        self._data.update(new_data)
        self.last_updated = datetime.datetime()
    
        
    def handle_tracker_error(self,response):
        raise Exception('Handle tracker error not yet implemented')

    def handle_tracker_failure(self,tracker,response):
        # just prune tracker, no?
        raise Exception('Handle tracker failure not yet implemented')

    @prop_and_memo
    def announce(self):
        return self.query('announce')

    @prop_and_memo
    def info(self):
        return self.query('info')

    @prop_and_memo
    def hashed_info(self):
        '''Hashed info dict for requests'''
        return sha1(bencode(self.info)).digest()
    
    @prop_and_memo
    def total_length(self):
        if self.file_mode == 'single':
            return self.query('length')
        else:
            return str(sum(int(f['length']) for f in self.query('files')))

    @prop_and_memo
    def pieces(self):
        '''Returns a list of the hash codes for each piece, divided by length 
        20'''
        pieces = self.query('pieces')
        return [pieces[i:i+20] for i in range(0,len(pieces),20)]

    @prop_and_memo
    def announce_list(self):
        '''N.B. each item here seems to be encased in a list by default. Again,'''
        try:
            return self.query('announce-list')
        except KeyError:
            return []

    def report_peer_addresses(self,peers):
        '''Adds peers if they're not already registered'''
        for peer_address in peers:
            if peer_address not in self.peers:
                s = socket.socket()
                s.connect(peer_address)    
                peer = Peer(s,self.client,self)
                peer.send_handshake()
                self.peers[peer_address] = peer

    def _parse_announce_list(self,announce_list):
        '''Recursive method that will make sure to get every possible Tracker 
        out of announce list'''
        return_set = {}
        for item in announce_list:
            if type(item) == list:
                return_set += self._parse_announce_list(item)
            else:
                return_set.add(TrackerHandler(item,self))
        return return_set

    @prop_and_memo
    def creation_date(self):
        '''Returns a date object; else an KeyError bubbles through'''
        return datetime.date.fromtimestamp(self.query('creation date'))


    @memo
    def query(self,key):
        '''This is the public method for accessing data in the torrent
        file. If data isn't found, a KeyError will bubble through here.'''
        return self._traverseTree(key,self._data)

    def _traverseTree(self,key,tree):
        '''Recursive method searching the structure of the tree, will raise
        an index error if nothing is found.'''
        for k,v in tree.items():
            if k == key:
                return v 
            if type(v) == dict:
                try:
                    return self._traverseTree(key,v)
                except KeyError:
                    continue
        else:
            # this pattern ensures that an IndexError is only raised if the 
            # key isn't found at ANY level of recursion
            raise KeyError(key + ' not found in torrent data.')

