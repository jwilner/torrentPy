import datetime, io, socket, logging, messages, config
import bitarray, torrent_exceptions, strategies
from hashlib import sha1
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
        self._trackers = set()

        with io.open(filename,'rb') as f:
            self._data = debencode(f)

        self.have = [0]*self.num_pieces
        self.frequency = [0]*self.num_pieces

        # tuple information pointing to filename maybe? 
        self.piece_record = {i: {} for i in range(self.num_pieces)} 

        self.file_mode = 'multi' if 'files' in self.info else 'single'

        self._strategy_manager = strategies.StrategyManager(config.DEFAULT_STRATEGY_SET)
        self._strategy_manager.update(strategies.INIT_EVENT)

        # instantiate strategy with strategy_manager
        self.strategy = self._strategy_manager.current(self)
        self.strategy.init_callback() # should set up trackers

        self._message_dispatch = {
                    messages.Handshake : self._handshake_maker,
                    messages.Bitfield : self._bitfield_maker
                }
        
        self.receipt_callbacks = {
                messages.Have : lambda msg : self._increment_frequency(msg.index),
                messages.Bitfield : self._process_bitfield
                }

        self.exception_handlers = {
                }

    def __str__(self):
        return '<Torrent tracked at {0}>'.format(self.announce)

    def handle_exception(self,e): 
        try:
            self._exception_handlers[type(e)](e)
        except KeyError:
            self.strategy.handle_exception(e)

    def receipt_callback(self,peer,msg):
        '''Just dispatches with private strategy object''' 
        self._strategy[type(msg)](peer,msg)


    def drop_peer(self,peer):
        '''Procedure to disconnect from peer'''
        del self.peers[peer.address]

    @prop_and_memo
    def files(self):
        if self.file_mode == 'single':
            return [{'length':self.total_length,
                     'path': [self.query('name')]}]
        else:
            return self.query('files')

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
    def all_announce_urls(self):
        return [self.annouce]+self._parse_announce_list(self.announce_list)


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

    def dispatch(self,peer,message_type,*args):
        '''Handles instructing peers to send messages'''
        try:
            try:
                msg = self._message_dispatch[message_type](peer,*args)
            except KeyError:
                msg = message_type(*args)
            peer.enqueue_message(msg)
        except torrent_exceptions.DoNotSendException:
            # for example, stops us from sending a bitfield when we have nothing?
            pass

    def report_peer_addresses(self,peers):
        '''Adds peers if they're not already registered'''
        for peer_address in peers:
            if self.strategy.want_peer(peer_address):
                s = socket.socket()
                s.connect(peer_address)    
                peer = Peer(s,self._client,self)
                self.add_peer(peer)
                
    def add_peer(self,peer):
        self.peers[peer.address] = peer
        self.strategy.new_peer_callback(peer)

    def receive_peer_message(self,peer,msg):
        self.strategy.receipt_callback(peer,msg)

    def handle_block(self,piece_msg):
        index,begin,data = piece_msg.payload 
        coords = begin,len(data) 
        if coords in self.piece_record[index]:
            return
        self.piece_record[index][coords] = data # write data to disk here?

        if self._is_piece_complete(index):
            self._complete_piece_callback(index)

    def _is_piece_complete(self,index):
        this_piece = sorted(self.piece_record[index].keys())
        _,l_end = this_piece[0]
        for begin,end in this_piece[1:]:
            if l_end != begin:
                return False
            l_end = end     
         
        return self.piece_lengths[index] == begin+l_end

    def _process_bitfield(self,msg):
        for i,p in enumerate(msg.bitfield):
            if p:
                self._increment_frequency(i)

    def _increment_frequency(self,index):
        self.frequency[index] += 1

    def _verify_piece_hash(self,index):
        keys = sorted(self.piece_record[index].keys())
        joined = ''.join(self.piece_record[index][k] for k in keys)
        hashed = sha1(joined).digest()
        return hashed in self.pieces

    def _complete_piece_callback(self,index):
        if not self._verify_piece_hash(index):
            self.piece_record[index] = {}
        else:
            self.have[index] = 1

            if all(self.have): # download is completed
                self.strategy.download_completed(index)
            else: 
                self.strategy.have_event(index)

    def _old_write_to_disk(self):
        with open('testfile.jpg','wb+') as f:
            for key in sorted(self.piece_record.keys()):
                for coords in sorted(self.piece_record[key]):
                    f.write(self.piece_record[key][coords])

    def _parse_announce_list(self,announce_list):
        '''Recursive method that will make sure to get every possible Tracker 
        out of announce list'''
        return_list = list()
        for item in announce_list:
            if type(item) is list:
                return_list.extend(self._parse_announce_list(item))
            else:
                return_list.append(item)
        return return_list

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
