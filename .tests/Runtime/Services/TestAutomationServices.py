import Runtime.Services.Automation              as Automation
import Runtime.Services.EncounterManagerService as EncounterManager

class TestAutomationServices:
    def TestCustomActionActivationTypeEnum(self) -> None:
        assert (Automation.AutomationModelsModule.CustomActionActivationType.Action.value == "Action")
        assert (Automation.AutomationModelsModule.CustomActionActivationType.BonusAction.value == "BonusAction")
        assert (Automation.AutomationModelsModule.CustomActionActivationType.Reaction.value == "Reaction")

    def TestAutomationEffectTypeEnum(self) -> None:
        assert (Automation.AutomationEffectType.Target.value == "Target")
        assert (Automation.AutomationEffectType.Attack.value == "Attack")
        assert (Automation.AutomationEffectType.Damage.value == "Damage")
        assert (Automation.AutomationEffectType.Save.value == "Save")

    def TestActionDocumentAndEffectNodeValidation(self) -> None:
        TargetEffect: Automation.EffectNode     = Automation.EffectNode(Type = Automation.AutomationEffectType.Damage, Damage = "3d6", DamageType = "Fire")
        ParentNode  : Automation.EffectNode     = Automation.EffectNode(Type = Automation.AutomationEffectType.Target, Target = "each", Effects = [TargetEffect])
        Document    : Automation.ActionDocument = Automation.ActionDocument(Name = "Burning Hands", ActivationType = Automation.AutomationModelsModule.CustomActionActivationType.Action, Automation = [ParentNode])

        assert (Document.Name == "Burning Hands")
        assert (len(Document.Automation) == 1)
        assert (Document.Automation[0].Type == Automation.AutomationEffectType.Target)
        assert (Document.Automation[0].Effects is not None)
        assert (len(Document.Automation[0].Effects) == 1)
        assert (Document.Automation[0].Effects[0].Damage == "3d6")

    def TestAutomationContextTargetOutcomesAndLogging(self) -> None:
        TargetCombatant: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(ID = "target-1", Name = "Goblin Skirmisher", Initiative = 12, CurrentHitPoints = 10, MaxHitPoints = 10)
        ContextInstance: Automation.AutomationContext    = Automation.AutomationContext(Caster = {"Name": "Wizard"}, Targets = [TargetCombatant], ActionName = "Firebolt")

        assert (ContextInstance.GetCasterName() == "Wizard")

        FirstOutcome: Automation.TargetEffectOutcome = ContextInstance.GetOrCreateTargetOutcome("Goblin Skirmisher")
        FirstOutcome.HitStatus                       = "Hit"

        SecondOutcome: Automation.TargetEffectOutcome = ContextInstance.GetOrCreateTargetOutcome("Goblin Skirmisher")
        assert (SecondOutcome.HitStatus == "Hit")
        assert (len(ContextInstance.Result.TargetOutcomes) == 1)

        ContextInstance.LogGlobalMessage("The spell explodes in flames.")
        assert (len(ContextInstance.Result.GlobalNarrative) == 1)

    def TestConcentrationManagerDCAndStateLifecycle(self) -> None:
        ManagerInstance: Automation.ConcentrationManager = Automation.ConcentrationManager()
        assert (ManagerInstance.CalculateConcentrationSaveDC(0) == 10)
        assert (ManagerInstance.CalculateConcentrationSaveDC(14) == 10)
        assert (ManagerInstance.CalculateConcentrationSaveDC(26) == 13)

        Combatant: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(ID = "c-caster", Name = "Cleric", Initiative = 10, CurrentHitPoints = 30, MaxHitPoints = 30)
        assert (ManagerInstance.IsConcentrating(Combatant) is False)

        DropNoticeFirst: str | None = ManagerInstance.SetConcentration(None, Combatant, "Bless")
        assert (DropNoticeFirst is None)
        assert (ManagerInstance.IsConcentrating(Combatant) is True)
        assert (ManagerInstance.GetConcentrationName(Combatant) == "Bless")

        DropNoticeSecond: str | None = ManagerInstance.SetConcentration(None, Combatant, "Shield of Faith")
        assert (DropNoticeSecond is not None)
        assert ("dropped concentration on **Bless**" in DropNoticeSecond)
        assert (ManagerInstance.GetConcentrationName(Combatant) == "Shield of Faith")

        DroppedName: str | None = ManagerInstance.DropConcentration(None, Combatant)
        assert (DroppedName == "Shield of Faith")
        assert (ManagerInstance.IsConcentrating(Combatant) is False)
