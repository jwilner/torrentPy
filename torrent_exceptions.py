
class DoNotSendException(Exception):
    pass

class LeftoverException(Exception):
    def __init__(self,message='',value=None):
        self.leftover = value
        super(LeftoverException,self).__init__(message)

class RanDryException(Exception):
    def __init__(self,message='',value=None):
        self.unused = value
        super(RanDryException,self).__init__(message)

class InvalidMessageError(Exception):
    pass

class FatallyFlawedMessage(Exception):
    def __init__(self,**kwargs):
        text = kwargs.pop('message','')
        self.peer = kwargs.pop('peer')
        self.msg = kwargs.pop('msg') 
        super(FatallyFlawedMessage,self).__init__(text)


class TorrentComplete(Exception):
    pass

class NoStrategyFound(Exception):
    pass
