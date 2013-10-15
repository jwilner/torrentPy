
# Types:
# Byte Strings
# Integers
# Lists
# Dictionaries

class BencodeParser():
    '''Takes a string and returns a list of tuples'''

    _end_struct = 'END'

    def __init__(self,ioString):
        self._stream = ioString
        self._rules = (
                (lambda x: x in '0123456789', self._parse_string),
                (lambda x: x == 'i', self._parse_int),
                (lambda x: x == 'd', lambda x : self._dict_constructor),
                (lambda x: x == 'l', lambda x : self._list_constructor),
                (lambda x: x == 'e', lambda x : self._end_struct)
                )
   
    def parse_and_build(self):
        self._token = self._token_generator()
        return next(self._token)() 

    def _dict_constructor(self):
        new_dict = {}
        while True:
            k = next(self._token)
            if k == self._end_struct:
                return new_dict
            new_dict[k()] = next(self._token)()

    def _list_constructor(self):
        new_list = []
        while True:
           item = next(self._token)
           if item == self._end_struct:
               return new_list
           new_list.append(item())

    def _token_generator(self):
        while True:
            char = self._stream.read(1)
            if char == '':
                raise StopIteration
            for rule,method in self._rules:
                if rule(char): 
                    yield method(char)
    
    def _parse_string(self,x):
        while True:
            next_char = self._stream.read(1)
            if next_char == ':':
                break
            x += next_char
        length = int(x)
        word = self._stream.read(length)
        return lambda : word

    def _parse_int(self,x):
        integer = ''
        while True:
            next_char = self._stream.read(1)
            if next_char == 'e':
                break
            integer += next_char
        return lambda : int(integer)


if __name__ == '__main__':
    import io,sys
    with io.open(sys.argv[1],'rb') as f:
        t = BencodeParser(f)
        print t.parse_and_build()
