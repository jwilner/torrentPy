from utils import memo
import os, torrent_exceptions

@memo
def safe_filename(filename):
    new_filename = ''.join(c for c in filename 
                                if c.isalpha() or c.isdigit() or c == ' ')
    return new_filename.replace(' ','_')

class FileHandler(object):
    '''A class for handling file operations within the torrent. Takes files,
     a list of dictionaries of length and path, and a list of piece lengths.'''

    def __init__(self,name,files,piece_lengths,dirname=None):
        self._files = [] 
        self._piece_lengths = piece_lengths
        self._piece_length = self._piece_lengths[0]

        start_name = os.splitext(name) if dirname is None else dirname

        directory = test_name = safe_filename(start_name)

        i = 1
        while os.path.exists(test_name): 
            test_name = directory+'({0})'.format(i)
            i += 1

        self._directory = test_name+'/'
        os.mkdir(self._directory)

        start_in_bytes = 0     
        for f in files:
            full_path = os.path.join(self._directory,*f['path'])
            dir_path = os.path.dirname(full_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
            f.open(full_path,mode='w').close()
            end = start_in_bytes + int(f['length'])
            self._files.append((start_in_bytes,end,full_path)) 
            start_in_bytes = end

    def write(self,piece,offset,value):
        pass

    def read(self,piece,offset,length):
        pass

    def _map_block_to_files(self,piece,offset,length):
        block_start = piece * self._piece_length + offset
        block_end = block_start + length

        files_wanted = []
        iterfiles = iter(self._files)
        while True:
            file_start,file_end,file_path = next(iterfiles)
            if file_start <= block_start: 
                files_wanted.append((block_start-file_start,file_path))
                while True:
                    if file_start >= block_end: 
                        break
                    files_wanted.append((0,file_path))
                break
        return files_wanted 
