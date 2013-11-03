
class ExceptionManager():
    '''My way of controlling exception behavior when the call stack
    always resolves to the event loop'''

    def handle_exception(self,e,e_type=None):
        if e_type is None:
            e_type = type(e)

        try:
            self._exception_handlers[e_type](e)
        except KeyError:
            try:
                self._next_level.handle_exception(e,e_type=e_type)
            except AttributeError:
                raise e

class UnhandledSocketEvent(Exception):
    pass

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
