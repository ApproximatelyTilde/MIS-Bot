import typing                             as Typing
import Services.EncounterManagerService     as EncounterManager
import Services.Draconic.SandboxedScope     as SandboxedScope

class CombatantController:
    def __init__(self, Entry: EncounterManager.CombatantEntry) -> None:
        self.Entry: EncounterManager.CombatantEntry = Entry

    @property
    def id(self) -> str:
        return self.Entry.ID

    @property
    def name(self) -> str:
        return self.Entry.Name

    @property
    def hp(self) -> int:
        return self.Entry.CurrentHitPoints

    @property
    def max_hp(self) -> int:
        return self.Entry.MaxHitPoints

    @property
    def temp_hp(self) -> int:
        return self.Entry.TemporaryHitPoints

    @property
    def ac(self) -> int:
        return self.Entry.ArmorClass

    @property
    def init(self) -> int:
        return self.Entry.Initiative

    @property
    def initiative(self) -> int:
        return self.Entry.Initiative

    @property
    def conditions(self) -> SandboxedScope.DraconicList:
        return SandboxedScope.DraconicList(self.Entry.Conditions)

    def modify_hp(self, AmountDelta: int) -> int:
        CurrentHP: int = self.Entry.CurrentHitPoints
        TempHP   : int = self.Entry.TemporaryHitPoints

        if (AmountDelta < 0):
            DamageRemaining: int = abs(AmountDelta)
            if (TempHP > 0):
                AbsorbedDamage = min(TempHP, DamageRemaining)
                TempHP         -= AbsorbedDamage
                DamageRemaining -= AbsorbedDamage

            NewCurrentHP = max(0, CurrentHP - DamageRemaining)

        else:
            NewCurrentHP = min(self.Entry.MaxHitPoints, CurrentHP + AmountDelta)

        self.Entry.CurrentHitPoints   = NewCurrentHP
        self.Entry.TemporaryHitPoints = TempHP
        return NewCurrentHP

    def set_hp(self, Value: int) -> int:
        self.Entry.CurrentHitPoints = max(0, min(self.Entry.MaxHitPoints, Value))
        return self.Entry.CurrentHitPoints

    def set_temp_hp(self, Value: int) -> int:
        self.Entry.TemporaryHitPoints = max(0, Value)
        return self.Entry.TemporaryHitPoints

    def add_condition(self, ConditionName: str) -> None:
        CleanCondition: str = ConditionName.strip()
        if CleanCondition and (CleanCondition not in self.Entry.Conditions):
            self.Entry.Conditions.append(CleanCondition)

    def remove_condition(self, ConditionName: str) -> bool:
        CleanCondition: str = ConditionName.strip().lower()
        for ExistingCondition in list(self.Entry.Conditions):
            if (ExistingCondition.lower() == CleanCondition):
                self.Entry.Conditions.remove(ExistingCondition)
                return True

        return False

    def has_condition(self, ConditionName: str) -> bool:
        CleanCondition: str = ConditionName.strip().lower()
        return any(ExistingCondition.lower() == CleanCondition for ExistingCondition in self.Entry.Conditions)

    def add_effect(self, EffectName: str, DurationRounds: Typing.Optional[int] = None, PassiveEffectsMap: Typing.Optional[dict[str, Typing.Any]] = None) -> None:
        if not hasattr(self.Entry, "Effects"):
            self.Entry.__dict__["Effects"] = []

        ActiveEffectsList: list[dict[str, Typing.Any]] = getattr(self.Entry, "Effects", [])
        NewEffect: dict[str, Typing.Any] = {
            "Name"          : EffectName,
            "DurationRounds": DurationRounds,
            "PassiveEffects": PassiveEffectsMap if (PassiveEffectsMap is not None) else {}
        }
        ActiveEffectsList.append(NewEffect)

    def remove_effect(self, EffectName: str) -> bool:
        if not hasattr(self.Entry, "Effects"):
            return False

        ActiveEffectsList: list[dict[str, Typing.Any]] = getattr(self.Entry, "Effects", [])
        CleanName        : str                         = EffectName.strip().lower()
        for EffectItem in list(ActiveEffectsList):
            if (str(EffectItem.get("Name", "")).lower() == CleanName):
                ActiveEffectsList.remove(EffectItem)
                return True

        return False

    def has_effect(self, EffectName: str) -> bool:
        if not hasattr(self.Entry, "Effects"):
            return False

        ActiveEffectsList: list[dict[str, Typing.Any]] = getattr(self.Entry, "Effects", [])
        CleanName        : str                         = EffectName.strip().lower()
        return any(str(EffectItem.get("Name", "")).lower() == CleanName for EffectItem in ActiveEffectsList)

