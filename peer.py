import messages
from collections import deque
from strategy import strategies

class Peer():
    '''Class representing peer for specific torrent download and
    providing interface with specific TCP socket'''

    def __inif__(self,socket,client,torrent=None):
        self.ip, self.port = socket.getsockname()
        self.address = self.ip, self.port 
        self.client = client
        self.torrent = torrent
        self._handshake = {'sent': False, 'received': False } 

        self.outbox = deque() 
        self.sent_folder, self.archive = [], []

        self.socket_handlers = {
            'read' : self.parse_message, 
            'write': self.process_outbox,
            'error': self.handle_socket_error
            }

        self.message_handlers = {
            sc : strategies[sc] for sc in messages.Msg.__subclasses__() 
                }

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        return '<Peer for {0!s} at {1!s}:{2!s}>'.format(
                self.torrent, self.ip, self.port)

    def _set_socket(self,s):
        self._socket = s

    def _get_socket(self):
        return self._socket

    def _del_socket(self):
        self._socket = None

    socket = property(_get_socket,_set_socket,_del_socket)

    def send_handshake(self):
        handshake = messages.Handshake(
                        self.client.client_id,
                        self.torrent.hashed_info)
        handshake.observers.append()
        self.outbox.append(handshake)

    def register_handshake(self,msg,sent):
        self._handshake['sent'] = sent

    def connect(self):
        self.client.register(self.socket,self.socket_handlers)
        self.socket.connect(self.address)

        self._handshook

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

    def parse_message(self):
        if self._handshook['received']:
            msg = messages.gather_message_from_socket(self.socket) 
        else:
            # InvalidHandshakeException can bubble through here.
            msg = messages.gather_handshake_from_socket(self.socket)

        self.archive.append(msg)
        self.message_handlers[type(msg)](msg)

    def handle_socket_error(self):
        pass

