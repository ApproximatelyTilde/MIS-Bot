import typing as Typing

class DraconicException(Exception):
    def __init__(self, Message: str = "") -> None:
        super().__init__(Message)

class DraconicSecurityError(DraconicException):
    def __init__(self, Message: str = "") -> None:
        super().__init__(Message)

class DraconicExecutionError(DraconicException):
    def __init__(self, Message: str = "") -> None:
        super().__init__(Message)

class DraconicTimeoutError(DraconicException):
    def __init__(self, Message: str = "") -> None:
        super().__init__(Message)

class DraconicSyntaxError(DraconicException):
    def __init__(self, Message: str = "") -> None:
        super().__init__(Message)

class ReturnSignal(Exception):
    def __init__(self, ReturnValue: Typing.Any = None) -> None:
        self.ReturnValue: Typing.Any = ReturnValue
        super().__init__()

class BreakSignal(Exception):
    def __init__(self) -> None:
        super().__init__()

class ContinueSignal(Exception):
    def __init__(self) -> None:
        super().__init__()

