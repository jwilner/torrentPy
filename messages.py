import config
from bitarray import bitarray
from utils import int_to_big_endian, four_bytes_to_int, prop_and_memo, memo

OUTGOING = 'OUTGOING'
INCOMING = 'INCOMING'

class MessageManager():

    def _handle_message_event(self,msg,msg_type=None):
        '''Dispatch procedure common to all message handling objects'''
        if msg_type is None:
            msg_type = type(msg)

        try:
            self._message_handlers[msg.EVENT_TYPE][msg_type](msg)
        except KeyError:
            pass

        try: 
            self._next_message_level.handle_message_event(self,msg,msg_type)
        except AttributeError:
            pass


class InvalidMessage(Exception):
    pass

class InvalidHandshake(InvalidMessage):
    pass

class Msg(object):
    '''super class'''

    def __init__(self,**kwargs):
        self.EVENT_TYPE = kwargs.pop('msg_event') 
        self.peer = None

    def __repr__(self):
        return '{0}'.format(type(self))

class Handshake(Msg):
    def __init__(self,peerid,info_hash,reserved=config.RESERVED_BYTES,pstr=config.PROTOCOL):
        super(Handshake,self).__init__()
        self.peer_id = peerid
        self.info_hash = info_hash
        self.reserved = reserved 
        self.pstr = pstr
        self.pstrlen = chr(len(self.pstr))

    def __str__(self):
        msg =  self.pstrlen + self.pstr + self.reserved + self.info_hash + self.peer_id
        return msg

class Message(Msg):
    id = ''
    
    def __init__(self,*args,**kwargs):
        super(Message,self).__init__()
        from_string = kwargs.pop('from_string',False)

        if from_string:
            self._string = args[0]
        else:
            self._payload = args

    @memo
    def __str__(self):
        body = '{0}{1}'.format(self._encoded_id(),self.string)
        strlen = int_to_big_endian(len(body))
        msg = '{0}{1}'.format(strlen,body)
        print 'This {0} is {1} characters long.'.format(type(self),len(msg))
        return msg

    @prop_and_memo
    def string(self):
        '''the body of the message as a string'''
        try:
            return self._string
        except AttributeError:
            self._string = self._parse_payload()
            return self._string

    @prop_and_memo
    def payload(self):
        '''the body of the message as a list'''
        try:
            return self._payload
        except:
            self._payload = self._parse_string()
            return self._payload

    def _parse_string(self):
        return []

    def _parse_payload(self):
        return ''

    @memo
    def _encoded_id(self):
        return chr(self.id)

class KeepAlive(Message):
    '''No payload or id'''
    pass

class Choke(Message):
    '''No payload'''
    id  = 0

class Unchoke(Message):
    '''No payload'''
    id = 1

class Interested(Message):
    '''No payload'''
    id = 2

class NotInterested(Message):
    '''No payload'''
    id = 3

class Have(Message):
    '''Expects piece index as an init arg'''
    id = 4

    @property
    def piece_index(self):
        return four_bytes_to_int(self.payload)

    def _parse_string(self):
        return self._string

class Bitfield(Message):
    '''Expects a bitfield as an init arg'''
    id = 5

    @property
    def bitfield(self):
        b = bitarray()
        b.frombytes(self.payload)
        return b

    def _parse_string(self):
        return self._string

    def _parse_payload(self):
        return self.bitfield.tobytes()

class Request(Message):
    '''Expects index, begin, length as init args'''
    id = 6

    @property
    def index(self):
        return self.payload[0]

    @property
    def begin(self):
        return self.payload[1]

    @property
    def length(self):
        return self.payload[2]

    def get_triple(self):
        return self.index,self.begin,self.length

    def _parse_string(self): 
        return [four_bytes_to_int(self._string[i:i+4]) for i in (0,4,8)]

    def _parse_payload(self):
        return ''.join(int_to_big_endian(i) for i in self._payload)

    def __repr__(self):
        return '<Request for piece {0} beginning at {1} with length {2} >'.format(self.index,self.begin,self.length)

class Piece(Message):
    '''Expects index, begin, block as init args'''
    id = 7

    @property
    def index(self):
        return self.payload[0]

    @property
    def begin(self):
        return self.payload[1]

    @property
    def block(self):
        return self.payload[2]

    def _parse_string(self):
        return [four_bytes_to_int(self._string[i:i+4]) for i in (0,4)]+[self._string[8:]]

    def _parse_payload(self):
        return ''.join(int_to_big_endian(i) for i in self._payload) 

    def __repr__(self):
        return '<Piece message for piece {0} beginning at {1} with length {2} >'.format(self.index,self.begin,len(self.block))


class Cancel(Request): # employs same payload as Request
    '''Expects index, begin, length as init args'''
    id = 8

class Port(Message):
   '''Expects listen-port as an argument'''
   id = 9


lookup = { sc.id:sc for sc in Message.__subclasses__()}
