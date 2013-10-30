import datetime, io, socket, logging, messages, bitarray, strategies, torrent_exceptions
from hashlib import sha1
from tracker import TrackerHandler
from peer import Peer
from utils import memo, bencode, debencode, prop_and_memo 

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class Torrent(object):
    '''Wraps torrent metadata and keeps track of processes'''

    def __init__(self,filename,client):
        '''Opens file with context manager'''
        self.client = client
        self.peers = {}
        self._cached_messages = {}

        with io.open(filename,'rb') as f:
            self._data = debencode(f)

        self.have = [0]*self.num_pieces
        self.frequency = [0]*self.num_pieces

        # tuple information pointing to filename maybe? 
        self.piece_record = {i: {} for i in range(self.num_pieces)} 

        self.strategy = strategies.RandomPieceStrategy(self)
        self.strategy_interval = 1.05

        self.file_mode = 'multi' if 'files' in self.info else 'single'

        self.trackers = {TrackerHandler(self,self.announce)} 
        self.trackers.update({TrackerHandler(self,a) for a in 
                             self._parse_announce_list(self.announce_list)})

        for t in self.trackers:
            t.announce_to_tracker('started')

        self._message_dispatch = {
                    messages.Handshake : self._handshake_maker,
                    messages.Bitfield : self._bitfield_maker
                }

        self.client.add_timer(self.strategy_interval,self.act_on_strategy)

    def __str__(self):
        return '<Torrent tracked at {0}>'.format(self.announce)

    def handle_tracker_error(self,response):
        raise Exception('Handle tracker error not yet implemented')

    def handle_tracker_failure(self,tracker,response):
        # just prune tracker, no?
        raise Exception('Handle tracker failure not yet implemented')

    def unregister(self,peer):
        logger.info('Unregistering peer %s',peer.address)
        del self.peers[peer.address]
        self.client.unregister(peer.socket)

    @property
    def downloaded(self):
        return 0
        return sum(len(piece.bytes) for piece in self._dled_pieces) 

    @property
    def uploaded(self):
        return sum(peer.given for peer in self.peers.values())

    @prop_and_memo
    def announce(self):
        return self.query('announce')

    @prop_and_memo
    def info(self):
        return self._data['info']

    @prop_and_memo
    def hashed_info(self):
        '''Hashed info dict for requests'''
        return sha1(bencode(self.info)).digest()
    
    @prop_and_memo
    def total_length(self):
        if self.file_mode is 'single':
            return self.query('length')
        else:
            return str(sum(int(f['length']) for f in self.query('files')))

    @prop_and_memo
    def piece_lengths(self):
        piece_lengths = [self.piece_length] * self.num_pieces
        last = self.total_length % self.piece_length
        if last != 0:
            piece_lengths[-1] = last
        return piece_lengths

    @prop_and_memo
    def piece_length(self):
        return self.query('piece length')

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

    def act_on_strategy(self):
        logger.info('Acting on strategy...')
        self.strategy.act()
        logger.info('Done acting on strategy...')
        self.client.add_timer(self.strategy_interval,self.act_on_strategy)

    def dispatch(self,peer,message_type,*args):
        '''Handles instructing peers to send messages'''
        try:
            try:
                msg = self._message_dispatch[message_type](peer,*args)
            except KeyError:
                msg = message_type(*args)
            peer.enqueue_message(msg)
        except torrent_exceptions.DoNotSendException:
            pass

    def report_peer_addresses(self,peers):
        '''Adds peers if they're not already registered'''
        logger.info('Found peers %s',peers)
        for peer_address in peers:
            if peer_address not in self.peers and peer_address[0] != '74.212.183.186' and peer_address[0] != '72.229.191.53':
                logger.info('Adding peer %s',str(peer_address))
                s = socket.socket()
                s.connect(peer_address)    
                logger.info('Connected to peer %s also known as %s',str(peer_address),str(s.getpeername()))
                peer = Peer(s,self.client,self)
                logger.info('Enqueuing Handshake to peer %s',str(peer_address))
                self.dispatch(peer,messages.Handshake)
                self.dispatch(peer,messages.Bitfield)
                self.peers[peer_address] = peer

    def handle_block(self,piece_msg):
        index,begin,data = piece_msg.payload 
        coords = begin,len(data) 
        print 'We\'re dealing with a blcok with these coordinates ',coords
        print 'This index has these current coords ',self.piece_record[index]
        if coords in self.piece_record[index]:
            return
        self.piece_record[index][coords] = data # write data to disk here?
        this_piece = sorted(self.piece_record[index].keys())

        _,l_end = this_piece[0]
        print 'Block begins at {0} and ends at {1}'.format(_,l_end)
        for begin,end in this_piece[1:]:
            print 'Block begins at {0} and ends at {1} and {2}'.format(begin,end,l_end)
            if l_end != begin:
                break
            l_end = end     
        else:
            print self.piece_lengths[index], l_end
            if self.piece_lengths[index] == begin+l_end:
                self._complete_piece_procedure(index)

    def _complete_piece_procedure(self,index):
        keys = sorted(self.piece_record[index].keys())
        joined = ''.join(self.piece_record[index][k] for k in keys)
        print 'String is ', len(joined), ' long'
        hashed = sha1(joined).digest()
        print hashed
        if hashed != self.pieces[index]:
            if hashed not in self.pieces:
                self.piece_record[index] = {}
            print 'Hashed info for index is at ',self.pieces.index(hashed)

        self.have[index] = 1
        print 'WE HAVE DEFINITELY RECEIVED PART {0}'.format(index)
        print self.have
        if len(filter(None,(h == 1 for h in self.have))) == 78:
            print 'Hit final loop'
            with open('testfile.jpg','wb+') as f:
                for key in sorted(self.piece_record.keys()):
                    for coords in sorted(self.piece_record[key]):
                        print 'Writing...'
                        f.write(self.piece_record[key][coords])
            raise torrent_exceptions.TorrentComplete
        self.strategy.have_event(index)

    def _parse_announce_list(self,announce_list):
        '''Recursive method that will make sure to get every possible Tracker 
        out of announce list'''
        return_set = set()
        for item in announce_list:
            if type(item) is list:
                return_set.update(self._parse_announce_list(item))
            else:
                return_set.add(item)
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
            if type(v) is dict:
                try:
                    return self._traverse_tree(key,v)
                except KeyError:
                    continue
        else:
            # this pattern ensures that an IndexError is only raised if the 
            # key isn't found at ANY level of recursion
            raise KeyError('{0} not found in torrent data.'.format(key))

    def _handshake_maker(self,peer,*args):
        try:
            msg = self._cached_messages[messages.Handshake]
        except KeyError:
            msg = self._cached_messages = messages.Handshake(
                    self.client.client_id,self.hashed_info)
        msg.observers = [peer.record_handshake]
        return msg
      
    def _bitfield_maker(self,peer,*args):
        if not any(self.have):
            raise torrent_exceptions.DoNotSendException
        string = ''.join(str(bit) for bit in self.have) 
        b = bitarray.bitarray(string)
        msg =  messages.Bitfield(b.tobytes())   
        return msg
