import math                                     as MathLibrary
import re                                       as RegularExpressions
import typing                                   as Typing
import Services.DebugService                    as Debug
import Services.DiceService                     as DiceService
import Services.EncounterManagerService         as EncounterManager
import Services.Automation.AutomationModels     as Models
import Services.Automation.EffectContext        as EffectContext
import Services.Automation.Effects.IEffectHandler as IEffectHandler

SLOT_LEVEL_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"\[(\d+)\]")

class AutomationEngine:
    def __init__(self, DiceRoller: Typing.Optional[DiceService.DiceRollerService] = None) -> None:
        self.DiceRoller   : DiceService.DiceRollerService   = DiceRoller if (DiceRoller is not None) else DiceService.DiceRollerService()
        self.EffectHandler: IEffectHandler.IEffectHandler   = IEffectHandler.IEffectHandler(self.DiceRoller)

    def RunAutomation(self, Action: Models.ActionDocument, Context: EffectContext.AutomationContext) -> Models.AutomationExecutionResult:
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Running Action Automation: Name=\"{Action.Name}\", Caster=\"{Context.GetCasterName()}\"")
        for EffectNodeItem in Action.Automation:
            self.ExecuteNode(EffectNodeItem, CurrentTarget = None, Context = Context)

        return Context.Result

    def ExecuteNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        NodeType: Models.AutomationEffectType = Node.Type

        if (NodeType == Models.AutomationEffectType.Target):
            self.ExecuteTargetNode(Node, Context)

        elif (NodeType == Models.AutomationEffectType.Attack):
            self.ExecuteAttackNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.Save):
            self.ExecuteSaveNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.Damage):
            self.ExecuteDamageNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.TempHP):
            self.ExecuteTempHPNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.Heal):
            self.ExecuteHealNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.Condition):
            self.ExecuteConditionNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.InitiativeEffect):
            self.ExecuteInitiativeEffectNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.Counter):
            self.ExecuteCounterNode(Node, CurrentTarget, Context)

        elif (NodeType == Models.AutomationEffectType.Text):
            self.ExecuteTextNode(Node, CurrentTarget, Context)

    def ExecuteTargetNode(self, Node: Models.EffectNode, Context: EffectContext.AutomationContext) -> None:
        TargetMode   : str                                   = str(Node.Target or "each").lower()
        ChildEffects : list[Models.EffectNode]               = Node.Effects or []
        ChosenTargets: list[EncounterManager.CombatantEntry] = []

        if (TargetMode == "self"):
            CasterName: str = Context.GetCasterName().lower()
            if (Context.Encounter is not None):
                for Candidate in Context.Encounter.Combatants:
                    if (Candidate.Name.lower() == CasterName):
                        ChosenTargets.append(Candidate)
                        break

        else:
            ChosenTargets = list(Context.Targets)

        for SingleTarget in ChosenTargets:
            for ChildNode in ChildEffects:
                self.ExecuteNode(ChildNode, CurrentTarget = SingleTarget, Context = Context)

    def ExecuteAttackNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (CurrentTarget is None):
            return

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)

        BaseBonus    : int = 5
        CasterEntry  : Typing.Optional[EncounterManager.CombatantEntry] = None
        if isinstance(Context.Caster, EncounterManager.CombatantEntry):
            CasterEntry = Context.Caster

        if (Node.Amount is not None):
            try:
                BaseBonus = int(Node.Amount)

            except ValueError:
                pass

        elif hasattr(Context.Caster, "stats"):
            BaseBonus = int(getattr(Context.Caster, "pb", 2)) + int(Context.Caster.stats.get("strength_mod", 3))

        PassiveBonus : int = self.EffectHandler.CalculateAttackBonus(CasterEntry)
        TotalBonus   : int = BaseBonus + PassiveBonus

        BaseAdvantage: int = Context.Arguments.adv()
        NetAdvantage : int = self.EffectHandler.CalculateNetAdvantage(CasterEntry, CurrentTarget, BaseAdvantage)

        AdvFlag: str = "-adv" if (NetAdvantage > 0) else ("-dis" if (NetAdvantage < 0) else "")
        Formula: str = f"1d20{'+' if TotalBonus >= 0 else ''}{TotalBonus} {AdvFlag}".strip()

        RollResult: DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(Formula)
        TargetOutcome.AttackTotal = RollResult.Total

        EffectiveAC: int = CurrentTarget.ArmorClass + self.EffectHandler.CalculateArmorClassModifier(CurrentTarget)
        TargetOutcome.TargetArmorClass = EffectiveAC

        IsCriticalHit : bool = RollResult.IsCriticalHit
        IsCriticalMiss: bool = RollResult.IsCriticalMiss
        IsHit         : bool = (not IsCriticalMiss) and (IsCriticalHit or (RollResult.Total >= EffectiveAC))

        if IsCriticalHit:
            TargetOutcome.HitStatus = "Critical Hit"

        elif IsCriticalMiss:
            TargetOutcome.HitStatus = "Critical Miss"

        elif IsHit:
            TargetOutcome.HitStatus = "Hit"

        else:
            TargetOutcome.HitStatus = "Miss"

        BranchNodes: list[Models.EffectNode] = (Node.Hit or []) if IsHit else (Node.Miss or [])
        for ChildNode in BranchNodes:
            self.ExecuteNode(ChildNode, CurrentTarget = CurrentTarget, Context = Context)

    def ExecuteSaveNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (CurrentTarget is None):
            return

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)

        TargetStat: str = str(Node.Stat or "dex").lower()
        TargetDC  : int = int(Node.DC or 15)
        TargetOutcome.SaveTargetDC = TargetDC

        SaveBonus: int = 0
        if isinstance(CurrentTarget, EncounterManager.CombatantEntry):
            if (CurrentTarget.MonsterData is not None) and isinstance(CurrentTarget.MonsterData, dict):
                SavesDict = CurrentTarget.MonsterData.get("save", {})
                if TargetStat in SavesDict:
                    try:
                        SaveBonus = int(str(SavesDict[TargetStat]).replace("+", ""))

                    except ValueError:
                        pass

                elif TargetStat in CurrentTarget.MonsterData:
                    Score     = int(CurrentTarget.MonsterData.get(TargetStat, 10))
                    SaveBonus = (Score - 10) // 2

            for Mod in self.EffectHandler.CollectAllPassiveModifiers(CurrentTarget):
                if (Mod.SaveBonus is not None):
                    try:
                        SaveBonus += int(Mod.SaveBonus.strip().lstrip("+"))

                    except ValueError:
                        pass

        Formula: str = f"1d20{'+' if SaveBonus >= 0 else ''}{SaveBonus}"
        SaveRoll : DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(Formula)
        TargetOutcome.SaveResultTotal = SaveRoll.Total

        SaveSucceeded: bool = (SaveRoll.Total >= TargetDC)
        TargetOutcome.SaveSucceeded = SaveSucceeded

        BranchNodes: list[Models.EffectNode] = (Node.Success or []) if SaveSucceeded else (Node.Fail or [])
        for ChildNode in BranchNodes:
            self.ExecuteNode(ChildNode, CurrentTarget = CurrentTarget, Context = Context)

    def ExecuteDamageNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (CurrentTarget is None):
            return

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)

        DamageFormula: str = str(Node.Damage or "1d8")
        if (Node.Higher is not None) and (Context.SpellLevel > 1):
            SlotLevelKey: str = str(Context.SpellLevel)
            if SlotLevelKey in Node.Higher:
                DamageFormula = Node.Higher[SlotLevelKey]

        DamageRoll: DiceService.RollOutcome = self.DiceRoller.EvaluateRoll(DamageFormula)
        RawDamage : int                     = DamageRoll.Total

        ModifiedDamage, LogSuffix = self.EffectHandler.ApplyDamageModifiers(CurrentTarget, RawDamage, Node.DamageType)
        TargetOutcome.DamageDealt += ModifiedDamage
        TargetOutcome.DamageType   = Node.DamageType

        CurrentHP: int = CurrentTarget.CurrentHitPoints
        TempHP   : int = CurrentTarget.TemporaryHitPoints

        if (ModifiedDamage > 0):
            DamageRemaining: int = ModifiedDamage
            if (TempHP > 0):
                AbsorbedDamage = min(TempHP, DamageRemaining)
                TempHP         -= AbsorbedDamage
                DamageRemaining -= AbsorbedDamage

            CurrentTarget.CurrentHitPoints   = max(0, CurrentHP - DamageRemaining)
            CurrentTarget.TemporaryHitPoints = TempHP

            ConcWarning: Typing.Optional[str] = self.EffectHandler.HandleDamageConcentrationCheck(CurrentTarget, ModifiedDamage)
            if (ConcWarning is not None):
                TargetOutcome.NarrativeMessages.append(ConcWarning)

    def ExecuteTempHPNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (CurrentTarget is None):
            return

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)
        AmountFormula: str                        = str(Node.Amount or "5")
        RollOutcome  : DiceService.RollOutcome   = self.DiceRoller.EvaluateRoll(AmountFormula)
        GrantedAmount: int                        = RollOutcome.Total

        if (GrantedAmount > CurrentTarget.TemporaryHitPoints):
            CurrentTarget.TemporaryHitPoints = GrantedAmount
            TargetOutcome.TemporaryHPGranted = GrantedAmount

    def ExecuteHealNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (CurrentTarget is None):
            return

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)
        AmountFormula: str                        = str(Node.Amount or "5")
        RollOutcome  : DiceService.RollOutcome   = self.DiceRoller.EvaluateRoll(AmountFormula)
        HealAmount   : int                        = RollOutcome.Total

        CurrentTarget.CurrentHitPoints = min(CurrentTarget.MaxHitPoints, CurrentTarget.CurrentHitPoints + HealAmount)
        TargetOutcome.NarrativeMessages.append(f"Healed for {HealAmount} HP")

    def ExecuteConditionNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (CurrentTarget is None) or (Node.Condition is None):
            return

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)
        ConditionName: str                        = Node.Condition.strip()

        if ConditionName not in CurrentTarget.Conditions:
            CurrentTarget.Conditions.append(ConditionName)
            TargetOutcome.ConditionsApplied.append(ConditionName)

    def ExecuteInitiativeEffectNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        TargetRecipient: Typing.Optional[EncounterManager.CombatantEntry] = CurrentTarget
        EffectName     : str                                             = str(Node.Name or "Effect")

        if (TargetRecipient is None) and (Context.Encounter is not None):
            CasterName: str = Context.GetCasterName().lower()
            for Candidate in Context.Encounter.Combatants:
                if (Candidate.Name.lower() == CasterName):
                    TargetRecipient = Candidate
                    break

        if (TargetRecipient is None):
            return

        IsConcentration: bool = bool(Node.Concentration or False)
        AttachedEffect = self.EffectHandler.AttachEffect(
            Combatant       = TargetRecipient,
            EffectName      = EffectName,
            DurationRounds  = Node.Duration,
            PassiveEffects  = Node.PassiveEffects,
            IsConcentration = IsConcentration,
            CasterName      = Context.GetCasterName()
        )

        TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(TargetRecipient.Name)
        TargetOutcome.EffectsAttached.append(EffectName)

        if IsConcentration:
            Context.Result.ConcentrationCast = True
            Context.Result.ConcentrationName = EffectName

    def ExecuteCounterNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        CounterName: Typing.Optional[str] = Node.Counter
        if (CounterName is None):
            return

        DeltaValue: int = int(Node.Amount or 1)
        if hasattr(Context.Caster, "mod_cc"):
            try:
                Context.Caster.mod_cc(CounterName, DeltaValue)

            except Exception:
                pass

    def ExecuteTextNode(self, Node: Models.EffectNode, CurrentTarget: Typing.Optional[EncounterManager.CombatantEntry], Context: EffectContext.AutomationContext) -> None:
        if (Node.Text is not None):
            if (CurrentTarget is not None):
                TargetOutcome: Models.TargetEffectOutcome = Context.GetOrCreateTargetOutcome(CurrentTarget.Name)
                TargetOutcome.NarrativeMessages.append(Node.Text)

            else:
                Context.LogGlobalMessage(Node.Text)
