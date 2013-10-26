from utils import int_to_big_endian, prop_and_memo, four_bytes_to_int 

class InvalidMessage(Exception):
    pass

class InvalidHandshake(InvalidMessage):
    pass

class Msg(object):
    '''super class'''
    def __init__(self):
        self.observers = []

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

    def __repr__(self):
        return 'Handshake('+str(self)+')'

class Message(Msg):
    id = ''
    _payload = ''

    def __init__(self,*args):
        super(Message,self).__init__()
        self._payload = args 

    def __str__(self):
        return ''.join(str(x) for x in (self.length_prefix,self.id)) + self.payload       

    @prop_and_memo
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

class Bitfield(Message):
    '''Expects a bitfield as an init arg'''
    id = 5

class Request(Message):
    '''Expects index, begin, length as init args'''
    id = 6
          
class Piece(Message):
    '''Expects index, begin, block as init args'''
    id = 7

class Cancel(Message):
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

if __name__ == '__main__':
    import pprint, socket, main, torrent, torrent_requests, processes

    t = torrent.LiveTorrent('../../../Data/torrentPy/flagfromserver.torrent',main.BitTorrentClient())
    r = torrent_requests.send_started_announce_request(t)
    peers = [p for p in processes.make_peers(t,r['peers'])]
    h = Handshake(t.client.client_id,t.hashed_info)
    for peer in peers:
        if peer.ip == '74.212.183.186':
            continue 
        pprint.pprint(peer.address)
        s = socket.socket()
        s.connect(peer.address)
        s.send(str(h)) 
        handshake = gather_handshake_from_socket(s)
        gen = generate_messages_from_socket(s)
        messages = [handshake]
        while True:
            msg = next(gen)
            pprint.pprint(msg)
            messages.append(msg)


