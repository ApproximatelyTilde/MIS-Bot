import typing as Typing

class DraconicException(Exception):
    pass

class DraconicSecurityError(DraconicException):
    pass

class DraconicExecutionError(DraconicException):
    pass

class DraconicTimeoutError(DraconicException):
    pass

class DraconicSyntaxError(DraconicException):
    pass

class ReturnSignal(Exception):
    def __init__(self, ReturnValue: Typing.Any = None) -> None:
        self.ReturnValue: Typing.Any = ReturnValue
        super().__init__()

class BreakSignal(Exception):
    pass

class ContinueSignal(Exception):
    pass

