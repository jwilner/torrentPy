from utils import int_to_big_endian, four_bytes_to_int 

class InvalidMessage(Exception):
    pass

class InvalidHandshake(InvalidMessage):
    pass

class Msg(object):
    '''super class'''

    def __init__(self):
        self.observers = []

    def __repr__(self):
        return '{0}({1!s})'.format(self.__class__._name__,self)

class Handshake(Msg):
    def __init__(self,peerid,info_hash,reserved='\x00\x00\x00\x00\x00\x00\x00\x00',pstr='BitTorrent protocol'):
        super(Handshake,self).__init__()
        self._peerid = peerid
        self._info_hash = info_hash
        self._reserved = reserved 
        self._pstr = pstr
        self._pstrlen = chr(len(self._pstr))

    def __str__(self):
        return self._pstrlen + self._pstr + self._reserved + self._info_hash + self._peerid


class Message(Msg):
    id = ''
    _payload = ''

    def __init__(self,*args):
        super(Message,self).__init__()
        self._payload = args 

    def __str__(self):
        return ''.join(str(x) for x in (self.length_prefix,self.id)) + self.payload       

    @property
    def payload(self):
        return ''.join(str(x) for x in self._payload)

    @property
    def length_prefix(self):
        return int_to_big_endian(len(str(self.id)+self.payload))

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
        return self._payload[0]

class Bitfield(Message):
    '''Expects a bitfield as an init arg'''
    id = 5

class Request(Message):
    '''Expects index, begin, length as init args'''
    id = 6

    @property
    def index(self):
        return self._payload[0]

    @property
    def begin(self):
        return self._payload[1]

    @property
    def length(self):
        return self._payload[2]
          
class Piece(Message):
    '''Expects index, begin, block as init args'''
    id = 7

class Cancel(Request):
    '''Expects index, begin, length as init args'''
    id = 8

class Port(Message):
   '''Expects listen-port as an argument'''
   id = 9

msg_lookup = {sc.id:sc for sc in Message.__subclasses__() if sc.id}

def gather_handshake_from_socket(s):
    pstrlen = ord(s.recv(1))
    pstr = s.recv(pstrlen)
    reserved = s.recv(8)
    info_hash = s.recv(20)
    peer_id = s.recv(20)
    h = Handshake(peer_id,info_hash,reserved=reserved,pstr=pstr)
    return h

def gather_message_from_socket(s):
    '''Takes a socket and yields message objects contained within'''
    bytes_length_prefix = s.recv(4)        
    length = four_bytes_to_int(bytes_length_prefix)
    if not length:
        return KeepAlive()
    msg_body = s.recv(length)
    msg_id = ord(msg_body[0])
    return msg_lookup[msg_id](msg_body[1:])

