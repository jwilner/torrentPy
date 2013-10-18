import io,datetime,functools

class Torrent():
    '''Wrapper for torrent metadata file'''

    def __init__(self,filename):
        '''Opens file with context manager'''
        with io.open(filename,'rb') as f:
            parser = BencodeParser(f)
            self._data = parser.parse()
        self._cache = {}

    @property
    def announce(self):
        '''This is an obligatory item in the dictionary -- if it's not here,
        da fuck we doin'? Like other query wrappers, an IndexError can pass
        through.'''
        return self.query('announce')

    @property
    def pieces(self):
        '''Returns a list of the hash codes for each piece, divided by length 
        20'''
        try:
            return self._pieces
        except AttributeError:
            try:
                pieces = self.query('pieces')
                self._pieces = [pieces[i:i+20] for i in range(0,len(pieces),20)]
            except KeyError:
                # does there need to be a more dramatic exception here? If no 
                # pieces are found, that means something is seriously wrong, no?
                self._pieces = []
            return self._pieces

    @property
    def announce_list(self):
        '''N.B. each item here seems to be encased in a list by default. Again,'''
        try:
            return self._announce_list
        except AttributeError:
            try:
                self._announce_list = self.query('announce-list')
            except KeyError:
                self._announce_list = []
            return self._announce_list

    @property
    def creation_date(self):
        '''Returns a date object; else an KeyError bubbles through'''
        try:
            return self._creation_date
        except AttributeError:
            try:
                self._creation_date = datetime.date.fromtimestamp(self.query('creation date'))
            except TypeError:
                raise KeyError('Creation date not found in torrent data')
            return self._creation_date

    def query(self,key):
        '''This is the public, cached method for accessing data in the torrent
        file. If data isn't found, a KeyError will bubble through here.'''
        try:
            return self._cache[key]
        except KeyError: # this only handles a key not found in the CACHE
            # a key error can still very much rise up from here
            self._cache[key] = self._traverseTree(key,self._data)
        return self._cache[key]

    def _traverseTree(self,key,tree):
        '''Recursive method searching the structure of the tree, will raise
        an index error if nothing is found.'''
        for k,v in tree.items():
            if k == key:
                return v 
            if type(v) == dict:
                try:
                    return self._traverseTree(key,v)
                except KeyError:
                    continue
        else:
            # this pattern ensures that an IndexError is only raised if the 
            # key isn't found at ANY level of recursion
            raise KeyError(key+' not found in torrent data.')

class BencodeParser():
    '''Takes a bencoded file and returns the dictionary encoded within.'''
    _end_struct = 'END' #

    def __init__(self,ioString):
        '''
        Requires a stream providing a read method that can return one or more
        characters at a time. If the file ISN'T properly bencoded, this will 
        halt and catch fire quickly.
        '''
        #providing access to file stream to all methods
        self._stream = ioString

        self._rules_methods = {k: functools.partial(self._parse_string,k) for k in '0123456789'}
        self._rules_methods.update({
            'd':  self._dict_constructor,
            'l':  self._list_constructor,
            'e':  self._end_struct,
            'i':  self._parse_int
            })
   
    def parse(self):
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
            yield self._rules_methods[char] #parse method returning function
 
    def _dict_constructor(self):
        '''Opens dictionary and gathers stream in it 'til it hits end_struct'''
        new_dict = {}
        while True: # breaks on return
            k = next(self._token)
            if k == self._end_struct:
                return new_dict
            key = k()
            new_dict[key] = next(self._token)() # *see below block comment

    def _list_constructor(self):
        '''Opens list and gathers stream in it 'til it hits end_struct'''
        new_list = []
        while True:
           item = next(self._token)
           if item == self._end_struct:
               return new_list
           new_list.append(item()) # *see below block comment
   
    def _parse_string(self,x):
        '''Parses string'''
        while True:
            next_char = self._stream.read(1)
            if next_char == ':':
                break
            x += next_char
        length = int(x)
        return self._stream.read(length)

    def _parse_int(self):
        '''Parses int'''
        integer = ''
        while True:
            next_char = self._stream.read(1)
            if next_char == 'e':
                break
            integer += next_char
        return int(integer)

# a version that avoids recursion, for shits n' giggles and those times when
# when your torrent file has thousands of nested directories.

class BencodeParserNonRecursive():
    def __init__(self,stream):
        self._stream, self._done = stream, None
        self._holding, self._int_buffer = [], ''
        self._rules_methods = {
            ':': self._parse_string,
            'd': functools.partial(
                    self._add_new_level,
                    lambda x: dict((x[y],x[y+1]) for y in range(len(x)) if y % 2 == 0)),
            'l': functools.partial(self._add_new_level,list),
            'e': self._close_level,
            'i': functools.partial(self._add_new_level,
                                    lambda x: ''.join(self._get_int_buffer()))
            }
        
    def parse(self):
        while not self._done:
            next_char = self._stream.read(1)
            try:
                self._rules_methods[next_char]()
            except KeyError:
                self._int_buffer += next_char 
        return self._done

    def _get_int_buffer(self):
        buff = self._int_buffer
        self._int_buffer = ''
        return buff

    def _parse_string(self):
        cur = self._stream.read(int(self._int_buffer))
        self._current.append(cur)
        self._int_buffer = ''
    
    def _add_new_level(self,lev_func):
        try:
            self._holding.append(self._current)
        except AttributeError:
            self._current = []
        self._current = [lev_func]
        
    def _close_level(self):
        new_struct = self._current[0](self._current[1:])
        try:
            self._current = self._holding.pop()
            self._current.append(new_struct)
        except IndexError: #index error is raised when holding is empty which means we're done
            self._done = new_struct
 
if __name__ == '__main__':
    import sys,pprint
    try:
        filename = sys.argv[1]
    except IndexError:
        filename = 'pretend_file.txt'

    with io.open(filename,'rb') as f:
        t = BencodeParser(f)
        pprint.pprint(t.parse())

