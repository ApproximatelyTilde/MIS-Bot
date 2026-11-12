import typing                             as Typing
import unittest.mock                      as MockLibrary
import pytest                             as Pytest
import Runtime.Services.MGT2EStateService as MGT2EState

class TestMGT2EStateService:
    def TestCalculateCharacteristicModifierThresholds(self) -> None:
        ServiceInstance: MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        assert (ServiceInstance.CalculateCharacteristicModifier(0) == -3)
        assert (ServiceInstance.CalculateCharacteristicModifier(-1) == -3)
        assert (ServiceInstance.CalculateCharacteristicModifier(1) == -2)
        assert (ServiceInstance.CalculateCharacteristicModifier(2) == -2)
        assert (ServiceInstance.CalculateCharacteristicModifier(3) == -1)
        assert (ServiceInstance.CalculateCharacteristicModifier(5) == -1)
        assert (ServiceInstance.CalculateCharacteristicModifier(6) == 0)
        assert (ServiceInstance.CalculateCharacteristicModifier(8) == 0)
        assert (ServiceInstance.CalculateCharacteristicModifier(9) == 1)
        assert (ServiceInstance.CalculateCharacteristicModifier(11) == 1)
        assert (ServiceInstance.CalculateCharacteristicModifier(12) == 2)
        assert (ServiceInstance.CalculateCharacteristicModifier(14) == 2)
        assert (ServiceInstance.CalculateCharacteristicModifier(15) == 3)
        assert (ServiceInstance.CalculateCharacteristicModifier(18) == 3)

    def TestNormalizeCharacteristicName(self) -> None:
        ServiceInstance: MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        assert (ServiceInstance.NormalizeCharacteristicName("str") == "Strength")
        assert (ServiceInstance.NormalizeCharacteristicName("dex") == "Dexterity")
        assert (ServiceInstance.NormalizeCharacteristicName("end") == "Endurance")
        assert (ServiceInstance.NormalizeCharacteristicName("int") == "Intelligence")
        assert (ServiceInstance.NormalizeCharacteristicName("edu") == "Education")
        assert (ServiceInstance.NormalizeCharacteristicName("soc") == "SocialStanding")
        assert (ServiceInstance.NormalizeCharacteristicName("social") == "SocialStanding")

    def TestGetDefaultCharacteristicForSkill(self) -> None:
        ServiceInstance: MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        assert (ServiceInstance.GetDefaultCharacteristicForSkill("pilot") == "Dexterity")
        assert (ServiceInstance.GetDefaultCharacteristicForSkill("medic") == "Education")
        assert (ServiceInstance.GetDefaultCharacteristicForSkill("carouse") == "SocialStanding")
        assert (ServiceInstance.GetDefaultCharacteristicForSkill("melee") == "Strength")
        assert (ServiceInstance.GetDefaultCharacteristicForSkill("survival") == "Endurance")
        assert (ServiceInstance.GetDefaultCharacteristicForSkill("gun combat (slug)") == "Dexterity")

    def TestIsSkillTrained(self) -> None:
        ServiceInstance : MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        SkillsDictionary: dict[str, int]               = {
            "pilot"             : 1,
            "gun combat (slug)" : 2,
            "jack of all trades": 1,
            "medic"             : -1
        }

        assert (ServiceInstance.IsSkillTrained(SkillsDictionary, "pilot") is True)
        assert (ServiceInstance.IsSkillTrained(SkillsDictionary, "gun combat (slug)") is True)
        assert (ServiceInstance.IsSkillTrained(SkillsDictionary, "gun combat") is True)
        assert (ServiceInstance.IsSkillTrained(SkillsDictionary, "jack of all trades") is False)
        assert (ServiceInstance.IsSkillTrained(SkillsDictionary, "medic") is False)
        assert (ServiceInstance.IsSkillTrained(SkillsDictionary, "athletics") is False)

    def TestEvaluateRollSuccessAndEffect(self) -> None:
        ServiceInstance: MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        Outcome        : MGT2EState.MGT2ERollOutcome  = ServiceInstance.EvaluateRoll(Modifier = 3, NetBoons = 0, TargetDifficulty = 8)

        assert (len(Outcome.DiceRolls) == 2)
        assert (len(Outcome.KeptRolls) == 2)
        assert (Outcome.ModifierTotal == 3)
        assert (Outcome.Total == Outcome.BaseTotal + 3)
        assert (Outcome.Effect == Outcome.Total - 8)
        assert (Outcome.IsSuccess == (Outcome.Effect >= 0))
        assert (len(Outcome.BreakdownString) > 0)
        assert (len(Outcome.OutcomeDescription) > 0)

    def TestEvaluateRollBoonsAndBanes(self) -> None:
        ServiceInstance: MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        BoonOutcome    : MGT2EState.MGT2ERollOutcome  = ServiceInstance.EvaluateRoll(Modifier = 0, NetBoons = 1, TargetDifficulty = 8)
        assert (len(BoonOutcome.DiceRolls) == 3)
        assert (len(BoonOutcome.KeptRolls) == 2)

        BaneOutcome    : MGT2EState.MGT2ERollOutcome  = ServiceInstance.EvaluateRoll(Modifier = 0, NetBoons = -1, TargetDifficulty = 8)
        assert (len(BaneOutcome.DiceRolls) == 3)
        assert (len(BaneOutcome.KeptRolls) == 2)

    @Pytest.mark.asyncio
    async def TestResolveActiveCharacterPrioritizesPrimaryCharacter(self) -> None:
        MockPlatform: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPlatform.FetchCharactersByDiscordID = MockLibrary.AsyncMock(return_value = [{"ID": "other-1", "Name": "Pirate Raider", "GameSystem": "MGT2E", "EntityType": "Other"}, {"ID": "ship-1", "Name": "Beowulf", "GameSystem": "MGT2E", "EntityType": "Vehicle"}, {"ID": "char-1", "Name": "Kira", "GameSystem": "MGT2E", "EntityType": "Character"}])
        ServiceInstance: MGT2EState.MGT2EStateService  = MGT2EState.MGT2EStateService(PlatformClientInstance = MockPlatform)
        Resolved: Typing.Optional[dict[str, Typing.Any]] = await ServiceInstance.ResolveActiveCharacter("111", "222")
        assert (Resolved is not None)
        assert (Resolved["ID"] == "char-1")

    def TestFormatVehicleSheetEmbed(self) -> None:
        ServiceInstance: MGT2EState.MGT2EStateService = MGT2EState.MGT2EStateService()
        VehicleRecord  : dict[str, Typing.Any]        = {
            "ID"        : "v1",
            "Name"      : "Free Trader",
            "EntityType": "Vehicle",
            "DetailData": {
                "VehicleType"  : "Type-A",
                "HullPoints"   : 35,
                "MaxHullPoints": 40,
                "Armor"        : 4,
                "Thrust"       : 1,
                "JumpRating"   : 1,
                "Fuel"         : 20,
                "MaxFuel"      : 20
            }
        }
        Embed: Typing.Any = ServiceInstance.FormatSheetEmbed(VehicleRecord)
        assert ("Free Trader" in str(Embed.title))
        assert ("Hull:** 35/40" in str(Embed.description))
