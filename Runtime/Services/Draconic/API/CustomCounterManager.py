import typing                               as Typing
import Runtime.Services.DebugService        as Debug
import Runtime.Services.PlatformClient      as PlatformClient
import Runtime.Services.Draconic.Exceptions as Exceptions

COUNTER_DISPLAY_SHAPES: dict[str, tuple[str, str]] = {
    "circle": ("●", "○"),
    "square": ("■", "□"),
    "hex"   : ("⬢", "⬡"),
    "star"  : ("★", "☆")
}
VALID_DISPLAY_STYLES: tuple[str, ...] = ("number", "circle", "square", "hex", "star")

class CustomCounterManager:
    def __init__(self, CharacterRecord: dict[str, Typing.Any], PlatformClientInstance: Typing.Optional[PlatformClient.TallyPlatformClient] = None) -> None:
        self.CharacterRecord       : dict[str, Typing.Any]            = CharacterRecord
        self.PlatformClient        : PlatformClient.TallyPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.TallyPlatformClient()
        self.DetailData            : dict[str, Typing.Any]            = CharacterRecord.setdefault("DetailData", {})
        self.CustomCounters        : dict[str, dict[str, Typing.Any]] = self.DetailData.setdefault("CustomCounters", {})
        self.Variables             : dict[str, Typing.Any]            = self.DetailData.setdefault("Variables", {})

    def GetCharacterID(self) -> str:
        return str(self.CharacterRecord.get("ID", ""))

    def CounterExists(self, CounterName: str) -> bool:
        return (CounterName in self.CustomCounters)

    def CreateCounter(self, CounterName: str, MinValue: Typing.Optional[int] = 0, MaxValue: Typing.Optional[int] = None, ResetTo: Typing.Optional[int] = None, ResetOn: str = "LongRest", Description: Typing.Optional[str] = None, DisplayStyle: Typing.Optional[str] = None) -> dict[str, Typing.Any]:
        InitialValue: int                  = MaxValue if (MaxValue is not None) else (MinValue if (MinValue is not None) else 0)
        CleanStyle  : Typing.Optional[str] = DisplayStyle.strip().lower() if (DisplayStyle is not None) else None
        if (CleanStyle is not None) and (CleanStyle not in VALID_DISPLAY_STYLES):
            CleanStyle = "number"

        CounterPayload: dict[str, Typing.Any] = {
            "Name"         : CounterName,
            "Value"        : InitialValue,
            "MaxValue"     : MaxValue,
            "MinValue"     : MinValue,
            "ResetSchedule": ResetOn,
            "Description"  : Description,
            "DisplayStyle" : CleanStyle
        }
        self.CustomCounters[CounterName] = {
            "Value"        : InitialValue,
            "MaxValue"     : MaxValue,
            "MinValue"     : MinValue,
            "ResetSchedule": ResetOn,
            "Description"  : Description,
            "DisplayStyle" : CleanStyle
        }
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Created Counter: Name=\"{CounterName}\", Value={InitialValue}, Style=\"{CleanStyle}\"")
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

        CounterData : dict[str, Typing.Any] = self.CustomCounters[CounterName]
        CurrentValue: int                   = int(CounterData.get("Value", 0))
        NewValue    : int                   = CurrentValue + DeltaValue

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

    def GetCounterDisplayStyle(self, CounterName: str) -> str:
        if CounterName in self.CustomCounters:
            CounterStyle: Typing.Optional[str] = self.CustomCounters[CounterName].get("DisplayStyle")
            if (CounterStyle is not None):
                return CounterStyle.lower()

        CharacterPreference: Typing.Optional[str] = self.Variables.get("csetting_counter_display")
        if (CharacterPreference is not None) and (CharacterPreference.lower() in VALID_DISPLAY_STYLES):
            return CharacterPreference.lower()

        return "number"

    def SetCounterDisplayStyle(self, CounterName: str, DisplayStyle: str) -> str:
        if CounterName not in self.CustomCounters:
            raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

        CleanStyle: str = DisplayStyle.strip().lower()
        if CleanStyle not in VALID_DISPLAY_STYLES:
            raise Exceptions.DraconicExecutionError(f"Invalid display style '{DisplayStyle}'. Valid options: {", ".join(VALID_DISPLAY_STYLES)}")

        self.CustomCounters[CounterName]["DisplayStyle"] = CleanStyle
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Set Counter Display Style: Name=\"{CounterName}\", Style=\"{CleanStyle}\"")
        return CleanStyle

    def FormatCounter(self, CounterName: str, OverrideStyle: Typing.Optional[str] = None) -> str:
        if CounterName not in self.CustomCounters:
            raise Exceptions.DraconicExecutionError(f"Counter '{CounterName}' does not exist")

        CounterData: dict[str, Typing.Any] = self.CustomCounters[CounterName]
        Value      : int                   = int(CounterData.get("Value", 0))
        MaxValue   : Typing.Optional[int]  = CounterData.get("MaxValue")
        StyleToUse : str                   = OverrideStyle.strip().lower() if (OverrideStyle is not None) else self.GetCounterDisplayStyle(CounterName)

        if StyleToUse in COUNTER_DISPLAY_SHAPES:
            FilledSym, EmptySym = COUNTER_DISPLAY_SHAPES[StyleToUse]
            if (MaxValue is not None) and (MaxValue > 0) and (MaxValue <= 30):
                ClampedValue: int = max(0, min(MaxValue, Value))
                EmptyCount  : int = max(0, MaxValue - ClampedValue)
                ShapeString : str = (FilledSym * ClampedValue) + (EmptySym * EmptyCount)
                return f"[{ShapeString}] {Value}/{MaxValue}"

            elif (MaxValue is None) and (Value >= 0) and (Value <= 20):
                ShapeString = (FilledSym * Value) if (Value > 0) else EmptySym
                return f"[{ShapeString}] {Value}"

        return f"{Value}/{MaxValue}" if (MaxValue is not None) else str(Value)

    def GetAllCounters(self) -> dict[str, dict[str, Typing.Any]]:
        return self.CustomCounters

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

