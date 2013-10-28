import messages, config
from time import time
from collections import deque
from functools import partial
from utils import prop_and_memo

class Peer(object):
    '''Class representing peer for specific torrent download and
    providing interface with specific TCP socket'''

    def __init__(self,socket,client,torrent=None):
        self.socket = socket

        self.outbox = deque() 
        self.sent_folder, self.archive = [], []

        self._handshake = {'sent': False, 'received': False } 
        self.client = client
        self._torrent = torrent

        self.client.register(self.socket,
                                read=self.parse_message,
                                write=self.send_next_message,
                                error=self.handle_socket_error)

        self.last_heard_from = time()

        self.am_choking, self.am_interesting = True, False
        self.choking_me, self.interesting_me = True, False

        attr_setter = partial(self.__setattr__) 
        choke_setter = partial(attr_setter,'choking_me')
        interest_setter = partial(attr_setter,'interesting_me')

        self._message_handlers = {
            messages.Handshake : self._process_handshake,
            messages.Choke : lambda x : choke_setter(True),
            messages.Unchoke : lambda x : choke_setter(False),
            messages.Interested : lambda x : interest_setter(True),
            messages.NotInterested : lambda x : interest_setter(False),
            messages.Have : self._process_have,
            messages.Bitfield : self._process_bitfield,
            messages.Request : self._process_request,
            messages.Piece : self._process_piece,
            messages.Cancel : self._process_cancel
                }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<Peer for {0!s} at {1!s}:{2!s}>'.format(
                self.torrent, self.ip, self.port)

    @property
    def choking_me(self):
        return self._choking_me

    @choking_me.setter
    def choking_me(self,value):
        if value is True: 
            self.outbox = deque()
        self._choking_me = value

    @property
    def torrent(self):
        return self._torrent

    @torrent.setter
    def torrent(self,t):
        self._torrent = t
        self.has = [0]*t.num_pieces

    def send_handshake(self):
        handshake = messages.Handshake(
                        self.client.client_id,
                        self.torrent.hashed_info)
        handshake.observers.append(self._register_handshake)
        self.outbox.append(handshake)

    def parse_message(self):
        self.last_heard_from = time()

        if self._handshake['received']:
            msg = messages.gather_message_from_socket(self.socket) 
        else:
            # InvalidHandshakeException can bubble through here.
            msg = messages.gather_handshake_from_socket(self.socket)

        self.archive.append(msg)
        
        try:
            self.message_handlers[type(msg)](msg)
        except KeyError:
            # e.g. for KeepAlive message or any unimplemented handlers
            pass

    def send_next_message(self):
        try:
            msg = self.outbox.popleft()
            self._send_message(msg)
        except IndexError: #queue empty
            pass

    def handle_socket_error(self):
        pass

    def update_message_handlers(self,**handlers):
        pass

    @prop_and_memo
    def address(self):
        return self.socket.getsockname()

    @prop_and_memo
    def ip(self):
        return self.address[0]

    @prop_and_memo
    def port(self):
        return self.address[1]

    def _send_message(self,msg):
        self.socket.sendall(str(msg))
        self.sent_folder.append(msg)

        # notify any observers
        for observer in msg.observers:
            observer(msg,True)

    def _register_handshake(self,msg,sent):
        '''Fires as callback when handshake is sent. This is a method 
        because assignment can't happen in lambdas...'''
        self._handshake['sent'] = sent

    def _process_have(self,msg):
        self.has[msg.piece_index] = True 

    def _process_bitfield(self,msg):
        if len(msg.bitfield) is not self.torrent.num_pieces:
            # initiate dropping procedure
            pass
        for i,p in enumerate(msg.bitfield):
            self.has[i] = bool(p)
    
    def _process_request(self,msg):
        if self.am_choking:
            # peer is being obnoxious -- do something about it?
            pass
        if msg.length > config.MAX_REQUESTED_PIECE_LENGTH:
            # this cat's cray -- drop 'em 
            self.torrent.drop_peer(self)
        self.wants.add((msg.index,msg.begin,msg.length))

    def _process_cancel(self,msg):
        if msg.length > config.MAX_REQUESTED_PIECE_LENGTH:
            # initiate dropping procedure
            self.torrent.drop_peer(self)
        self.wants.discard((msg.index,msg.begin,msg.length))  

    def _process_piece(self,msg):
        # do something in this context?
        self.torrent.add_block(msg)
