import os
import io
import itertools


def safe_filename(name):
    return name


class FileHandler(object):
    '''A class for handling file operations within the torrent. Takes files,
     a list of dictionaries of length and path,  and a list of piece lengths.
     The basic idea is to break all reads and writes into the common
     denominator of bytes'''

    def __init__(self, name, files, piece_lengths, dirname=None):

        start_name = os.splitext(name) if dirname is None else dirname
        directory = test_name = safe_filename(start_name)

        i = 1
        while os.path.exists(test_name):
            test_name = directory+'({})'.format(i)
            i += 1

        self._directory = test_name+'/'
        os.mkdir(self._directory)

        self._files = {}
        start_in_bytes = 0

        for f in files:
            full_path = \
                os.path.join(self._directory, *f['path']).replace(' ', '_')
            dir_path = os.path.dirname(full_path)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

            f.open(full_path, mode='w').close()

            end_in_bytes = start_in_bytes + int(f['length'])
            self._files[start_in_bytes, end_in_bytes] = full_path

            start_in_bytes = end_in_bytes

        self._piece_starts = [sum(p_l for p_l in piece_lengths[:i])
                              for i in range(len(piece_lengths))]

        self._piece_length = piece_lengths[0]

    def write(self, piece, offset, value):
        stream = io.BytesIO(value)
        for f_path, s_point, length in self._block_to_files(piece, offset,
                                                            len(value)):
            with io.open(f_path, mode='ab') as f:
                f.seek(s_point)
                f.write(stream.read(length))

        self._is_piece_complete(piece)

    def read(self, piece, offset, length):
        '''Takes piece coordinates and returns chained together bytearrays'''
        return itertools.chain.from_iterable(
            self._read_helper(file_path, seek_point, read_amount)
            for file_path, seek_point, read_amount
            in self._block_to_files(piece, offset, length))

    def _read_helper(self, file_path, seek_point, amount):
        with io.open(file_path, mode='rb') as f:
            f.seek(seek_point)
            return f.read(amount)

    def _block_to_files(self, piece_index, offset, block_length):
        '''Takes a piece index,  an offset,  and a length; yields triples
        offset filename,  seek_point,  and length.'''

        block_start = self._piece_starts[piece_index] + offset
        block_end = block_start + block_length

        files = ((file_path, file_start, file_end)
                 for file_start, file_end, file_path in self._files.items()
                 if file_start <= block_start and file_end >= block_end)

        for file_path, file_start, file_end in files:
            seek = block_start - file_start
            remaining_length = block_end - file_end
            end = (file_end if remaining_length else block_end) - file_start
            yield (file_path, seek, end)
            block_start,  block_length = file_end,  remaining_length
