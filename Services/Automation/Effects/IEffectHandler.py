import math                                     as MathLibrary
import typing                                   as Typing
import Services.DebugService                    as Debug
import Services.DiceService                     as DiceService
import Services.EncounterManagerService         as EncounterManager
import Services.Automation.AutomationModels     as Models
import Services.Automation.DynamicConditionRegistry as ConditionRegistry

class IEffectHandler:
    def __init__(self, DiceRoller: Typing.Optional[DiceService.DiceRollerService] = None) -> None:
        self.DiceRoller: DiceService.DiceRollerService = DiceRoller if (DiceRoller is not None) else DiceService.DiceRollerService()

    def GetCombatantActiveEffects(self, Combatant: EncounterManager.CombatantEntry) -> list[dict[str, Typing.Any]]:
        if not hasattr(Combatant, "Effects"):
            Combatant.__dict__["Effects"] = []

        return getattr(Combatant, "Effects", [])

    def AttachEffect(self, Combatant: EncounterManager.CombatantEntry, EffectName: str, DurationRounds: Typing.Optional[int] = None, PassiveEffects: Typing.Optional[Models.PassiveEffectsModel] = None, IsConcentration: bool = False, CasterName: str = "") -> dict[str, Typing.Any]:
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)

        if IsConcentration:
            self.DropConcentration(Combatant)

        NewEffect: dict[str, Typing.Any] = {
            "Name"          : EffectName,
            "DurationRounds": DurationRounds,
            "PassiveEffects": PassiveEffects.model_dump() if (PassiveEffects is not None) else {},
            "Concentration" : IsConcentration,
            "Caster"        : CasterName
        }
        ActiveEffects.append(NewEffect)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Attached Effect: Name=\"{EffectName}\", Combatant=\"{Combatant.Name}\", Conc={IsConcentration}")
        return NewEffect

    def RemoveEffect(self, Combatant: EncounterManager.CombatantEntry, EffectName: str) -> bool:
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)
        CleanTarget  : str                         = EffectName.strip().lower()

        for EffectItem in list(ActiveEffects):
            if (str(EffectItem.get("Name", "")).lower() == CleanTarget):
                ActiveEffects.remove(EffectItem)
                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Removed Effect: Name=\"{EffectName}\", Combatant=\"{Combatant.Name}\"")
                return True

        return False

    def DropConcentration(self, Combatant: EncounterManager.CombatantEntry) -> Typing.Optional[str]:
        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)
        for EffectItem in list(ActiveEffects):
            if EffectItem.get("Concentration", False):
                EffectName: str = str(EffectItem.get("Name", "Concentration Effect"))
                ActiveEffects.remove(EffectItem)
                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Dropped Concentration: Effect=\"{EffectName}\", Combatant=\"{Combatant.Name}\"")
                return EffectName

        return None

    def HandleDamageConcentrationCheck(self, Combatant: EncounterManager.CombatantEntry, DamageAmount: int) -> Typing.Optional[str]:
        if (DamageAmount <= 0):
            return None

        ActiveEffects: list[dict[str, Typing.Any]] = self.GetCombatantActiveEffects(Combatant)
        ConcentrationEffect: Typing.Optional[dict[str, Typing.Any]] = None
        for EffectItem in ActiveEffects:
            if EffectItem.get("Concentration", False):
                ConcentrationEffect = EffectItem
                break

        if (ConcentrationEffect is None):
            return None

        EffectName   : str = str(ConcentrationEffect.get("Name", "Concentration"))
        RequiredDC   : int = max(10, DamageAmount // 2)
        Announcement : str = f"⚠️ **{Combatant.Name}** took {DamageAmount} damage and must make a **DC {RequiredDC} Constitution saving throw** to maintain concentration on **{EffectName}**."
        return Announcement

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
        for Mod in ModifiersList:
            if (Mod.ArmorClassBonus is not None):
                TotalBonus += Mod.ArmorClassBonus

        return TotalBonus

    def CalculateNetAdvantage(self, CasterCombatant: Typing.Optional[EncounterManager.CombatantEntry], TargetCombatant: Typing.Optional[EncounterManager.CombatantEntry], BaseAdvantage: int = 0) -> int:
        NetAdvantage: int = BaseAdvantage

        if (CasterCombatant is not None):
            for Mod in self.CollectAllPassiveModifiers(CasterCombatant):
                if (Mod.AttackAdvantage is not None):
                    NetAdvantage += Mod.AttackAdvantage

        return max(-1, min(1, NetAdvantage))

    def CalculateAttackBonus(self, CasterCombatant: Typing.Optional[EncounterManager.CombatantEntry]) -> int:
        if (CasterCombatant is None):
            return 0

        TotalBonus: int = 0
        for Mod in self.CollectAllPassiveModifiers(CasterCombatant):
            if (Mod.ToHitBonus is not None):
                try:
                    TotalBonus += int(Mod.ToHitBonus.strip().lstrip("+"))

                except ValueError:
                    pass

        return TotalBonus

    def ApplyDamageModifiers(self, Target: EncounterManager.CombatantEntry, RawDamage: int, DamageType: Typing.Optional[str]) -> tuple[int, str]:
        if (RawDamage <= 0) or (DamageType is None):
            return (RawDamage, "")

        CleanType: str = DamageType.strip().lower()
        Modifiers: list[Models.PassiveEffectsModel] = self.CollectAllPassiveModifiers(Target)

        for Mod in Modifiers:
            if (Mod.Immunities is not None) and (CleanType in [I.lower() for I in Mod.Immunities]):
                return (0, f" (Immune to {DamageType})")

        IsResistant: bool = False
        for Mod in Modifiers:
            if (Mod.Resistances is not None) and (CleanType in [R.lower() for R in Mod.Resistances]):
                IsResistant = True
                break

        IsVulnerable: bool = False
        for Mod in Modifiers:
            if (Mod.Vulnerabilities is not None) and (CleanType in [V.lower() for V in Mod.Vulnerabilities]):
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
                        ActiveEffects.remove(EffectItem)
                        Announcements.append(f"⏱️ Effect **{EffectItem.get('Name')}** expired on **{Combatant.Name}**.")

                    else:
                        EffectItem["DurationRounds"] = DurationRounds

        return Announcements

