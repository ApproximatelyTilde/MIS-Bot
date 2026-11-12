import typing                                       as Typing
import Runtime.Services.DiceService                 as Dice
import Runtime.Services.EncounterManagerService     as EncounterManager
import Runtime.Services.Draconic.API.ArgumentParser as ArgumentParser
import Runtime.Services.Automation.AutomationModels as Models

class AutomationContext:
    def __init__(self, Caster: Typing.Any, Targets: list[EncounterManager.CombatantEntry], Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None, ChannelID: str = "", Arguments: Typing.Optional[ArgumentParser.ParsedArguments] = None, SpellLevel: int = 1, Variables: Typing.Optional[dict[str, Typing.Any]] = None, DiceRoller: Typing.Optional[Dice.DiceRollerService] = None, ActionName: str = "Action", Phrase: Typing.Optional[str] = None, ThumbnailURL: Typing.Optional[str] = None) -> None:
        self.Caster          : Typing.Any                                        = Caster
        self.Targets         : list[EncounterManager.CombatantEntry]             = Targets
        self.Encounter       : Typing.Optional[EncounterManager.CombatEncounter] = Encounter
        self.ChannelID       : str                                               = ChannelID
        self.Arguments       : ArgumentParser.ParsedArguments                    = Arguments if (Arguments is not None) else ArgumentParser.CreateArgumentParser("")
        self.SpellLevel      : int                                               = SpellLevel
        self.Variables       : dict[str, Typing.Any]                             = Variables if (Variables is not None) else dict()
        self.DiceRoller      : Dice.DiceRollerService                            = DiceRoller if (DiceRoller is not None) else Dice.DiceRollerService()
        self.Result          : Models.AutomationExecutionResult                  = Models.AutomationExecutionResult(ActionName = ActionName, CasterName = self.GetCasterName(), Phrase = Phrase, ThumbnailURL = ThumbnailURL)

    def GetCasterName(self) -> str:
        if hasattr(self.Caster, "Name"):
            return str(self.Caster.Name)

        if hasattr(self.Caster, "name"):
            return str(self.Caster.name)

        if isinstance(self.Caster, dict):
            return str(self.Caster.get("Name", self.Caster.get("name", "Caster")))

        return "Caster"

    def GetOrCreateTargetOutcome(self, TargetName: str) -> Models.TargetEffectOutcome:
        for Outcome in self.Result.TargetOutcomes:
            if (Outcome.TargetName.lower() == TargetName.lower()):
                return Outcome

        NewOutcome: Typing.Any = Models.TargetEffectOutcome(TargetName = TargetName)
        self.Result.TargetOutcomes.append(NewOutcome)
        return NewOutcome

    def LogGlobalMessage(self, MessageText: str) -> None:
        self.Result.GlobalNarrative.append(MessageText)
