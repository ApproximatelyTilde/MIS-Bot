import json                          as JSONLibrary
import re                            as RegularExpressions
import typing                        as Typing
import Runtime.Services.DebugService as Debug

TRAILING_COMMA_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r",\s*([\]\}])")

def StripJSONCComments(InputText: str) -> str:
    OutputCharacters     : list[str] = []
    TextLength           : int       = len(InputText)
    Index                : int       = 0
    IsInsideString       : bool      = False
    IsEscaped            : bool      = False
    IsInsideSingleComment: bool      = False
    IsInsideMultiComment : bool      = False

    while (Index < TextLength):
        CurrentCharacter: str = InputText[Index]
        NextCharacter   : str = InputText[Index + 1] if (Index + 1 < TextLength) else ""

        if IsInsideSingleComment:
            if (CurrentCharacter == "\n"):
                IsInsideSingleComment = False
                OutputCharacters.append("\n")

            Index += 1
            continue

        if IsInsideMultiComment:
            if (CurrentCharacter == "*") and (NextCharacter == "/"):
                IsInsideMultiComment = False
                Index += 2
                continue

            Index += 1
            continue

        if IsInsideString:
            OutputCharacters.append(CurrentCharacter)
            if IsEscaped:
                IsEscaped = False

            elif (CurrentCharacter == "\\"):
                IsEscaped = True

            elif (CurrentCharacter == "\""):
                IsInsideString = False

            Index += 1
            continue

        if (CurrentCharacter == "\""):
            IsInsideString = True
            OutputCharacters.append(CurrentCharacter)
            Index += 1
            continue

        if (CurrentCharacter == "/") and (NextCharacter == "/"):
            IsInsideSingleComment = True
            Index += 2
            continue

        if (CurrentCharacter == "/") and (NextCharacter == "*"):
            IsInsideMultiComment = True
            Index += 2
            continue

        OutputCharacters.append(CurrentCharacter)
        Index += 1

    return "".join(OutputCharacters)

def StripTrailingCommas(CleanedJSONText: str) -> str:
    return TRAILING_COMMA_PATTERN.sub(r"\1", CleanedJSONText)

def NormalizeJSONC(InputText: str) -> str:
    StrippedCommentsText: str = StripJSONCComments(InputText)
    NormalizedJSONString: str = StripTrailingCommas(StrippedCommentsText)
    return NormalizedJSONString

def ParseJSONC(InputText: str) -> Typing.Any:
    NormalizedString: str = NormalizeJSONC(InputText)
    try:
        ParsedObject: Typing.Any = JSONLibrary.loads(NormalizedString)
        return ParsedObject

    except JSONLibrary.JSONDecodeError as DecodeError:
        Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"JSONC Decode Failed: Error=\"{str(DecodeError)}\"")
        raise ValueError(f"Invalid JSONC syntax: {str(DecodeError)}") from DecodeError

def DumpJSONC(DataObject: Typing.Any, Indent: int = 2) -> str:
    return JSONLibrary.dumps(DataObject, indent = Indent, ensure_ascii = False)
