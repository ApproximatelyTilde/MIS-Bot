import math                             as MathLibrary
import typing                           as Typing
import Services.DebugService            as Debug
import Services.DiceService             as Dice
import Services.EncounterManagerService as EncounterManager

class ConcentrationState:
    def __init__(self, SpellOrEffectName: str, LinkedEffectIDs: Typing.Optional[list[str]] = None, CasterName: str = "") -> None:
        self.SpellOrEffectName: str       = SpellOrEffectName
        self.LinkedEffectIDs  : list[str] = list(LinkedEffectIDs) if (LinkedEffectIDs is not None) else []
        self.CasterName       : str       = CasterName

class ConcentrationManager:
    def __init__(self, DiceRoller: Typing.Optional[Dice.DiceRollerService] = None) -> None:
        self.DiceRoller: Dice.DiceRollerService = DiceRoller if (DiceRoller is not None) else Dice.DiceRollerService()

    def CalculateConcentrationSaveDC(self, DamageAmount: int) -> int:
        if (DamageAmount <= 0):
            return 10

        CalculatedDC: int = max(10, MathLibrary.floor(DamageAmount / 2))
        return CalculatedDC

    def IsConcentrating(self, Combatant: EncounterManager.CombatantEntry) -> bool:
        ConcentrationData: Typing.Optional[dict[str, Typing.Any]] = getattr(Combatant, "ConcentrationData", None)
        if (ConcentrationData is not None) and ConcentrationData.get("Name"):
            return True

        EffectsList: list[dict[str, Typing.Any]] = getattr(Combatant, "Effects", [])
        for EffectItem in EffectsList:
            if bool(EffectItem.get("Concentration", False)):
                return True

        return False

    def GetConcentrationName(self, Combatant: EncounterManager.CombatantEntry) -> Typing.Optional[str]:
        ConcentrationData: Typing.Optional[dict[str, Typing.Any]] = getattr(Combatant, "ConcentrationData", None)
        if (ConcentrationData is not None) and ConcentrationData.get("Name"):
            return str(ConcentrationData.get("Name"))

        EffectsList: list[dict[str, Typing.Any]] = getattr(Combatant, "Effects", [])
        for EffectItem in EffectsList:
            if bool(EffectItem.get("Concentration", False)):
                return str(EffectItem.get("Name", "Concentration"))

        return None

    def SetConcentration(self, Encounter: Typing.Optional[EncounterManager.CombatEncounter], Combatant: EncounterManager.CombatantEntry, SpellOrEffectName: str, LinkedEffectNames: Typing.Optional[list[str]] = None) -> Typing.Optional[str]:
        PreviousDropMessage: Typing.Optional[str] = None
        if self.IsConcentrating(Combatant):
            OldName             : Typing.Optional[str] = self.DropConcentration(Encounter, Combatant)
            PreviousDropMessage = f"**{Combatant.Name}** dropped concentration on **{OldName}** to cast **{SpellOrEffectName}**."

        LinkedNames: list[str] = list(LinkedEffectNames) if (LinkedEffectNames is not None) else [SpellOrEffectName]
        Combatant.__dict__["ConcentrationData"] = {
            "Name"       : SpellOrEffectName,
            "LinkedNames": LinkedNames
        }
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Concentration Set: Combatant=\"{Combatant.Name}\", Spell=\"{SpellOrEffectName}\"")
        return PreviousDropMessage

    def DropConcentration(self, Encounter: Typing.Optional[EncounterManager.CombatEncounter], Combatant: EncounterManager.CombatantEntry) -> Typing.Optional[str]:
        ConcentrationData: Typing.Optional[dict[str, Typing.Any]] = getattr(Combatant, "ConcentrationData", None)
        DroppedName      : Typing.Optional[str]                  = None
        LinkedNames      : list[str]                             = []

        if (ConcentrationData is not None):
            DroppedName = ConcentrationData.get("Name")
            LinkedNames = list(ConcentrationData.get("LinkedNames", []))
            Combatant.__dict__["ConcentrationData"] = None

        EffectsList: list[dict[str, Typing.Any]] = getattr(Combatant, "Effects", [])
        for EffectItem in list(EffectsList):
            if bool(EffectItem.get("Concentration", False)):
                if (DroppedName is None):
                    DroppedName = str(EffectItem.get("Name", "Concentration"))

                LinkedNames.append(str(EffectItem.get("Name", "")))
                EffectsList.remove(EffectItem)

        if (Encounter is not None) and LinkedNames:
            CleanLinkedNames: list[str] = [N.strip().lower() for N in LinkedNames if N]
            for TargetCombatant in Encounter.Combatants:
                TargetEffects: list[dict[str, Typing.Any]] = getattr(TargetCombatant, "Effects", [])
                for TargetEffect in list(TargetEffects):
                    if (str(TargetEffect.get("Name", "")).strip().lower() in CleanLinkedNames) and (str(TargetEffect.get("Caster", "")).strip().lower() == Combatant.Name.strip().lower()):
                        TargetEffects.remove(TargetEffect)
                        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Removed Linked Concentration Effect: Name=\"{TargetEffect.get("Name")}\", Target=\"{TargetCombatant.Name}\"")

        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Concentration Dropped: Combatant=\"{Combatant.Name}\", Effect=\"{DroppedName}\"")
        return DroppedName

    def CheckDamageConcentration(self, Encounter: Typing.Optional[EncounterManager.CombatEncounter], Combatant: EncounterManager.CombatantEntry, DamageAmount: int, AutoRoll: bool = False) -> tuple[int, bool, str]:
        RequiredDC: int = self.CalculateConcentrationSaveDC(DamageAmount)
        if not self.IsConcentrating(Combatant):
            return (RequiredDC, True, "")

        ActiveSpell: str = self.GetConcentrationName(Combatant) or "Concentration"
        if not AutoRoll:
            PromptMessage: str = f"⚠️ **{Combatant.Name}** took {DamageAmount} damage and must make a **DC {RequiredDC} Constitution saving throw** to maintain concentration on **{ActiveSpell}**."
            return (RequiredDC, False, PromptMessage)

        ConModifier: int = 0
        if (Combatant.MonsterData is not None) and isinstance(Combatant.MonsterData, dict):
            SavesDictionary = Combatant.MonsterData.get("save", {})
            if "con" in SavesDictionary:
                CleanConText: str = str(SavesDictionary["con"]).replace("+", "").strip()
                if CleanConText.lstrip("-").isdigit():
                    ConModifier = int(CleanConText)

            elif "con" in Combatant.MonsterData:
                Score       = int(Combatant.MonsterData.get("con", 10))
                ConModifier = (Score - 10) // 2

        RollFormula : str                    = f"1d20{"+" if (ConModifier >= 0) else ""}{ConModifier}"
        SaveOutcome : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(RollFormula)
        SaveSucceeded: bool                  = (SaveOutcome.Total >= RequiredDC)

        if SaveSucceeded:
            OutcomeMessage: str = f"🛡️ **{Combatant.Name}** maintained concentration on **{ActiveSpell}** (DC {RequiredDC} CON Save: rolled **{SaveOutcome.Total}**)."

        else:
            self.DropConcentration(Encounter, Combatant)
            OutcomeMessage: str = f"💥 **{Combatant.Name}** lost concentration on **{ActiveSpell}** (DC {RequiredDC} CON Save: rolled **{SaveOutcome.Total}**)."

        return (RequiredDC, SaveSucceeded, OutcomeMessage)
