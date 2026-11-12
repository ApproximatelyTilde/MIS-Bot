import enum                  as Enumeration
import re                    as RegularExpressions
import typing                as Typing
import d20                   as D20Library
import pydantic              as Pydantic
import Services.DebugService as Debug

DEFAULT_DICE_EXPRESSION: str = "1d20"
MAXIMUM_REPEAT_COUNT   : int = 50

REPEAT_PATTERN           : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:--?rr|\brr)\s+(\d+)", RegularExpressions.IGNORECASE)
ADVANTAGE_PATTERN        : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:--?adv|\badv\b)", RegularExpressions.IGNORECASE)
DISADVANTAGE_PATTERN     : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:--?disadv|--?dis|\bdisadv\b|\bdis\b)", RegularExpressions.IGNORECASE)

class AdvantageMode(str, Enumeration.Enum):
    NoneMode     = "None"
    Advantage    = "Advantage"
    Disadvantage = "Disadvantage"

class RollOutcome(Pydantic.BaseModel):
    RawInput       : str
    Expression     : str
    FormattedString: str
    Breakdown      : str
    Total          : int
    Comment        : Typing.Optional[str] = None
    IsCriticalHit  : bool                 = False
    IsCriticalMiss : bool                 = False
    Advantage      : AdvantageMode        = AdvantageMode.NoneMode

class DiceRollerService:
    def ParseFlagsAndExpression(self, RawInputString: str) -> Typing.Tuple[str, D20Library.AdvType, int, Typing.Optional[str]]:
        WorkingText: str             = RawInputString.strip()
        RepeatCount: int             = 1
        ResolvedAdv: D20Library.AdvType = D20Library.AdvType.NONE
        ExtractedComment: Typing.Optional[str] = None

        RepeatMatch = REPEAT_PATTERN.search(WorkingText)
        if (RepeatMatch is not None):
            ParsedCount: int = int(RepeatMatch.group(1))
            RepeatCount      = max(1, min(ParsedCount, MAXIMUM_REPEAT_COUNT))
            WorkingText      = REPEAT_PATTERN.sub("", WorkingText).strip()

        AdvantageMatch = ADVANTAGE_PATTERN.search(WorkingText)
        if (AdvantageMatch is not None):
            ResolvedAdv = D20Library.AdvType.ADV
            WorkingText = ADVANTAGE_PATTERN.sub("", WorkingText).strip()

        DisadvantageMatch = DISADVANTAGE_PATTERN.search(WorkingText)
        if (DisadvantageMatch is not None):
            ResolvedAdv = D20Library.AdvType.DIS
            WorkingText = DISADVANTAGE_PATTERN.sub("", WorkingText).strip()

        if (len(WorkingText) == 0):
            WorkingText = DEFAULT_DICE_EXPRESSION

        return (WorkingText, ResolvedAdv, RepeatCount, ExtractedComment)

    def EvaluateRoll(self, RawInputString: str, ForcedAdvantage: Typing.Optional[D20Library.AdvType] = None) -> RollOutcome:
        CleanedExpression, DetectedAdvantage, _, ExtractedComment = self.ParseFlagsAndExpression(RawInputString)
        EffectiveAdvantage: D20Library.AdvType = ForcedAdvantage if (ForcedAdvantage is not None) else DetectedAdvantage
        AdvantageLabel    : AdvantageMode      = AdvantageMode.NoneMode
        if (EffectiveAdvantage == D20Library.AdvType.ADV):
            AdvantageLabel = AdvantageMode.Advantage

        elif (EffectiveAdvantage == D20Library.AdvType.DIS):
            AdvantageLabel = AdvantageMode.Disadvantage

        RollResult: D20Library.RollResult = D20Library.roll(CleanedExpression, advantage = EffectiveAdvantage, allow_comments = True)
        FullFormatted: str = str(RollResult)
        BreakdownPart: str = FullFormatted
        if (" = " in FullFormatted):
            BreakdownPart = FullFormatted.split(" = ")[0].strip()

        FinalComment: Typing.Optional[str] = RollResult.comment if (RollResult.comment is not None) else ExtractedComment
        IsCritHit   : bool                 = (RollResult.crit == D20Library.CritType.CRIT)
        IsCritMiss  : bool                 = (RollResult.crit == D20Library.CritType.FAIL)

        Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Dice Evaluated: Expr=\"{CleanedExpression}\", Total={RollResult.total}, CritHit={IsCritHit}, CritMiss={IsCritMiss}")
        return RollOutcome(
            RawInput        = RawInputString,
            Expression      = CleanedExpression,
            FormattedString = FullFormatted,
            Breakdown       = BreakdownPart,
            Total           = int(RollResult.total),
            Comment         = FinalComment,
            IsCriticalHit   = IsCritHit,
            IsCriticalMiss  = IsCritMiss,
            Advantage       = AdvantageLabel
        )

    def EvaluateMultipleRolls(self, RawInputString: str, ForcedAdvantage: Typing.Optional[D20Library.AdvType] = None) -> Typing.List[RollOutcome]:
        _, _, RepeatCount, _ = self.ParseFlagsAndExpression(RawInputString)
        ResultsList: Typing.List[RollOutcome] = []
        for RollIndex in range(RepeatCount):
            SingleResult: RollOutcome = self.EvaluateRoll(RawInputString, ForcedAdvantage = ForcedAdvantage)
            ResultsList.append(SingleResult)

        return ResultsList

