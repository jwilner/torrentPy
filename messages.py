from utils import int_to_big_endian, four_bytes_to_int, prop_and_memo

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

    def __init__(self,from_string=False,*args):
        super(Message,self).__init__()
        if from_string:
            self._string = args
        else:
            self._payload = args

    def __str__(self):
        return ''.join(str(x) for x in (self.length_prefix,self.id)) + self._formatted_string       

    @prop_and_memo
    def _formatted_string(self):
        try:
            return self._string
        except AttributeError:
            return ''.join(str(x) for x in self._parsed_payload)

    @prop_and_memo
    def _parsed_payload(self):
        try:
            return self._payload
        except AttributeError:
            try:
                parse = self._parse
                return parse(self._string)
            except AttributeError:
                return self._string

    @property
    def length_prefix(self):
        return int_to_big_endian(len(str(self.id)+self._inner_string))

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
        return self._parsed_payload[0]

class Bitfield(Message):
    '''Expects a bitfield as an init arg'''
    id = 5

    @property
    def bitfield(self):
        # dynamically calculate bitfield and return as list of booleans
        pass

class Request(Message):
    '''Expects index, begin, length as init args'''
    id = 6

    def _parse(self,m): 
        return [four_bytes_to_int(m[i:i+4]) for i in (0,4,8)]

    @property
    def index(self):
        return self._parsed_payload[0]

    @property
    def begin(self):
        return self._parsed_payload[1]

    @property
    def length(self):
        return self._parsed_payload[2]

class Piece(Message):
    '''Expects index, begin, block as init args'''
    id = 7

    def _parse(self,m):
        return [four_bytes_to_int(m[i:i+4]) for i in (0,4)]+[m[8:]]

    @property
    def index(self):
        return self._parsed_payload[0]

    @property
    def begin(self):
        return self._parsed_payload[1]

    @property
    def block(self):
        return self._parsed_payload[2]

class Cancel(Request): # employs same payload as Request
    '''Expects index, begin, length as init args'''
    id = 8

class Port(Message):
   '''Expects listen-port as an argument'''
   id = 9


id_to_constructor = {
        sc.id:sc.__init__ for sc in Message.__subclasses__()
        }
