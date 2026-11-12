import typing                                              as Typing
import unittest.mock                                       as MockLibrary
import pytest                                              as Pytest
import Runtime.Services.CharacterStateService              as CharacterState
import Runtime.Application.Commands.DND5E.TrackingCommands as TrackingCommands

class TestCharacterStateService:
    def TestBuildContextKey(self) -> None:
        ServiceInstance: CharacterState.CharacterStateService = CharacterState.CharacterStateService()
        ContextKey     : str                                  = ServiceInstance.BuildContextKey(DiscordUserID = 12345, ChannelID = 67890)
        assert (ContextKey == "12345:67890")

    def TestSetAndGetActiveCharacter(self) -> None:
        ServiceInstance: CharacterState.CharacterStateService = CharacterState.CharacterStateService()
        ServiceInstance.SetActiveCharacter(DiscordUserID = 100, ChannelID = 200, CharacterID = "char-alpha")

        assert (ServiceInstance.GetActiveCharacterID(DiscordUserID = 100, ChannelID = 200) == "char-alpha")
        assert (ServiceInstance.GetActiveCharacterID(DiscordUserID = 100, ChannelID = 999) == "char-alpha")
        assert (ServiceInstance.GetActiveCharacterID(DiscordUserID = 999, ChannelID = 200) is None)

    def TestGetAbilityModifierCalculations(self) -> None:
        ServiceInstance: CharacterState.CharacterStateService = CharacterState.CharacterStateService()
        DetailData     : dict[str, Typing.Any]                = {
            "AbilityScores": {
                "Strength"    : {
                    "TotalScore": 16,
                    "Modifier"  : 3
                },
                "Dexterity"   : {
                    "TotalScore": 10,
                    "Modifier"  : 0
                },
                "Constitution": {
                    "TotalScore": 8,
                    "Modifier"  : -1
                }
            }
        }

        NameStr, ScoreStr, ModStr = ServiceInstance.GetAbilityModifier(DetailData, "str")
        assert (NameStr == "Strength")
        assert (ScoreStr == 16)
        assert (ModStr == 3)

        NameDex, ScoreDex, ModDex = ServiceInstance.GetAbilityModifier(DetailData, "dexterity")
        assert (NameDex == "Dexterity")
        assert (ScoreDex == 10)
        assert (ModDex == 0)

        NameCon, ScoreCon, ModCon = ServiceInstance.GetAbilityModifier(DetailData, "con")
        assert (NameCon == "Constitution")
        assert (ScoreCon == 8)
        assert (ModCon == -1)

    def TestGetSavingThrowModifier(self) -> None:
        ServiceInstance: CharacterState.CharacterStateService = CharacterState.CharacterStateService()
        DetailData     : dict[str, Typing.Any]                = {
            "ProficiencyBonus"        : 3,
            "AbilityScores"           : {
                "Wisdom"    : {
                    "TotalScore": 14,
                    "Modifier"  : 2
                },
                "Charisma"  : {
                    "TotalScore": 10,
                    "Modifier"  : 0
                }
            },
            "SavingThrowProficiencies": [{"AbilityName": "Wisdom", "IsProficient": True, "BonusModifier": 0}, {"AbilityName": "Charisma", "IsProficient": False, "BonusModifier": 1}]
        }

        NameWis, TotalSaveWis, IsProfWis = ServiceInstance.GetSavingThrowModifier(DetailData, "wis")
        assert (NameWis == "Wisdom")
        assert (IsProfWis is True)
        assert (TotalSaveWis == 5)

        NameCha, TotalSaveCha, IsProfCha = ServiceInstance.GetSavingThrowModifier(DetailData, "cha")
        assert (NameCha == "Charisma")
        assert (IsProfCha is False)
        assert (TotalSaveCha == 1)

    def TestHasJackOfAllTradesDetection(self) -> None:
        ServiceInstance: CharacterState.CharacterStateService = CharacterState.CharacterStateService()

        BardDetail: dict[str, Typing.Any] = {
            "Classes" : [{"ClassName": "Bard", "Level": 2}],
            "Features": []
        }
        assert (ServiceInstance.HasJackOfAllTrades(BardDetail) is True)

        FeatureDetail: dict[str, Typing.Any] = {
            "Classes" : [{"ClassName": "Rogue", "Level": 3}],
            "Features": [{"Name": "Jack of All Trades Feature"}]
        }
        assert (ServiceInstance.HasJackOfAllTrades(FeatureDetail) is True)

        NonBardDetail: dict[str, Typing.Any] = {
            "Classes" : [{"ClassName": "Fighter", "Level": 5}],
            "Features": []
        }
        assert (ServiceInstance.HasJackOfAllTrades(NonBardDetail) is False)

    @Pytest.mark.asyncio
    async def TestResolveActiveCharacterAutoSelectsOnlyPrimaryCharacter(self) -> None:
        MockPlatform: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPlatform.FetchCharactersByDiscordID = MockLibrary.AsyncMock(return_value = [{"ID": "comp-1", "Name": "Familiar", "GameSystem": "DND5E", "EntityType": "Companion"}, {"ID": "char-1", "Name": "Aldric", "GameSystem": "DND5E", "EntityType": "Character"}])
        ServiceInstance: CharacterState.CharacterStateService = CharacterState.CharacterStateService(PlatformClientInstance = MockPlatform)
        Resolved: Typing.Optional[dict[str, Typing.Any]]      = await ServiceInstance.ResolveActiveCharacter("111", "222")
        assert (Resolved is not None)
        assert (Resolved["ID"] == "char-1")

    @Pytest.mark.asyncio
    async def TestTrackingCommandsShareBotStateAndPersist(self) -> None:
        MockPlatform: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPlatform.PersistCharacterState  = MockLibrary.AsyncMock(return_value = {"ID": "char-1"})
        SharedState : CharacterState.CharacterStateService = CharacterState.CharacterStateService(PlatformClientInstance = MockPlatform)
        CharacterRecord  : dict[str, Typing.Any]                = {
            "ID"        : "char-1",
            "Name"      : "Aldric",
            "GameSystem": "DND5E",
            "EntityType": "Character",
            "DetailData": {"HitPoints": {
                "CurrentHitPoints"  : 20,
                "MaxHitPoints"      : 25,
                "TemporaryHitPoints": 0
            }}
        }
        SharedState.CharacterCache["char-1"] = CharacterRecord
        SharedState.SetActiveCharacter("111", "222", "char-1")

        MockBot: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockBot.CharacterStateService  = SharedState
        MockBot.EncounterManager       = None

        CogInstance: TrackingCommands.TrackingCommands = TrackingCommands.TrackingCommands(MockBot)
        assert (CogInstance.StateService is SharedState)

        MockContext       : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.author                        = MockLibrary.MagicMock(id = 111)
        MockContext.channel                       = MockLibrary.MagicMock(id = 222)
        MockContext.prefix                        = "!"
        MockContext.send                          = MockLibrary.AsyncMock()
        await CogInstance.HitPointsCommand.callback(CogInstance, MockContext, ArgumentsText = "-5")
        MockPlatform.PersistCharacterState.assert_awaited_once()
        assert (CharacterRecord["DetailData"]["HitPoints"]["CurrentHitPoints"] == 15)
