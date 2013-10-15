
# Types:
# Byte Strings
# Integers
# Lists
# Dictionaries

class Tokenizer():
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
    
    def _dict_constructor():
        pass

    def _list_constructor():
        pass

    def _get_token(self):
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
        return self._stream.read(length)

    def _parse_int(self,x):
        integer = ''
        while True:
            next_char = self._stream.read(1)
            if next_char == 'e':
                break
            integer += next_char
        return int(integer)


if __name__ == '__main__':
    import io
    with io.open('pretend_file.txt','rb') as f:
        t = Tokenizer(f)
        print [p for p in t._get_token()]

