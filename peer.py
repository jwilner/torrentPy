import messages, config, torrent_exceptions, logging, socket
from time import time
from collections import deque
from functools import partial
from utils import prop_and_memo, four_bytes_to_int, StreamReader

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Peer(torrent_exceptions.ExceptionManager,
            messages.MessageManager,object):
    '''Class representing peer for specific torrent download and
    providing interface with specific TCP socket'''

    def __init__(self,socket,client,torrent=None):
        logger.info('Instantiating peer %s',str(socket.getpeername()))
        self.socket = socket
        self.active = True
        self.peer_id = None
        
        self.address = socket.getpeername()
        self.ip, self.port = self.address

        self.outbox = deque() 
        self.sent_folder, self.archive = [], []

        self.handshake = {'sent': False, 'received': False } 
        self.client = client
        self._torrent = torrent
        
        if torrent is not None:
            self.has = [0]*torrent.num_pieces

        self.client.register(self, read=self.handle_incoming,
                                    write=self.handle_outgoing,
                                    error=self.handle_socket_error)

        self.last_heard_from = time()
        self.last_spoke_to = 0

        self._read_buffer = ''

        # for sending process, a queue of tuples -- msg and offset remaining
        # to be sent
        self._pending_send = deque()

        self.outstanding_requests = set()

        self.am_choking, self.am_interested = True, False
        self.choking_me, self.interested_me = True, False

        # Am I anal? Maybe.
        attr_setter = partial(self.__setattr__) 
        choking_me_setter = partial(attr_setter,'choking_me')
        am_choking_setter = partial(attr_setter,'am_choking')
        interested_me_setter = partial(attr_setter,'interested_me')
        am_interested_setter = partial(attr_setter,'am_interested')

        # Don't need to define a handler for KeepAlive, because undefined 
        # messages fail silently but still update 'last_heard_from'
        self._next_message_level = torrent

        self._message_handlers = {
            messages.INCOMING : {
                 messages.Handshake : self._process_handshake,
                 messages.Choke : lambda x : choking_me_setter(True),
                 messages.Unchoke : lambda x : choking_me_setter(False),
                 messages.Interested : lambda x : interested_me_setter(True),
                 messages.NotInterested : lambda x : interested_me_setter(False),
                 messages.Have : self._process_have,
                 messages.Bitfield : self._process_bitfield,
                 messages.Request : self._process_request,
                 messages.Piece : self._process_piece,
                 messages.Cancel : self._process_cancel
             },
            messages.OUTGOING : { 
                 messages.Handshake : self.record_handshake,
                 messages.Request : self.record_request,
                 messages.Cancel : self.record_cancel,
                 messages.Choke : lambda m : am_choking_setter(True),
                 messages.Unchoke : lambda m : am_choking_setter(False),
                 messages.Interested : lambda m : am_interested_setter(True),
                 messages.NotInterested : lambda m : am_interested_setter(False)
            }
        }

        # exception handling
        self._next_except_level = torrent
        self._exception_handlers = {

            }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<Peer for {0!s} at {1!s}:{2!s}>'.format(
                self.torrent, self.ip, self.port)
    
    def fileno(self):
        return self._socket.fileno()

    @property
    def choking_me(self):
        return self._choking_me

    @choking_me.setter
    def choking_me(self,value):
        # should I really filter out outstanding_requests here? Seems like
        # a job for the strategy class, no?
        if value is True: 
            self.outbox = deque(
                    msg for msg in self.outbox 
                        if type(msg) is not messages.Request)
        self._choking_me = value

    @property
    def torrent(self):
        return self._torrent

    @torrent.setter
    def torrent(self,t):
        '''stuff to do at time of torrent assignment'''
        self._torrent = t
        self.has = [0]*t.num_pieces

    @property
    def wanted_pieces(self):
        return {i for i,v in enumerate(self.has) 
                    if v and not self.torrent.have[i]}

    def handle_incoming(self):
        self.last_heard_from = time()

        for msg in self._read_from_socket():
            try:
                self.handle_message_event(msg)
            except torrent_exceptions.FatallyFlawedIncomingMessage as e:
                self.handle_exception(e)

    def handle_outgoing(self):
        sent_msgs = self._send_via_socket()

        for msg in sent_msgs:
            try:
                self.handle_message_event(msg)
            except torrent_exceptions.FatallyFlawedOutgoingMessage as e:
                self.handle_exception(e)

        if not self._pending_send:
            self._client.waiting_to_write.discard(self)

    def enqueue_message(self,msg):
        # if outbox is currently empty, then we'll want to tell the client
        notify = not self._pending_send
        self._pending_send.append([msg,len(msg)])

        if notify: # tell client
            self.client.waiting_to_write.add(self)

    def drop(self):
        '''Procedure to disconnect socket'''
        self.active = False
        self.socket.close()

    def _read_from_socket(self):
        new_string = self.socket.recv(config.DEFAULT_READ_AMOUNT)
        stream = StreamReader(self._read_buffer + new_string)

        try:
            while True:
                yield self._parse_string_to_message(stream)
        except torrent_exceptions.LeftoverException as e:
            self._read_buffer = e.leftover

    def _send_via_socket(self):
        '''Attempts to send message via socket. Returns a list of 
        msgs sent -- potentially empty if sent was incomplete'''

        strung = ''.join(str(msg)[-length:] for msg,length in self._pending_send)
        amt_sent = self._socket.send(strung)
         
        sent_msgs = []

        while amt_sent:
            # loop over lengths of pending msgs, updating their remaining amount 
            # or appending them to the response list if they've been completely sent
            if self._pending_send[0][1] > amt_sent:
                self._pending_send[0][1] -= amt_sent
                amt_sent = 0
            else:
                amt_sent -= length
                # appends actual msg to self
                sent_msgs.append(self._pending_send.leftpop()[0])

        if sent_msgs:
            self.last_spoke_to = time()

        return sent_msgs

    def _parse_string_to_message(self,stream):
        parts = []
        try:
            if not self.handshake['received']: # must be handshake
                try:
                    parts.append(ord(stream.read(1))) 
                    pstrlen = parts[0]
                    for l in (pstrlen,8,20,20): # protocol string, reserved, info hash, peer_id
                        parts.append(stream.read(l))
                    info_hash, peer_id = parts[3], parts[4]
                    return messages.Handshake(
                            peer_id,info_hash,reserved=parts[2],pstr=parts[1],
                            msg_event=messages.INCOMING)
                except torrent_exceptions.RanDryException as e:
                    raise torrent_exceptions.LeftoverException(value=''.join(parts)+e.unused)
            # normal message
            try:
                parts.append(stream.read(4))
                bytes_length_prefix = parts[0] 
                length = four_bytes_to_int(bytes_length_prefix)
                if length == 0:
                    return messages.KeepAlive()
                parts.append(stream.read(length))
                msg_body = parts[1]
                msg_id = ord(msg_body[0])
                return messages.lookup[msg_id](
                        msg_body[1:],from_string=True,msg_event=messages.INCOMING)
            except torrent_exceptions.RanDryException as e:
                raise torrent_exceptions.LeftoverException(value=''.join(parts)+e.unused)
        except torrent_exceptions.MessageParsingError as e:
            self.handle_exception(e)

    def record_handshake(self,msg):
        '''Fires as callback when handshake is sent. This is a method 
        because assignment can't happen in lambdas...'''
        self.handshake['sent'] = True

    def record_request(self,msg):
        self.outstanding_requests.add(msg.get_triple()[:2])

    def record_cancel(self,msg):
        self.outstanding_requests.discard(msg.get_triple()[:2])

    def _process_handshake(self,msg):
        self.handshake['received'] = True
        self.peer_id = msg.peer_id

        if msg.pstr != config.PROTOCOL:
            # will be caught by strategy
            raise torrent_exceptions.FatallyFlawedIncomingMessage(
                    peer=self,msg=msg)

        if not self.torrent: # this is an unknown peer
            # will resolve to client, where it'll be handled
            raise torrent_exceptions.UnknownPeerHandshake(
                    msg=msg,peer=self) 

    def _process_have(self,msg):
        self.has[msg.piece_index] = 1 

    def _process_bitfield(self,msg):
        quotient, remainder = divmod(self.torrent.num_pieces,8)

        # this appropriately rounds up the required length of the bitfield
        req_len = (quotient+1)*8 if remainder != 0 else quotient*8

        if len(msg.bitfield) != req_len:
            # gets caught by strategy
            raise torrent_exceptions.FatallyFlawedIncomingMessage(
                    peer=self,msg=msg)

        for i,p in enumerate(msg.bitfield):
            try:
                self.has[i] = p 
            except IndexError:
                break
    
    def _process_request(self,msg):
        if self.am_choking:
            # peer is being obnoxious -- do something about it?
            pass
        if msg.length > config.MAX_REQUESTED_PIECE_LENGTH:
            # this cat's cray -- drop 'em 
            raise torrent_exceptions.FatallyFlawedMessage(
                    peer=self,msg=msg)
        self.wants.add((msg.index,msg.begin,msg.length))

    def _process_cancel(self,msg):
        if msg.length > config.MAX_REQUESTED_PIECE_LENGTH:
            # initiate dropping procedure
            raise torrent_exceptions.FatallyFlawedMessage(
                    peer=self,msg=msg)
        self.wants.discard((msg.index,msg.begin,msg.length))  

    def _process_piece(self,msg):
        # do something in this context?
        self.outstanding_requests.discard((msg.index,msg.begin))
