from functools import partial
import struct, torrent_exceptions, io

def memo(f):
    cache = {}
    def g(*args):
        try:
            return cache[args]
        except KeyError:
            cache[args] = f(*args)
            return cache[args]
    return g

def prop_and_memo(f):
    return property(memo(f))

def bencode(whole):
    '''Takes a data structure and bencodes it'''

    def encode_int(integer):
        return 'i{0!s}e'.format(integer) 

    def encode_str(string):
        return '{0!s}:{1}'.format(len(string),string)

    def encode_list(a_list):
        return 'l{0}e'.format(''.join(parse(term) for term in a_list))

    def encode_dict(a_dict):
        return 'd{0}e'.format(''.join('{0}{1}'.format(parse(k),parse(v)) for k,v in sorted(a_dict.items())))

    dispatch = {int : encode_int,
                str : encode_str,
                list : encode_list,
                dict : encode_dict}
    
    def parse(structure):
        return dispatch[type(structure)](structure)

    return parse(whole)

def debencode(stream):
    ''' A bencoding parser that avoids recursion for s's and g's'''

    holding, int_buffer, current = [], [], []

    def parse_string(current,int_buffer):
        length = int(''.join(int_buffer)) # int buffer holds length
        current.append(stream.read(length))
        return current
    
    def open_level(lev_func,current,int_buffer):
        if current:
            holding.append(current)
        return [lev_func] # new current with function in first position
        
    def close_level(current,int_buffer):
        current += int_buffer # if int buffer has stuff in it at this point, this is an int
        new_struct = current[0](current[1:]) # call func stored in first pos
        try:
            current = holding.pop()
            current.append(new_struct)
            return current
        except IndexError: #index error is raised when holding is empty which means we're done
            return new_struct 

    dispatch = {':': parse_string,
                'd': partial(open_level,lambda x: dict((x[y],x[y+1]) for y in range(len(x)) if y % 2 == 0)),
                'l': partial(open_level,list),
                'e': close_level,
                'i': partial(open_level,lambda x: int(''.join(x)))}

    while True: 
        next_char = stream.read(1)
        try:
            current = dispatch[next_char](current,int_buffer)
            int_buffer = []
        except KeyError: #if key not in dispatch, must be int or empty string
            if next_char == '':
                return current
            int_buffer.append(next_char) 

def four_bytes_to_int(four_bytes):
    return struct.unpack('>i',four_bytes)[0]

def int_to_big_endian(integer):
    return struct.pack('>i',integer)

def parse_peer_string(p_string):
    peers = []
    for p in (p_string[i:i+6] for i in range(0,len(p_string),6)):
        ip = '.'.join(str(ord(ip_part)) for ip_part in p[:4])
        port = 256*(ord(p[4]))+ord(p[5])
        peers.append((ip,port))
    return peers

class StreamReader(io.BytesIO):
    def read(self,n=None):
        text = super(StreamReader,self).read(n) 
        if n and len(text) != n:
            raise torrent_exceptions.RanDryException(value=text)
        return text

if __name__ == '__main__':
    import sys,pprint,io
    try:
        filename = sys.argv[1]
    except IndexError:
        filename = 'pretend_file.txt'

    with io.open(filename,'rb') as f:
        structure = debencode(f)
    pprint.pprint(structure)


