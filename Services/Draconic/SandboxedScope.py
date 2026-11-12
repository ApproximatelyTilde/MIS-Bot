import collections.abc             as CollectionsABC
import json                            as JSONLibrary
import math                            as MathLibrary
import time                            as TimeLibrary
import types                           as TypesLibrary
import typing                          as Typing
import Services.Draconic.Exceptions    as Exceptions
import Services.DiceService            as DiceService

MAX_CONTAINER_SIZE: int = 50000

class DraconicList(list):
    def append(self, ObjectItem: Typing.Any) -> None:
        if (len(self) >= MAX_CONTAINER_SIZE):
            raise Exceptions.DraconicExecutionError("Container size limit exceeded")

        super().append(ObjectItem)

    def extend(self, IterableItems: Typing.Iterable[Typing.Any]) -> None:
        for Item in IterableItems:
            self.append(Item)

    def insert(self, IndexPosition: int, ObjectItem: Typing.Any) -> None:
        if (len(self) >= MAX_CONTAINER_SIZE):
            raise Exceptions.DraconicExecutionError("Container size limit exceeded")

        super().insert(IndexPosition, ObjectItem)

class DraconicDict(dict):
    def __getitem__(self, KeyValue: Typing.Any) -> Typing.Any:
        return super().__getitem__(KeyValue)

    def __setitem__(self, KeyValue: Typing.Any, ItemValue: Typing.Any) -> None:
        if (len(self) >= MAX_CONTAINER_SIZE) and (KeyValue not in self):
            raise Exceptions.DraconicExecutionError("Container size limit exceeded")

        super().__setitem__(KeyValue, ItemValue)

    def __getattr__(self, AttributeName: str) -> Typing.Any:
        if AttributeName.startswith("__"):
            raise Exceptions.DraconicSecurityError(f"Access to private attribute '{AttributeName}' is prohibited")

        if AttributeName in self:
            return self[AttributeName]

        raise AttributeError(f"'DraconicDict' object has no attribute '{AttributeName}'")

    def __setattr__(self, AttributeName: str, AttributeValue: Typing.Any) -> None:
        if AttributeName.startswith("__"):
            raise Exceptions.DraconicSecurityError(f"Access to private attribute '{AttributeName}' is prohibited")

        self[AttributeName] = AttributeValue

    def get(self, KeyValue: Typing.Any, DefaultValue: Typing.Any = None) -> Typing.Any:
        return super().get(KeyValue, DefaultValue)

class DraconicSet(set):
    def add(self, ElementItem: Typing.Any) -> None:
        if (len(self) >= MAX_CONTAINER_SIZE):
            raise Exceptions.DraconicExecutionError("Container size limit exceeded")

        super().add(ElementItem)

    def update(self, *Iterables: Typing.Iterable[Typing.Any]) -> None:
        for SingleIterable in Iterables:
            for Item in SingleIterable:
                self.add(Item)

def SafeLoadJSON(JSONStringText: str) -> Typing.Any:
    try:
        ParsedValue: Typing.Any = JSONLibrary.loads(JSONStringText)
        return WrapObjectInSafeProxy(ParsedValue)

    except Exception as ParseError:
        raise Exceptions.DraconicExecutionError(f"Failed to parse JSON: {str(ParseError)}")

def SafeDumpJSON(TargetObject: Typing.Any) -> str:
    try:
        CleanUnwrapped: Typing.Any = UnwrapSafeProxy(TargetObject)
        return JSONLibrary.dumps(CleanUnwrapped)

    except Exception as DumpError:
        raise Exceptions.DraconicExecutionError(f"Failed to dump JSON: {str(DumpError)}")

def SafeLoadYAML(YAMLStringText: str) -> Typing.Any:
    return SafeLoadJSON(YAMLStringText)

def SafeDumpYAML(TargetObject: Typing.Any) -> str:
    return SafeDumpJSON(TargetObject)

def SafeTime() -> float:
    return TimeLibrary.time()

