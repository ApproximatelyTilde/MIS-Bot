import typing                               as Typing
import Services.DiceService                  as DiceService
import Services.EncounterManagerService        as EncounterManager
import Services.Draconic.API.ArgumentParser as ArgumentParser
import Services.Automation.AutomationModels   as Models

class AutomationContext:
    def __init__(
        self,
        Caster               : Typing.Any,
        Targets              : list[EncounterManager.CombatantEntry],
        Encounter            : Typing.Optional[EncounterManager.CombatEncounter] = None,
        ChannelID            : str                                               = "",
        Arguments            : Typing.Optional[ArgumentParser.ParsedArguments]   = None,
        SpellLevel           : int                                               = 1,
        Variables            : Typing.Optional[dict[str, Typing.Any]]            = None,
        DiceRoller           : Typing.Optional[DiceService.DiceRollerService]    = None,
        ActionName           : str                                               = "Action",
        Phrase               : Typing.Optional[str]                              = None,
        ThumbnailURL         : Typing.Optional[str]                              = None
    ) -> None:
        self.Caster          : Typing.Any                                        = Caster
        self.Targets         : list[EncounterManager.CombatantEntry]             = Targets
        self.Encounter       : Typing.Optional[EncounterManager.CombatEncounter] = Encounter
        self.ChannelID       : str                                               = ChannelID
        self.Arguments       : ArgumentParser.ParsedArguments                    = Arguments if (Arguments is not None) else ArgumentParser.CreateArgumentParser("")
        self.SpellLevel      : int                                               = SpellLevel
        self.Variables       : dict[str, Typing.Any]                             = Variables if (Variables is not None) else {}
        self.DiceRoller      : DiceService.DiceRollerService                     = DiceRoller if (DiceRoller is not None) else DiceService.DiceRollerService()
        self.Result          : Models.AutomationExecutionResult                  = Models.AutomationExecutionResult(
            ActionName   = ActionName,
            CasterName   = self.GetCasterName(),
            Phrase       = Phrase,
            ThumbnailURL = ThumbnailURL
        )

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

        NewOutcome = Models.TargetEffectOutcome(TargetName = TargetName)
        self.Result.TargetOutcomes.append(NewOutcome)
        return NewOutcome

    def LogGlobalMessage(self, MessageText: str) -> None:
        self.Result.GlobalNarrative.append(MessageText)
