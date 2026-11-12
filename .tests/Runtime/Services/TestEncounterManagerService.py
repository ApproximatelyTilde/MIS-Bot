import typing                                   as Typing
import Runtime.Services.EncounterManagerService as EncounterManager

class TestEncounterManagerService:
    def TestCombatantEntryEffectsFieldNormalization(self) -> None:
        Combatant: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(ID = "c1", Name = "Goblin Archer", Initiative = 14, CurrentHitPoints = 7, MaxHitPoints = 7, Effects = [{"name": "Hidden", "duration": 1}])
        assert (len(Combatant.ActiveEffects) == 1)
        assert (Combatant.Effects[0]["name"] == "Hidden")

        Combatant.Effects = [{"name": "Poisoned", "duration": 2}]
        assert (Combatant.ActiveEffects[0]["name"] == "Poisoned")

    def TestCombatEncounterGroupInitiativeSyncAndSorting(self) -> None:
        Encounter: EncounterManager.CombatEncounter = EncounterManager.CombatEncounter(ChannelID = "12345")

        OrcA: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(ID = "o1", Name = "Orc Warrior A", Initiative = 12, CurrentHitPoints = 15, MaxHitPoints = 15, GroupName = "Orcs", PassivePerception = 10)
        OrcB: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(ID = "o2", Name = "Orc Warrior B", Initiative = 18, CurrentHitPoints = 15, MaxHitPoints = 15, GroupName = "Orcs", PassivePerception = 10)
        Hero: EncounterManager.CombatantEntry = EncounterManager.CombatantEntry(ID = "h1", Name = "Paladin Hero", Initiative = 15, CurrentHitPoints = 28, MaxHitPoints = 28, PassivePerception = 14)

        Encounter.AddCombatant(OrcA)
        Encounter.AddCombatant(OrcB)
        Encounter.AddCombatant(Hero)

        assert (OrcA.Initiative == 18)
        assert (OrcB.Initiative == 18)

        assert (len(Encounter.Combatants) == 3)
        assert (Encounter.Combatants[0].GroupName == "Orcs")
        assert (Encounter.Combatants[1].GroupName == "Orcs")
        assert (Encounter.Combatants[2].Name == "Paladin Hero")

    def TestCombatEncounterTurnAdvancementAndWrapping(self) -> None:
        Encounter : EncounterManager.CombatEncounter = EncounterManager.CombatEncounter(ChannelID = "23456")
        FirstHero : EncounterManager.CombatantEntry  = EncounterManager.CombatantEntry(ID = "1", Name = "Hero One", Initiative = 20, CurrentHitPoints = 10, MaxHitPoints = 10)
        SecondHero: EncounterManager.CombatantEntry  = EncounterManager.CombatantEntry(ID = "2", Name = "Hero Two", Initiative = 10, CurrentHitPoints = 10, MaxHitPoints = 10)

        Encounter.AddCombatant(FirstHero)
        Encounter.AddCombatant(SecondHero)

        assert (Encounter.RoundNumber == 1)
        assert (Encounter.ActiveCombatantIndex == 0)

        ActiveCombatant, RoundNum = Encounter.AdvanceTurn()
        assert (ActiveCombatant is not None)
        assert (ActiveCombatant.ID == "2")
        assert (RoundNum == 1)

        ActiveCombatantWrap, RoundNumWrap = Encounter.AdvanceTurn()
        assert (ActiveCombatantWrap is not None)
        assert (ActiveCombatantWrap.ID == "1")
        assert (RoundNumWrap == 2)

        ActiveCombatantPrev, RoundNumPrev = Encounter.PreviousTurn()
        assert (ActiveCombatantPrev is not None)
        assert (ActiveCombatantPrev.ID == "2")
        assert (RoundNumPrev == 1)

    def TestCombatEncounterFindAndRemove(self) -> None:
        Encounter: EncounterManager.CombatEncounter = EncounterManager.CombatEncounter(ChannelID = "34567")
        Fighter  : EncounterManager.CombatantEntry  = EncounterManager.CombatantEntry(ID = "f1", Name = "Aura Fighter", Initiative = 15, CurrentHitPoints = 20, MaxHitPoints = 20)
        Wizard   : EncounterManager.CombatantEntry  = EncounterManager.CombatantEntry(ID = "w1", Name = "Wise Wizard", Initiative = 12, CurrentHitPoints = 14, MaxHitPoints = 14)

        Encounter.AddCombatant(Fighter)
        Encounter.AddCombatant(Wizard)

        FoundByID: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant("w1")
        assert (FoundByID is not None)
        assert (FoundByID.Name == "Wise Wizard")

        FoundBySubstring: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.FindCombatant("fighter")
        assert (FoundBySubstring is not None)
        assert (FoundBySubstring.ID == "f1")

        RemovedCombatant: Typing.Optional[EncounterManager.CombatantEntry] = Encounter.RemoveCombatant("1")
        assert (RemovedCombatant is not None)
        assert (len(Encounter.Combatants) == 1)

    def TestEncounterManagerServiceLifecycle(self) -> None:
        ManagerService  : EncounterManager.EncounterManagerService = EncounterManager.EncounterManagerService()
        CreatedEncounter: EncounterManager.CombatEncounter         = ManagerService.CreateEncounter(ChannelID = "999888", GuildID = "111")
        assert (CreatedEncounter.ChannelID == "999888")
        assert (CreatedEncounter.IsActive is True)

        RetrievedEncounter: Typing.Optional[EncounterManager.CombatEncounter] = ManagerService.GetEncounter("999888")
        assert (RetrievedEncounter is not None)
        assert (RetrievedEncounter.ChannelID == "999888")

        EndedEncounter: Typing.Optional[EncounterManager.CombatEncounter] = ManagerService.EndEncounter("999888")
        assert (EndedEncounter is not None)
        assert (EndedEncounter.IsActive is False)
        assert (ManagerService.GetEncounter("999888") is None)

    def TestMGT2EEncounterEmbedFormatting(self) -> None:
        ManagerService: EncounterManager.EncounterManagerService = EncounterManager.EncounterManagerService()
        Encounter     : EncounterManager.CombatEncounter         = ManagerService.CreateEncounter(ChannelID = "555000", GameSystem = "MGT2E")
        Marine        : EncounterManager.CombatantEntry          = EncounterManager.CombatantEntry(ID = "m1", Name = "Marine Bob", Initiative = 9, CurrentHitPoints = 10, MaxHitPoints = 10, ArmorProtection = 6, Characteristics = {"Endurance": 8, "Strength": 9, "Dexterity": 10}, MaxCharacteristics = {"Endurance": 10, "Strength": 9, "Dexterity": 10})
        ScoutShip     : EncounterManager.CombatantEntry          = EncounterManager.CombatantEntry(ID = "s1", Name = "Beowulf", Initiative = 8, CurrentHitPoints = 80, MaxHitPoints = 80, ArmorProtection = 4, EntityType = "Vehicle", VehicleStats = {"HullPoints": 72, "MaxHullPoints": 80})

        Encounter.AddCombatant(Marine)
        Encounter.AddCombatant(ScoutShip)
        Embed     : Typing.Any = ManagerService.FormatEncounterEmbed(Encounter, CommandPrefix = ".")
        FieldValue: str        = str(Embed.fields[0].value)
        assert ("END 8/10" in FieldValue)
        assert ("Armor 6" in FieldValue)
        assert ("Hull 72/80" in FieldValue)
        assert ("HP |" not in FieldValue)
        assert ("AC " not in FieldValue)

    def TestPopcornInitiativePassingAndRoundWrap(self) -> None:
        Encounter: EncounterManager.CombatEncounter = EncounterManager.CombatEncounter(ChannelID = "777000", GameSystem = "DND5E", InitiativeMode = "Popcorn")
        HeroA    : EncounterManager.CombatantEntry  = EncounterManager.CombatantEntry(ID = "a1", Name = "Alice", Initiative = 10, CurrentHitPoints = 20, MaxHitPoints = 20)
        HeroB    : EncounterManager.CombatantEntry  = EncounterManager.CombatantEntry(ID = "b1", Name = "Bob", Initiative = 20, CurrentHitPoints = 20, MaxHitPoints = 20)
        Encounter.AddCombatant(HeroA)
        Encounter.AddCombatant(HeroB)

        assert (Encounter.Combatants[0].ID == "a1")
        assert (Encounter.RemainingInRound == ["a1", "b1"])

        Next1, Round1, Wrapped1 = Encounter.PassTurn("a1")
        assert (Next1 is not None) and (Next1.ID == "a1")
        assert (Round1 == 1)
        assert (Wrapped1 is False)
        assert (Encounter.RemainingInRound == ["b1"])

        AlreadyActed, _, _ = Encounter.PassTurn("a1")
        assert (AlreadyActed is None)

        Next2, Round2, Wrapped2 = Encounter.PassTurn("b1")
        assert (Next2 is not None) and (Next2.ID == "b1")
        assert (Round2 == 1)
        assert (Wrapped2 is False)
        assert (Encounter.RemainingInRound == [])

        Next3, Round3, Wrapped3 = Encounter.PassTurn("b1")
        assert (Next3 is not None) and (Next3.ID == "b1")
        assert (Round3 == 2)
        assert (Wrapped3 is True)
        assert (Encounter.RemainingInRound == ["a1"])