def WrapObjectInSafeProxy(SourceTarget: Typing.Any) -> Typing.Any:
    if isinstance(SourceTarget, dict):
        ProxyDictionary: DraconicDict = DraconicDict()
        for DictionaryKey, DictionaryValue in SourceTarget.items():
            ProxyDictionary[DictionaryKey] = WrapObjectInSafeProxy(DictionaryValue)

        return ProxyDictionary

    if isinstance(SourceTarget, list):
        ProxyList: DraconicList = DraconicList()
        for ListItem in SourceTarget:
            ProxyList.append(WrapObjectInSafeProxy(ListItem))

        return ProxyList

    if isinstance(SourceTarget, set):
        ProxySet: DraconicSet = DraconicSet()
        for SetItem in SourceTarget:
            ProxySet.add(WrapObjectInSafeProxy(SetItem))

        return ProxySet

    return SourceTarget

def UnwrapSafeProxy(SourceTarget: Typing.Any) -> Typing.Any:
    if isinstance(SourceTarget, (DraconicDict, dict)):
        return {UnwrapSafeProxy(DictionaryKey): UnwrapSafeProxy(DictionaryValue) for DictionaryKey, DictionaryValue in SourceTarget.items()}

    if isinstance(SourceTarget, (DraconicList, list)):
        return [UnwrapSafeProxy(ListItem) for ListItem in SourceTarget]

    if isinstance(SourceTarget, (DraconicSet, set)):
        return {UnwrapSafeProxy(SetItem) for SetItem in SourceTarget}

    return SourceTarget

class VerboseRollResult(DraconicDict):
    def __str__(self) -> str:
        return str(self.get("result", ""))

class SafeBuiltinsFactory:
    def __init__(self, DiceRoller: Typing.Optional[DiceService.DiceRollerService] = None) -> None:
        self.DiceRoller: DiceService.DiceRollerService = DiceRoller if (DiceRoller is not None) else DiceService.DiceRollerService()

    def Roll(self, ExpressionString: str) -> int:
        RollOutcome: DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(ExpressionString)
        return RollOutcome.Total

    def VerboseRoll(self, ExpressionString: str) -> VerboseRollResult:
        RollOutcome: DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(ExpressionString)
        ResultDictionary: VerboseRollResult  = VerboseRollResult()
        ResultDictionary["total"]            = RollOutcome.Total
        ResultDictionary["result"]           = RollOutcome.FormattedString
        ResultDictionary["dice"]             = RollOutcome.Breakdown
        ResultDictionary["consolidated"]     = RollOutcome.FormattedString
        ResultDictionary["raw"]              = RollOutcome.RawInput
        return ResultDictionary

    def BuildBaseScope(self) -> dict[str, Typing.Any]:
        BaseScopeMap: dict[str, Typing.Any] = {
            "roll"      : self.Roll,
            "vroll"     : self.VerboseRoll,
            "floor"     : MathLibrary.floor,
            "ceil"      : MathLibrary.ceil,
            "round"     : round,
            "abs"       : abs,
            "min"       : min,
            "max"       : max,
            "sum"       : sum,
            "sqrt"      : MathLibrary.sqrt,
            "len"       : len,
            "range"     : range,
            "enumerate" : enumerate,
            "zip"       : zip,
            "reversed"  : reversed,
            "sorted"    : sorted,
            "any"       : any,
            "all"       : all,
            "str"       : str,
            "int"       : int,
            "float"     : float,
            "bool"      : bool,
            "list"      : DraconicList,
            "dict"      : DraconicDict,
            "set"       : DraconicSet,
            "tuple"            : tuple,
            "Exception"        : Exception,
            "ValueError"       : ValueError,
            "TypeError"        : TypeError,
            "KeyError"         : KeyError,
            "IndexError"       : IndexError,
            "ZeroDivisionError": ZeroDivisionError,
            "AttributeError"   : AttributeError,
            "NameError"        : NameError,
            "load_json"        : SafeLoadJSON,
            "dump_json" : SafeDumpJSON,
            "load_yaml" : SafeLoadYAML,
            "dump_yaml" : SafeDumpYAML,
            "time"      : SafeTime
        }
        return BaseScopeMap
