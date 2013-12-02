import io, socket, logging, messages, events
import bitarray, torrent_exceptions, strategies
from file_handler import FileHandler
from tracker import TrackerHandler
from hashlib import sha1
from peer import Peer
from utils import memo, bencode, bdecode

logger = logging.getLogger(__name__)

class Torrent(events.EventManager,
                torrent_exceptions.ExceptionManager,
                messages.MessageManager):
    '''Wraps torrent metadata and keeps track of processes. Ideally,
    doesn't make any 'decisions.' They're all handled in the Strategy
    instance.'''

    def __init__(self,filename,client):
        '''Opens file with context manager'''
        self.client = client
        self.peers = {}
        self._cached_messages = {}
        self._trackers = set()

        with io.open(filename,'rb') as f:
            self._data = bdecode(f)

        # just so this init function doesn't get any bigger...
        self._calculate_properties()
        self._file_handler = FileHandler(self.query('name'),self.files,
                                     [p['length'] for p in self.pieces])

        # instantiate strategy with strategy_manager
        self._strategy_manager = strategies.StrategyManager(strategies.default_set)
        self._strategy_manager.update(strategies.INIT_EVENT)

        self._strategy = self._strategy_manager.current(self)
        self._strategy.init_callback() # should start up trackers

        self._message_dispatch = {
                messages.Handshake : self._handshake_maker,
                messages.Bitfield : self._bitfield_maker
                }

        self._next_message_level = self._strategy
        self._message_handlers = {
            messages.INCOMING: {
                messages.Have : lambda msg : self._increment_frequency(msg.index),
                messages.Bitfield : self._process_bitfield
                },
            messages.OUTGOING: {

                }
            }

        self._next_level = self._strategy
        self.exception_handlers = {
                }


    def __str__(self):
        return '<Torrent tracked at {0}>'.format(self.announce)

    def _calculate_properties(self):
        self.announce = self._query('announce')

        try:
            announce_list = self._query('announce-list')
        except KeyError:
            announce_list = []

        self.all_announce_urls = [self.announce]+self._parse_announce_list(announce_list)

        self.info = self._query('info')
        self.have = [0]*self.num_pieces
        self.frequency = [0]*self.num_pieces
        self.hashed_info = sha1(bencode(self.info)).digest()
        self.piece_length = self._query('piece length')

        pieces = self._query('pieces')
        self.piece_hashes = [pieces[i:i+20] for i in range(0,len(pieces),20)]
        self.num_pieces = len(self.piece_hashes)

        # tuple information pointing to filename maybe?
        self.piece_record = {i: {} for i in range(self.num_pieces)}

        self.file_mode = 'multi' if 'files' in self.info else 'single'
        if self.file_mode == 'single':
            self.files = [{'length': int(self.query('length')),
                             'path': [self._query('name')]}]
        else:
            self.files = [{'length':int(f['length']),
                             'path':f['path']} for f in self._query('files')]

        self.total_length = sum(f['length'] for f in self.files)

    def drop_peer(self,peer):
        '''Procedure to disconnect from peer'''
        del self.peers[peer.address]

    @property
    def downloaded(self):
        return 0
        return sum(len(piece.bytes) for piece in self._dled_pieces)

    @property
    def uploaded(self):
        return sum(peer.given for peer in self.peers.values())

    def dispatch(self,peer,message_type,*args,**kwargs):
        '''Handles instructing peers to send messages'''
        try:
            msg = self._message_dispatch[message_type](peer,*args,**kwargs)
        except KeyError:
            msg = message_type(*args,**kwargs)
        peer.enqueue_message(msg)

    def report_peer_addresses(self,peers):
        '''Adds peers if they're not already registered'''
        for peer_address in peers:
            if self._strategy.want_peer(peer_address):
                s = socket.socket()
                s.connect(peer_address)
                peer = Peer(s,self._client,self)
                self.add_peer(peer)

    def report_tracker_response(self,tracker):
        self._strategy.report_tracker_response(tracker)

    def add_peer(self,peer):
        self.peers[peer.address] = peer
        self._strategy.new_peer_callback(peer)

    def handle_block(self,piece_msg):
        index,begin,data = piece_msg.payload
        coords = begin,len(data)
        if coords in self.piece_record[index]:
            return
        self.piece_record[index][coords] = data # write data to disk here?

        if self._is_piece_complete(index):
            self._complete_piece_callback(index)

    def start_tracker(self,announce_url):
        t = TrackerHandler(self,announce_url)
        t.announce('started')
        self.trackers.add(t)

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
        return hashed in self.piece_hashes

    def _complete_piece_callback(self,index):
        if not self._verify_piece_hash(index):
            self.piece_record[index] = {}
        else:
            self.have[index] = 1

            if all(self.have): # download is completed
                self.strategy.download_completed(index)
            else:
                self.strategy.have_event(index)

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

    @memo
    def _query(self,key):
        '''This is the method for accessing data in the torrent
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

    def _handshake_maker(self,peer):
        return  messages.Handshake(
                    self.client.client_id,self.hashed_info)

    def _bitfield_maker(self,peer,override=None,*args):
        have = override if override is not None else self.have

        string = ''.join(str(bit) for bit in have)
        b = bitarray.bitarray(string)
        msg =  messages.Bitfield(b.tobytes())
        return msg
