import math                                         as MathLibrary
import typing                                       as Typing
import Services.DebugService                        as Debug
import Services.DiceService                         as Dice
import Services.EncounterManagerService             as EncounterManager
import Services.Automation.AutomationModels         as Models
import Services.Automation.DynamicConditionRegistry as ConditionRegistry
import Services.Automation.ConcentrationManager     as ConcentrationManager
import Services.Automation.Effects.DamageEffect     as DamageEffect

class IEffectHandler:
    def __init__(self, DiceRoller: Typing.Optional[Dice.DiceRollerService] = None) -> None:
        self.DiceRoller          : Dice.DiceRollerService              = DiceRoller if (DiceRoller is not None) else Dice.DiceRollerService()
        self.ConcentrationManager: ConcentrationManager.ConcentrationManager = ConcentrationManager.ConcentrationManager(self.DiceRoller)

    def GetCombatantActiveEffects(self, Combatant: EncounterManager.CombatantEntry) -> list[dict[str, Typing.Any]]:
        if not hasattr(Combatant, "Effects"):
            Combatant.__dict__["Effects"] = []

        return getattr(Combatant, "Effects", [])

    def AttachEffect(self, Combatant: EncounterManager.CombatantEntry, EffectName: str, DurationRounds: Typing.Optional[int] = None, PassiveEffects: Typing.Optional[Models.PassiveEffectsModel] = None, IsConcentration: bool = False, CasterName: str = "", Buttons: Typing.Optional[list[dict[str, Typing.Any]]] = None, SubAttacks: Typing.Optional[list[dict[str, Typing.Any]]] = None, TickOn: Typing.Optional[str] = None, Description: Typing.Optional[str] = None, Parent: Typing.Optional[str] = None, SaveAs: Typing.Optional[str] = None, Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None) -> dict[str, Typing.Any]:
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)

        if IsConcentration:
            self.ConcentrationManager.SetConcentration(Encounter, Combatant, EffectName, [EffectName])

        NewEffect: dict[str, Typing.Any] = {
            "Name"          : EffectName,
            "DurationRounds": DurationRounds,
            "PassiveEffects": PassiveEffects.model_dump() if (PassiveEffects is not None) else dict(),
            "Buttons"       : list(Buttons) if (Buttons is not None) else [],
            "SubAttacks"    : list(SubAttacks) if (SubAttacks is not None) else [],
            "TickOn"        : TickOn,
            "Description"   : Description,
            "Concentration" : IsConcentration,
            "Caster"        : CasterName,
            "Parent"        : Parent,
            "SaveAs"        : SaveAs
        }
        ActiveEffects.append(NewEffect)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Attached Effect: Name=\"{EffectName}\", Combatant=\"{Combatant.Name}\", Conc={IsConcentration}")
        return NewEffect

    def RemoveEffect(self, Combatant: EncounterManager.CombatantEntry, EffectName: str, Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None) -> bool:
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)
        CleanTarget  : str                         = EffectName.strip().lower()

        for EffectItem in list(ActiveEffects):
            if (str(EffectItem.get("Name", "")).lower() == CleanTarget):
                if bool(EffectItem.get("Concentration", False)):
                    self.ConcentrationManager.DropConcentration(Encounter, Combatant)

                if EffectItem in ActiveEffects:
                    ActiveEffects.remove(EffectItem)

                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Removed Effect: Name=\"{EffectName}\", Combatant=\"{Combatant.Name}\"")
                return True

        return False

    def DropConcentration(self, Combatant: EncounterManager.CombatantEntry, Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None) -> Typing.Optional[str]:
        return self.ConcentrationManager.DropConcentration(Encounter, Combatant)

    def HandleDamageConcentrationCheck(self, Combatant: EncounterManager.CombatantEntry, DamageAmount: int, Encounter: Typing.Optional[EncounterManager.CombatEncounter] = None, AutoRoll: bool = False) -> Typing.Optional[str]:
        if (DamageAmount <= 0):
            return None

        RequiredDC, SaveSucceeded, Message = self.ConcentrationManager.CheckDamageConcentration(Encounter, Combatant, DamageAmount, AutoRoll = AutoRoll)
        return Message if (Message) else None

    def CollectAllPassiveModifiers(self, Combatant: EncounterManager.CombatantEntry) -> list[Models.PassiveEffectsModel]:
        CombinedList: list[Models.PassiveEffectsModel] = []

        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)
        for EffectItem in ActiveEffects:
            PassiveData = EffectItem.get("PassiveEffects")
            if (PassiveData is not None) and isinstance(PassiveData, dict) and PassiveData:
                CombinedList.append(Models.PassiveEffectsModel.model_validate(PassiveData))

        ConditionModifiers = ConditionRegistry.GLOBAL_CONDITION_REGISTRY.ResolveConditionModifiers(Combatant.Conditions)
        CombinedList.extend(ConditionModifiers)
        return CombinedList

    def CalculateArmorClassModifier(self, Target: EncounterManager.CombatantEntry) -> int:
        ModifiersList: list[Models.PassiveEffectsModel] = self.CollectAllPassiveModifiers(Target)
        TotalBonus   : int                              = 0
        for ModifierItem in ModifiersList:
            if (ModifierItem.ArmorClassBonus is not None):
                TotalBonus += ModifierItem.ArmorClassBonus

        return TotalBonus

    def CalculateNetAdvantage(self, CasterCombatant: Typing.Optional[EncounterManager.CombatantEntry], TargetCombatant: Typing.Optional[EncounterManager.CombatantEntry], BaseAdvantage: int = 0) -> int:
        NetAdvantage: int = BaseAdvantage

        if (CasterCombatant is not None):
            for ModifierItem in self.CollectAllPassiveModifiers(CasterCombatant):
                if (ModifierItem.AttackAdvantage is not None):
                    NetAdvantage += ModifierItem.AttackAdvantage

        return max(-1, min(1, NetAdvantage))

    def CalculateAttackBonus(self, CasterCombatant: Typing.Optional[EncounterManager.CombatantEntry]) -> int:
        if (CasterCombatant is None):
            return 0

        TotalBonus: int = 0
        for ModifierItem in self.CollectAllPassiveModifiers(CasterCombatant):
            if (ModifierItem.ToHitBonus is not None):
                CleanBonusText: str = ModifierItem.ToHitBonus.strip().lstrip("+")
                if CleanBonusText.lstrip("-").isdigit():
                    TotalBonus += int(CleanBonusText)

        return TotalBonus

    def CalculateDamageBonus(self, CasterCombatant: Typing.Optional[EncounterManager.CombatantEntry]) -> int:
        if (CasterCombatant is None):
            return 0

        TotalBonus: int = 0
        for ModifierItem in self.CollectAllPassiveModifiers(CasterCombatant):
            if (ModifierItem.DamageBonus is not None):
                CleanBonusText: str = ModifierItem.DamageBonus.strip().lstrip("+")
                if CleanBonusText.lstrip("-").isdigit():
                    TotalBonus += int(CleanBonusText)

        return TotalBonus

    def CalculateSavingThrowBonus(self, Combatant: EncounterManager.CombatantEntry, StatName: str) -> int:
        TotalBonus : int                               = 0
        CleanStat  : str                               = StatName.strip().lower()
        Modifiers  : list[Models.PassiveEffectsModel] = self.CollectAllPassiveModifiers(Combatant)

        for ModifierItem in Modifiers:
            if (ModifierItem.SaveBonus is not None):
                CleanBonusText: str = ModifierItem.SaveBonus.strip().lstrip("+")
                if CleanBonusText.lstrip("-").isdigit():
                    TotalBonus += int(CleanBonusText)

        return TotalBonus

    def CalculateSaveAdvantage(self, Combatant: EncounterManager.CombatantEntry, StatName: str) -> int:
        CleanStat: str = StatName.strip().lower()
        AdvCount : int = 0
        DisCount : int = 0

        for ModifierItem in self.CollectAllPassiveModifiers(Combatant):
            if (ModifierItem.SaveAdvantage is not None):
                if (CleanStat in [S.lower() for S in ModifierItem.SaveAdvantage]) or ("all" in [S.lower() for S in ModifierItem.SaveAdvantage]):
                    AdvCount += 1

            if (ModifierItem.SaveDisadvantage is not None):
                if (CleanStat in [S.lower() for S in ModifierItem.SaveDisadvantage]) or ("all" in [S.lower() for S in ModifierItem.SaveDisadvantage]):
                    DisCount += 1

        NetAdv: int = AdvCount - DisCount
        return max(-1, min(1, NetAdv))

    def CalculateCheckBonus(self, Combatant: EncounterManager.CombatantEntry, AbilityOrSkillName: str) -> int:
        TotalBonus: int                               = 0
        Modifiers : list[Models.PassiveEffectsModel] = self.CollectAllPassiveModifiers(Combatant)

        for ModifierItem in Modifiers:
            if (ModifierItem.CheckBonus is not None):
                CleanBonusText: str = ModifierItem.CheckBonus.strip().lstrip("+")
                if CleanBonusText.lstrip("-").isdigit():
                    TotalBonus += int(CleanBonusText)

        return TotalBonus

    def CalculateCheckAdvantage(self, Combatant: EncounterManager.CombatantEntry, AbilityOrSkillName: str) -> int:
        CleanKey: str = AbilityOrSkillName.strip().lower()
        AdvCount: int = 0
        DisCount: int = 0

        for ModifierItem in self.CollectAllPassiveModifiers(Combatant):
            if (ModifierItem.CheckAdvantage is not None):
                if (CleanKey in [C.lower() for C in ModifierItem.CheckAdvantage]) or ("all" in [C.lower() for C in ModifierItem.CheckAdvantage]):
                    AdvCount += 1

            if (ModifierItem.CheckDisadvantage is not None):
                if (CleanKey in [C.lower() for C in ModifierItem.CheckDisadvantage]) or ("all" in [C.lower() for C in ModifierItem.CheckDisadvantage]):
                    DisCount += 1

        NetAdv: int = AdvCount - DisCount
        return max(-1, min(1, NetAdv))

    def GetAvailableButtons(self, Combatant: EncounterManager.CombatantEntry) -> list[dict[str, Typing.Any]]:
        ButtonsList  : list[dict[str, Typing.Any]] = []
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)

        for EffectItem in ActiveEffects:
            EffectButtons: list[dict[str, Typing.Any]] = EffectItem.get("Buttons", [])
            for Btn in EffectButtons:
                ButtonsList.append(Btn)

        return ButtonsList

    def GetAvailableSubAttacks(self, Combatant: EncounterManager.CombatantEntry) -> list[dict[str, Typing.Any]]:
        AttacksList  : list[dict[str, Typing.Any]] = []
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)

        for EffectItem in ActiveEffects:
            EffectAttacks: list[dict[str, Typing.Any]] = EffectItem.get("SubAttacks", [])
            for Atk in EffectAttacks:
                AttacksList.append(Atk)

        return AttacksList

    def ApplyDamageModifiers(self, Target: EncounterManager.CombatantEntry, RawDamage: int, DamageType: Typing.Optional[str]) -> tuple[int, str]:
        if (RawDamage <= 0) or (DamageType is None):
            return (RawDamage, "")

        CleanType: str = DamageType.strip().lower()
        Modifiers: list[Models.PassiveEffectsModel] = self.CollectAllPassiveModifiers(Target)

        for ModifierItem in Modifiers:
            if (ModifierItem.Immunities is not None) and (CleanType in [I.lower() for I in ModifierItem.Immunities]):
                return (0, f" (Immune to {DamageType})")

        IsResistant: bool = False
        for ModifierItem in Modifiers:
            if (ModifierItem.Resistances is not None) and (CleanType in [R.lower() for R in ModifierItem.Resistances]):
                IsResistant = True
                break

        IsVulnerable: bool = False
        for ModifierItem in Modifiers:
            if (ModifierItem.Vulnerabilities is not None) and (CleanType in [V.lower() for V in ModifierItem.Vulnerabilities]):
                IsVulnerable = True
                break

        if (IsResistant and IsVulnerable):
            return (RawDamage, "")

        if IsResistant:
            ModifiedDamage = RawDamage // 2
            return (ModifiedDamage, f" (Resisted: {RawDamage} ➔ {ModifiedDamage})")

        if IsVulnerable:
            ModifiedDamage = RawDamage * 2
            return (ModifiedDamage, f" (Vulnerable: {RawDamage} ➔ {ModifiedDamage})")

        return (RawDamage, "")

    def TickTurnEffects(self, Encounter: EncounterManager.CombatEncounter) -> list[str]:
        Announcements: list[str] = []
        for Combatant in Encounter.Combatants:
            ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)
            for EffectItem in list(ActiveEffects):
                DurationRounds: Typing.Optional[int] = EffectItem.get("DurationRounds")
                if (DurationRounds is not None):
                    DurationRounds -= 1
                    if (DurationRounds <= 0):
                        if bool(EffectItem.get("Concentration", False)):
                            self.ConcentrationManager.DropConcentration(Encounter, Combatant)

                        if EffectItem in ActiveEffects:
                            ActiveEffects.remove(EffectItem)

                        Announcements.append(f"⏱️ Effect **{EffectItem.get("Name")}** expired on **{Combatant.Name}**.")

                    else:
                        EffectItem["DurationRounds"] = DurationRounds

        return Announcements
