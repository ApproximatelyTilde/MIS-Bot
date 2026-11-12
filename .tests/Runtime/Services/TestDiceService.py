import d20                          as D20Library
import Runtime.Services.DiceService as Dice

class TestDiceService:
    def TestParseFlagsAndExpressionDefaultFallback(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Expression, AdvType, RepeatCount, Comment = DiceRoller.ParseFlagsAndExpression("")
        assert (Expression == Dice.DEFAULT_DICE_EXPRESSION)
        assert (AdvType == D20Library.AdvType.NONE)
        assert (RepeatCount == 1)
        assert (Comment is None)

    def TestParseFlagsAndExpressionWithRepeat(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Expression, AdvType, RepeatCount, Comment = DiceRoller.ParseFlagsAndExpression("1d20 + 5 --rr 4")
        assert (Expression == "1d20 + 5")
        assert (AdvType == D20Library.AdvType.NONE)
        assert (RepeatCount == 4)

    def TestParseFlagsAndExpressionRepeatClamping(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        _, _, RepeatCountHigh, _ = DiceRoller.ParseFlagsAndExpression("1d20 -rr 100")
        assert (RepeatCountHigh == Dice.MAXIMUM_REPEAT_COUNT)

        _, _, RepeatCountLow, _ = DiceRoller.ParseFlagsAndExpression("1d20 -rr 0")
        assert (RepeatCountLow == 1)

    def TestParseFlagsAndExpressionAdvantage(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Expression, AdvType, _, _ = DiceRoller.ParseFlagsAndExpression("1d20 + 3 adv")
        assert (Expression == "1d20 + 3")
        assert (AdvType == D20Library.AdvType.ADV)

    def TestParseFlagsAndExpressionDisadvantage(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Expression, AdvType, _, _ = DiceRoller.ParseFlagsAndExpression("1d20 + 3 dis")
        assert (Expression == "1d20 + 3")
        assert (AdvType == D20Library.AdvType.DIS)

    def TestEvaluateRollStandard(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Outcome   : Dice.RollOutcome       = DiceRoller.EvaluateRoll("1d6 + 2")
        assert (Outcome.Expression == "1d6 + 2")
        assert (3 <= Outcome.Total <= 8)
        assert (Outcome.Advantage == Dice.AdvantageMode.NoneMode)
        assert (len(Outcome.FormattedString) > 0)
        assert (len(Outcome.Breakdown) > 0)

    def TestEvaluateRollForcedAdvantage(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Outcome   : Dice.RollOutcome       = DiceRoller.EvaluateRoll("1d20", ForcedAdvantage = D20Library.AdvType.ADV)
        assert (Outcome.Advantage == Dice.AdvantageMode.Advantage)
        assert (1 <= Outcome.Total <= 20)

    def TestEvaluateRollForcedDisadvantage(self) -> None:
        DiceRoller: Dice.DiceRollerService = Dice.DiceRollerService()
        Outcome   : Dice.RollOutcome       = DiceRoller.EvaluateRoll("1d20", ForcedAdvantage = D20Library.AdvType.DIS)
        assert (Outcome.Advantage == Dice.AdvantageMode.Disadvantage)
        assert (1 <= Outcome.Total <= 20)

    def TestEvaluateMultipleRolls(self) -> None:
        DiceRoller  : Dice.DiceRollerService = Dice.DiceRollerService()
        OutcomesList: list[Dice.RollOutcome] = DiceRoller.EvaluateMultipleRolls("1d20 + 2 -rr 3")
        assert (len(OutcomesList) == 3)
        for SingleOutcome in OutcomesList:
            assert (3 <= SingleOutcome.Total <= 22)

    def TestRollOutcomeModelValidation(self) -> None:
        OutcomeInstance: Dice.RollOutcome = Dice.RollOutcome(RawInput = "1d20 + 4", Expression = "1d20 + 4", FormattedString = "1d20 (15) + 4 = 19", Breakdown = "1d20 (15) + 4", Total = 19, Comment = "Perception", IsCriticalHit = False, IsCriticalMiss = False, Advantage = Dice.AdvantageMode.NoneMode)
        assert (OutcomeInstance.Total == 19)
        assert (OutcomeInstance.Comment == "Perception")
