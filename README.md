#torrentPy

An exploration of the BitTorrent protocol in Python, using just select to handle the sockets. The only non-standard dependencies are the bitarray package, Requests, and a plugin to make Requests nonblocking.

This is very much currently a WIP as major parts are being refactored. Do not expect it to work at the moment!

##run
```shell
$ pip install requirements.txt

$ python main.py <torrent-file>
```
