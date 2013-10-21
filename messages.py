from utils import string_to_byte 

class Handshake():
    def __init__(self,peer_id,info_hash):
        self._peer_id = peer_id
        self._info_hash = info_hash
        self._reserved = "\x00"*8
        self._pstr = 'BitTorrent Protocol'
        self._pstrlen = chr(len(self._pstr))

    def __str__(self):
        return self._pstrlen + self._pstr + self._reserved + self._info_hash + self._peer_id

class Message():
    def __init__(self,*payload):
        self._payload = payload

    def __str__():
        
