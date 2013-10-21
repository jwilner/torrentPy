
class Peer():
    '''Class representing peer for specific torrent download'''

    def __init__(self,(ip,port),client,torrent):
        self.ip = ip
        self.port = port
        self.client = client
        self.torrent = torrent


