
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

class MessageParsingError(Exception):
    pass

class MessageException(Exception):
    def __init__(self,**kwargs):
        text = kwargs.pop('message','')
        self.peer = kwargs.pop('peer')
        self.msg = kwargs.pop('msg') 
        super(MessageException,self).__init__(text)


class UnknownPeerHandshake(MessageException):
    pass

class FatallyFlawedIncomingMessage(MessageException):
    pass

class FatallyFlawedOutgoingMessage(MessageException):
    pass

class TorrentComplete(Exception):
    pass

class NoStrategyFound(Exception):
    pass
