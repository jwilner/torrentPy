
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
