import typing                                   as Typing
import pytest                                   as Pytest
import Runtime.Services.CharacterStateService   as CharacterState
import Runtime.Services.MGT2EStateService       as MGT2EState
import Runtime.Services.EncounterManagerService as EncounterManager
import Runtime.Services.TargetResolverService   as TargetResolver

class TestTargetResolverService:
    def TestExtractMentionedUserID(self) -> None:
        Resolver: TargetResolver.TargetResolverService = TargetResolver.TargetResolverService()
        assert (Resolver.ExtractMentionedUserID("<@1234567890>") == "1234567890")
        assert (Resolver.ExtractMentionedUserID("<@!9876543210>") == "9876543210")
        assert (Resolver.ExtractMentionedUserID("Goblin") is None)

    @Pytest.mark.asyncio
    async def TestSystemMismatchGuardBlocksDNDOnMGT2E(self) -> None:
        SharedContext: dict[str, str]                       = {}
        DNDService   : CharacterState.CharacterStateService = CharacterState.CharacterStateService(ActiveSystemByContext = SharedContext)
        MGT2EService : MGT2EState.MGT2EStateService         = MGT2EState.MGT2EStateService(ActiveSystemByContext = SharedContext)
        Resolver     : TargetResolver.TargetResolverService = TargetResolver.TargetResolverService(CharacterStateInstance = DNDService, MGT2EStateInstance = MGT2EService, ActiveSystemByContext = SharedContext)

        DND5ECharacter: dict[str, Typing.Any] = {
            "ID"        : "dnd-1",
            "Name"      : "Aragorn",
            "GameSystem": "DND5E",
            "DetailData": {"HitPoints": {
                "CurrentHitPoints": 30,
                "MaxHitPoints"    : 30
            }, "ArmorClass": {
                "TotalArmorClass": 16
            }}
        }
        DNDService.CharacterCache["dnd-1"] = DND5ECharacter
        DNDService.SetActiveCharacter("42", "999", "dnd-1")

        IsValid, ResolvedRec, ErrorMsg = await Resolver.ValidateSystemGuard("42", "999", "MGT2E")
        assert (IsValid is False)
        assert (ResolvedRec is None)
        assert (ErrorMsg is not None) and ("Aragorn" in ErrorMsg)

    @Pytest.mark.asyncio
    async def TestResolveMentionOutsideInitiativeUsesCharacterNameAndSyntheticCombatant(self) -> None:
        SharedContext: dict[str, str]                       = {}
        DNDService   : CharacterState.CharacterStateService = CharacterState.CharacterStateService(ActiveSystemByContext = SharedContext)
        MGT2EService : MGT2EState.MGT2EStateService         = MGT2EState.MGT2EStateService(ActiveSystemByContext = SharedContext)
        Resolver     : TargetResolver.TargetResolverService = TargetResolver.TargetResolverService(CharacterStateInstance = DNDService, MGT2EStateInstance = MGT2EService, ActiveSystemByContext = SharedContext)

        DND5ECharacter: dict[str, Typing.Any] = {
            "ID"        : "dnd-char-1",
            "Name"      : "Kaelen Vance",
            "GameSystem": "DND5E",
            "EntityType": "Character",
            "DetailData": {
                "HitPoints" : {
                    "CurrentHitPoints": 22,
                    "MaxHitPoints"    : 28
                },
                "ArmorClass": {
                    "TotalArmorClass": 17
                }
            }
        }
        DNDService.CharacterCache["dnd-char-1"] = DND5ECharacter
        DNDService.SetActiveCharacter("555111", "888", "dnd-char-1")

        TargetsList: list[TargetResolver.ResolvedTarget] = await Resolver.ResolveTargets(["<@!555111>"], GameSystem = "DND5E", ChannelID = "888", Encounter = None)
        assert (len(TargetsList) == 1)
        TargetItem: TargetResolver.ResolvedTarget = TargetsList[0]
        assert (TargetItem.DisplayName == "Kaelen Vance")
        assert ("555111" not in TargetItem.DisplayName)
        assert (TargetItem.MentionedUserID == "555111")
        assert (TargetItem.IsSynthetic is True)
        assert (TargetItem.Combatant is not None)
        assert (TargetItem.Combatant.ArmorClass == 17)
        assert (TargetItem.Combatant.CurrentHitPoints == 22)

    @Pytest.mark.asyncio
    async def TestResolveMentionInsideInitiativeMatchesControllerCombatant(self) -> None:
        SharedContext: dict[str, str]                       = {}
        DNDService   : CharacterState.CharacterStateService = CharacterState.CharacterStateService(ActiveSystemByContext = SharedContext)
        MGT2EService : MGT2EState.MGT2EStateService         = MGT2EState.MGT2EStateService(ActiveSystemByContext = SharedContext)
        Resolver     : TargetResolver.TargetResolverService = TargetResolver.TargetResolverService(CharacterStateInstance = DNDService, MGT2EStateInstance = MGT2EService, ActiveSystemByContext = SharedContext)

        TravellerCharacter: dict[str, Typing.Any] = {
            "ID"        : "mgt-char-1",
            "Name"      : "Major Elena",
            "GameSystem": "MGT2E",
            "EntityType": "Character",
            "DetailData": {"Characteristics": {
                "Endurance": 9,
                "Strength" : 8,
                "Dexterity": 10
            }}
        }
        MGT2EService.CharacterCache["mgt-char-1"] = TravellerCharacter
        MGT2EService.SetActiveCharacter("777222", "888", "mgt-char-1")

        Encounter: EncounterManager.CombatEncounter = EncounterManager.CombatEncounter(ChannelID = "888", GameSystem = "MGT2E")
        Encounter.AddCombatant(EncounterManager.CombatantEntry(ID = "mgt-char-1", Name = "Major Elena", Initiative = 10, CurrentHitPoints = 9, MaxHitPoints = 9, ArmorProtection = 4, ControllerDiscordID = "777222", CharacterID = "mgt-char-1"))

        TargetsList: list[TargetResolver.ResolvedTarget] = await Resolver.ResolveTargets(["<@777222>"], GameSystem = "MGT2E", ChannelID = "888", Encounter = Encounter)
        assert (len(TargetsList) == 1)
        assert (TargetsList[0].DisplayName == "Major Elena")
        assert (TargetsList[0].IsSynthetic is False)
        assert (TargetsList[0].Combatant is not None)
        assert (TargetsList[0].Combatant.ArmorProtection == 4)
