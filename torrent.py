import datetime, io, socket
from hashlib import sha1
from tracker import TrackerHandler
from peer import Peer
from utils import memo, bencode, debencode, prop_and_memo 

class Torrent(object):
    '''Wraps torrent metadata and keeps track of processes'''

    def __init__(self,filename,client):
        '''Opens file with context manager'''
        self.client = client
        self.peers = {}

        with io.open(filename,'rb') as f:
            self._data = debencode(f)

        self.file_mode = 'multi' if 'files' in self.info else 'single'

        self.trackers = {TrackerHandler(self,self.announce)} 
        self.trackers += self._parse_announce_list(self.announce_list)

        for t in self.trackers:
            t.announce_to_tracker('started')

    def __hash__(self):
        return self._hashed_info

    def __str__(self):
        return '<Torrent tracked at {0}>'.format(self.announce)

    def handle_tracker_error(self,response):
        raise Exception('Handle tracker error not yet implemented')

    def handle_tracker_failure(self,tracker,response):
        # just prune tracker, no?
        raise Exception('Handle tracker failure not yet implemented')

    @property
    def downloaded(self):
        return sum(len(piece.bytes) for piece in self._dled_pieces) 

    @property
    def uploaded(self):
        return sum(peer.given for peer in self.peers.values())

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
    def num_pieces(self):
        '''Because this operation is called all over the place'''
        return len(self.pieces)

    @prop_and_memo
    def announce_list(self):
        '''N.B. each item here seems to be encased in a list by default.'''
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
        '''Returns a date object; else a KeyError bubbles through'''
        return datetime.date.fromtimestamp(self.query('creation date'))

    @memo
    def query(self,key):
        '''This is the public method for accessing data in the torrent
        file. If data isn't found, a KeyError will bubble through here.'''
        return self._traverse_tree(key,self._data)

    def _traverse_tree(self,key,tree):
        '''Recursive method searching the structure of the tree, will raise
        an index error if nothing is found.'''
        for k,v in tree.items():
            if k == key:
                return v 
            if type(v) == dict:
                try:
                    return self._traverse_tree(key,v)
                except KeyError:
                    continue
        else:
            # this pattern ensures that an IndexError is only raised if the 
            # key isn't found at ANY level of recursion
            raise KeyError(key + ' not found in torrent data.')

