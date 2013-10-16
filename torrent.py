import io

class Torrent():
    '''Wrapper for torrent metadata file'''
    def __init__(self,filename):
        '''Opens file with context manager'''
        with io.open(filename,'rb') as f:
            parser = BencodeParser(f)
            self._data = parser.parse_and_build()
        self._cache = {}

    @property
    def announce(self):
        return self.query('announce')

    @property
    def pieces(self):
        pieces = self.query('pieces')
        return [pieces[i:i+20] for i in range(0,len(pieces),20)]

    def query(self,key):
        try:
            return self._cache[key]
        except KeyError: 
            self._cache[key] = self._traverseTree(key,self._data)
        return self._cache[key]

    def _traverseTree(self,key,tree):
        for k,v in tree.items():
            if k == key:
                return v 
            if type(v) == dict:
                try:
                    return self._traverseTree(key,v)
                except IndexError:
                    continue
        else:
            raise IndexError(key+' not found in torrent data.')


class BencodeParser():
    '''Takes a bencoded file and returns the dictionary encoded within.'''

    _end_struct = 'END' #

    def __init__(self,ioString):
        '''
        Requires a stream providing a read method that can return one or more
        characters at a time. If the file ISN'T properly bencoded, this will 
        halt and catch fire pretty quickly.
        '''
        #providing access to file stream to all methods
        self._stream = ioString

        # list of lambda rules and the method to be called when rule == true
        self._rules_methods = [
                (lambda x: x in '0123456789', self._parse_string),
                (lambda x: x == 'i', self._parse_int),
                # some of these are lambdas returning other methods
                # this allows the function call to be delayed 'til we're at 
                # the right point in the construction process
                (lambda x: x == 'd', lambda x : self._dict_constructor),
                (lambda x: x == 'l', lambda x : self._list_constructor),
                (lambda x: x == 'e', lambda x : self._end_struct)
                ]
   
    def parse_and_build(self):
        '''Main interface'''
        #instantiate generator
        self._token = self._token_generator()

        #just pull and evaluate first token, and the others follow recursively.
        return next(self._token)() 

    def _token_generator(self):
        '''Defines generator object providing stream of functions'''
        while True: #breaks on StopIteration below
            char = self._stream.read(1)
            if char == '': # io type returns empty string on exhausted file
                raise StopIteration
            for rule,method in self._rules_methods:
                if rule(char): 
                    yield method(char) #parse method returning function
 
    def _dict_constructor(self):
        '''Opens dictionary and gathers stream in it 'til it hits end_struct'''
        new_dict = {}
        while True: # breaks on return
            k = next(self._token)
            if k == self._end_struct:
                return new_dict
            new_dict[k()] = next(self._token)()

    def _list_constructor(self):
        '''Opens list and gathers stream in it 'til it hits end_struct'''
        new_list = []
        while True:
           item = next(self._token)
           if item == self._end_struct:
               return new_list
           new_list.append(item())
   
    # the remaining two methods deal with parsing the scalar values in the file,
    # but the values are returned wrapped in a lambda to provide homogeneity
    # in the later control flow (i.e. we never have to if-test as a result)
    def _parse_string(self,x):
        '''Parses string and returns it within closure'''
        while True:
            next_char = self._stream.read(1)
            if next_char == ':':
                break
            x += next_char
        length = int(x)
        word = self._stream.read(length)
        return lambda : word

    def _parse_int(self,x):
        '''Parses int and returns it within closure'''
        integer = ''
        while True:
            next_char = self._stream.read(1)
            if next_char == 'e':
                break
            integer += next_char
        return lambda : int(integer)

if __name__ == '__main__':
    import io,sys,pprint
    try:
        filename = sys.argv[1]
    except IndexError:
        filename = 'pretend_file.txt'

    with io.open(filename,'rb') as f:
        t = BencodeParser(f)
        pprint.pprint(t.parse_and_build())
