import requests
from io import BytesIO
from utils import debencode

def send_started_announce_request(tor):
    print tor.announce_url_query_string
    r = requests.get(tor.announce_url_query_string)
    r.raise_for_status()
    print len(r.content)
    return debencode(BytesIO(r.content))

def get_torrent_scrape(tor):
    '''Takes a torrent and returns a dictionary of data'''
    r = requests.get(tor.scrape_url,data={'info_hash':tor.hashed_info})
    r.raise_for_status()
    return debencode(BytesIO(r.content))
