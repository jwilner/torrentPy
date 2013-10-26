import messages
from collections import deque
from strategy import strategies

class SocketManager(object):
    '''Super class for managing an individual socket'''

    def __init__(self,socket):
        self.ip, self.port = socket.getsockname()
        self.socket = socket
        self.address = self.ip, self.port 

        self.outbox = deque() 
        self.sent_folder, self.archive = [], []

        self.socket_handlers = {
            'read' : self.parse_message, 
            'write': self.process_outbox,
            'error': self.handle_socket_error
            }

        self.client.register(self.socket,self.socket_handlers)

    def parse_message(self):
        pass

    def send_message(self,msg):
        self.socket.sendall(str(msg))
        self.sent_folder.append(msg)

        # notify any observers
        for observer in msg.observers:
            observer(msg,True)

    def process_outbox(self):
        try:
            msg = self.outbox.popleft()
            self.send_message(msg)
        except IndexError: #queue empty
            pass

    def handle_socket_error(self):
        pass

class Peer(SocketManager):
    '''Class representing peer for specific torrent download and
    providing interface with specific TCP socket'''

    def __init__(self,socket,client,torrent=None):
        super(Peer,self).__init__()
        self._handshake = {'sent': False, 'received': False } 
        self.client = client
        self.torrent = torrent
        self.message_handlers = {
            sc : strategies[sc] for sc in messages.Msg.__subclasses__() 
                }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<Peer for {0!s} at {1!s}:{2!s}>'.format(
                self.torrent, self.ip, self.port)


    def send_handshake(self):
        handshake = messages.Handshake(
                        self.client.client_id,
                        self.torrent.hashed_info)
        handshake.observers.append()
        self.outbox.append(handshake)

    def register_handshake(self,msg,sent):
        self._handshake['sent'] = sent

def parse_message(self):
        if self._handshook['received']:
            msg = messages.gather_message_from_socket(self.socket) 
        else:
            # InvalidHandshakeException can bubble through here.
            msg = messages.gather_handshake_from_socket(self.socket)

        self.archive.append(msg)
        self.message_handlers[type(msg)](msg)


