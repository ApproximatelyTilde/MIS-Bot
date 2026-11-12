import math                             as MathLibrary
import typing                           as Typing
import Services.DebugService            as Debug
import Services.EncounterManagerService as EncounterManager

def ApplyHealingToCombatant(Combatant: EncounterManager.CombatantEntry, HealAmount: int, Overheal: bool = False) -> tuple[int, int, int, str]:
    if (HealAmount <= 0):
        return (0, 0, Combatant.CurrentHitPoints, "No healing applied")

    MissingHP: int = max(0, Combatant.MaxHitPoints - Combatant.CurrentHitPoints)

    if not Overheal:
        ActualHealed: int               = min(HealAmount, MissingHP)
        Combatant.CurrentHitPoints     += ActualHealed
        Narrative   : str               = f"Healed for {ActualHealed} HP"
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Healed Combatant: Name=\"{Combatant.Name}\", Amount={ActualHealed}, Overheal=False")
        return (ActualHealed, 0, Combatant.CurrentHitPoints, Narrative)

    ActualHealed: int   = min(HealAmount, MissingHP)
    OverhealAmount: int = max(0, HealAmount - MissingHP)
    Combatant.CurrentHitPoints = Combatant.MaxHitPoints

    if (OverhealAmount > 0):
        if (OverhealAmount > Combatant.TemporaryHitPoints):
            Combatant.TemporaryHitPoints = OverhealAmount

        Narrative = f"Healed for {ActualHealed} HP (Overheal: +{OverhealAmount} Temp HP)"

    else:
        Narrative = f"Healed for {ActualHealed} HP"

    Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Healed Combatant: Name=\"{Combatant.Name}\", Healed={ActualHealed}, OverhealAmount={OverhealAmount}")
    return (ActualHealed, OverhealAmount, Combatant.CurrentHitPoints, Narrative)

def ApplyDamageToCombatant(Combatant: EncounterManager.CombatantEntry, ModifiedDamage: int) -> tuple[int, int, int]:
    if (ModifiedDamage <= 0):
        return (0, Combatant.CurrentHitPoints, Combatant.TemporaryHitPoints)

    CurrentHP      : int = Combatant.CurrentHitPoints
    TempHP         : int = Combatant.TemporaryHitPoints
    DamageRemaining: int = ModifiedDamage

    if (TempHP > 0):
        AbsorbedAmount   = min(TempHP, DamageRemaining)
        TempHP          -= AbsorbedAmount
        DamageRemaining -= AbsorbedAmount

    NewHP: int = max(0, CurrentHP - DamageRemaining)
    Combatant.CurrentHitPoints   = NewHP
    Combatant.TemporaryHitPoints = TempHP
    Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Damaged Combatant: Name=\"{Combatant.Name}\", Dmg={ModifiedDamage}, HP={NewHP}, TempHP={TempHP}")
    return (ModifiedDamage, NewHP, TempHP)
