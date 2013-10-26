import datetime
import io
from hashlib import sha1
from utils import memo, bencode, debencode, prop_and_memo

class Tracker(object):
    '''Represents the http tracker server and handles interactions
    with it -- nested within a torrent object'''
    def __init__(self,torrent,announce_url):
        self.announce_url = announce_url
        self._torrent = torrent

    def handle_tracker_response(self,response):
        '''Cannot simply raise exception for errors here because asynchronous
        handling means the exception would resolve to the client before the 
        torrent'''

        info = debencode(io.BytesIO(response.content)) 
        if 'failure reason' in info:
            self._torrent.handle_tracker_failure(self,info)         
        elif 'warning message' in info:
            self._torrent.handle_tracker_warning(self,info) 
        else:
            self._parse_tracker_response(info)

    def _parse_tracker_response(self,info):
        pass 

class Torrent(object):
    '''Wraps torrent metadata and keeps track of processes'''

    def __init__(self,filename,client):
        '''Opens file with context manager'''
        self.client = client

        with io.open(filename,'rb') as f:
            self._data = debencode(f)

        self.file_mode = 'multi' if 'files' in self.info else 'single'
        self.downloaded = 0
        self.uploaded = 0

        self.trackers = {Tracker(self.announce,self)} 
        self.trackers += self._parse_announce_list(self.announce_list)

        request_params = self.announce_params
        request_params['event'] = 'started'

        for t in self.trackers:
            client.make_tracker_request(
                t.announce,
                request_params,
                t.handle_tracker_response,
                self.handle_tracker_error)

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

    def handle_tracker_warning(self,tracker,response):
        raise Exception('Handle tracker warning not yet implemented')

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

    def _parse_announce_list(self,announce_list):
        '''Recursive method that will make sure to get every possible Tracker 
        out of announce list'''
        return_set = {}
        for item in announce_list:
            if type(item) == list:
                return_set += self._parse_announce_list(item)
            else:
                return_set.add(Tracker(item,self))
        return return_set

    @prop_and_memo
    def announce_params(self):
        return {'info_hash':self.hashed_info,
                'peer_id':self.client.client_id,
                'port':self.client.port,
                'uploaded':self.uploaded,
                'downloaded':self.downloaded,
                'left':self.total_length,
                'compact':1,
                'supportcrypto':1}

    @prop_and_memo
    def creation_date(self):
        '''Returns a date object; else an KeyError bubbles through'''
        return datetime.date.fromtimestamp(self.query('creation date'))

    @prop_and_memo
    def scrape_url(self):
        '''Calculates the url to scrape torrent status info from'''
        # find last slash in announce url. if text to right is announce, 
        # replace it with 'scrape' for the scrape URL else AttributeError
        ind = self.announce.rindex('/') + 1
        end = ind+8
        if self.announce[ind:end] == 'announce':
            return self.announce[:ind]+'scrape'+self.announce[end:]
        else:
            raise AttributeError

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


        
if __name__ == '__main__':
    from pprint import pprint
    from main import BitTorrentClient
    from torrent_requests import send_started_announce_request
    t = LiveTorrent('../../../data/torrentPy/flagfromserver.torrent',BitTorrentClient())
    h = send_started_announce_request(t)
    for g in make_peers(t,h['peers']):
        print str(g)
    pprint(h)
    
