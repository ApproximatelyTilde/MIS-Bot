import typing                         as Typing
import Services.DebugService          as Debug
import Services.PlatformClient        as PlatformClient
import Services.Draconic.Exceptions   as Exceptions

class CustomCounterManager:
    def __init__(self, CharacterRecord: dict[str, Typing.Any], PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.CharacterRecord       : dict[str, Typing.Any]            = CharacterRecord
        self.PlatformClient        : PlatformClient.MISPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
        self.DetailData            : dict[str, Typing.Any]            = CharacterRecord.setdefault("DetailData", {})
        self.CustomCounters        : dict[str, dict[str, Typing.Any]] = self.DetailData.setdefault("CustomCounters", {})
        self.Variables             : dict[str, Typing.Any]            = self.DetailData.setdefault("Variables", {})

    def GetCharacterID(self) -> str:
        return str(self.CharacterRecord.get("ID", ""))

    def CounterExists(self, CounterName: str) -> bool:
        return (CounterName in self.CustomCounters)

    def CreateCounter(self, CounterName: str, MinValue: Typing.Optional[int] = 0, MaxValue: Typing.Optional[int] = None, ResetTo: Typing.Optional[int] = None, ResetOn: str = "LongRest", Description: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        InitialValue: int = MaxValue if (MaxValue is not None) else (MinValue if (MinValue is not None) else 0)
        CounterPayload: dict[str, Typing.Any] = {
            "Name"         : CounterName,
            "Value"        : InitialValue,
            "MaxValue"     : MaxValue,
            "MinValue"     : MinValue,
            "ResetSchedule": ResetOn,
            "Description"  : Description
        }
        self.CustomCounters[CounterName] = {
            "Value"        : InitialValue,
            "MaxValue"     : MaxValue,
            "MinValue"     : MinValue,
            "ResetSchedule": ResetOn,
            "Description"  : Description
        }
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Counter: Name=\"{CounterName}\", Value={InitialValue}")
        return self.CustomCounters[CounterName]

    def DeleteCounter(self, CounterName: str) -> bool:
        if CounterName in self.CustomCounters:
            del self.CustomCounters[CounterName]
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Counter: Name=\"{CounterName}\"")
            return True

        return False

    def GetCounter(self, CounterName: str) -> int:
        if CounterName in self.CustomCounters:
            return int(self.CustomCounters[CounterName].get("Value", 0))

        raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

    def GetCounterMax(self, CounterName: str) -> Typing.Optional[int]:
        if CounterName in self.CustomCounters:
            return self.CustomCounters[CounterName].get("MaxValue")

        raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

    def GetCounterMin(self, CounterName: str) -> Typing.Optional[int]:
        if CounterName in self.CustomCounters:
            return self.CustomCounters[CounterName].get("MinValue")

        raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

    def ModifyCounter(self, CounterName: str, DeltaValue: int, StrictMode: bool = False) -> int:
        if CounterName not in self.CustomCounters:
            raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

        CounterData: dict[str, Typing.Any] = self.CustomCounters[CounterName]
        CurrentValue: int                  = int(CounterData.get("Value", 0))
        NewValue    : int                  = CurrentValue + DeltaValue

        MinValue: Typing.Optional[int] = CounterData.get("MinValue")
        MaxValue: Typing.Optional[int] = CounterData.get("MaxValue")

        if StrictMode:
            if (MinValue is not None) and (NewValue < MinValue):
                raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' cannot fall below minimum value {MinValue}")

            if (MaxValue is not None) and (NewValue > MaxValue):
                raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' cannot exceed maximum value {MaxValue}")

        if (MinValue is not None) and (NewValue < MinValue):
            NewValue = MinValue

        if (MaxValue is not None) and (NewValue > MaxValue):
            NewValue = MaxValue

        CounterData["Value"] = NewValue
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Modified Counter: Name=\"{CounterName}\", Value={NewValue}")
        return NewValue

    def SetCounter(self, CounterName: str, NewValue: int, StrictMode: bool = False) -> int:
        if CounterName not in self.CustomCounters:
            raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

        CounterData: dict[str, Typing.Any] = self.CustomCounters[CounterName]
        MinValue   : Typing.Optional[int]  = CounterData.get("MinValue")
        MaxValue   : Typing.Optional[int]  = CounterData.get("MaxValue")

        if StrictMode:
            if (MinValue is not None) and (NewValue < MinValue):
                raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' cannot fall below minimum value {MinValue}")

            if (MaxValue is not None) and (NewValue > MaxValue):
                raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' cannot exceed maximum value {MaxValue}")

        if (MinValue is not None) and (NewValue < MinValue):
            NewValue = MinValue

        if (MaxValue is not None) and (NewValue > MaxValue):
            NewValue = MaxValue

        CounterData["Value"] = NewValue
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Set Counter: Name=\"{CounterName}\", Value={NewValue}")
        return NewValue

    def ResetCounter(self, CounterName: str) -> int:
        if CounterName not in self.CustomCounters:
            raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

        CounterData: dict[str, Typing.Any] = self.CustomCounters[CounterName]
        MaxValue   : Typing.Optional[int]  = CounterData.get("MaxValue")
        MinValue   : Typing.Optional[int]  = CounterData.get("MinValue")

        ResetValue: int      = MaxValue if (MaxValue is not None) else (MinValue if (MinValue is not None) else 0)
        CounterData["Value"] = ResetValue
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Reset Counter: Name=\"{CounterName}\", Value={ResetValue}")
        return ResetValue

    def GetVariable(self, VariableName: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        return self.Variables.get(VariableName, DefaultValue)

    def SetVariable(self, VariableName: str, VariableValue: Typing.Any) -> None:
        self.Variables[VariableName] = VariableValue
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Set Variable: Name=\"{VariableName}\", Value={VariableValue}")

    def DeleteVariable(self, VariableName: str) -> bool:
        if VariableName in self.Variables:
            del self.Variables[VariableName]
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deleted Variable: Name=\"{VariableName}\"")
            return True

        return False

