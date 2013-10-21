import io,datetime
from hashlib import sha1
from urllib import urlencode
from utils import memo, bencode, debencode

def prop_and_memo(f):
    return property(memo(f))

class BitTorrentClient():
    '''Object encapsulating central info for the process'''
    
    def __init__(self,port=6881):
        self._data = {'client_id':'-jw0001-123456789012',
                      'port':port}

    def __repr__(self):
        return "<Joe's BitTorrent Client -- id: {0}>".format(self._data['client_id'])

    def __getattr__(self,key):
        return self._data[key]

class Torrent():
    '''Wrapper for torrent metadata file'''

    def __init__(self,filename):
        '''Opens file with context manager'''
        with io.open(filename,'rb') as f:
            self._data = debencode(f)
        self.file_mode = 'multi' if 'files' in self.info else 'single'
    
    def update_data(self,new_data):
        self._data.update(new_data)
        self.last_updated = datetime.datetime()

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
    def length(self):
        return self.query('length')

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
            raise KeyError(key+' not found in torrent data.')

class LiveTorrent(Torrent):
    '''Extension of Torrent, provides access to methods and data
    required for a currently operating torrent.'''
    
    def __init__(self,filename,client):
        Torrent.__init__(self,filename)  
        self.client = client

    @prop_and_memo
    def announce_url_query_string(self):
        return self.announce + '?' + urlencode(self.announce_params)
    
    @prop_and_memo
    def announce_params(self):
        return {'info_hash':self.hashed_info,
                'peer_id':self.client.client_id,
                'port':self.client.port,
                'uploaded':0,
                'downloaded':0,
                'left':self.length,
                'compact':1,
                'event':'started'}
    
if __name__ == '__main__':
    from pprint import pprint
    from torrent_requests import send_started_announce_request, get_torrent_scrape
    t = LiveTorrent('../../../data/torrentPy/flagfromserver.torrent',BitTorrentClient())
    h = send_started_announce_request(t)

    for peer in (h['peers'][i:i+6] for i in range(0,len(h['peers']),6)):
        print '.'.join(str(ord(ip_part)) for ip_part in peer[:4])
        print 256*(ord(peer[4])+ord(peer[5]))
    pprint(h)
    
