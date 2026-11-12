import unittest.mock                          as MockLibrary
import pytest                                 as Pytest
import Runtime.Configuration.Config           as Config
import Runtime.Services.ServerSettingsService as ServerSettings

class TestServerSettingsService:
    def TestServerSettingsModelProperties(self) -> None:
        ModelInstance: ServerSettings.ServerSettingsModel = ServerSettings.ServerSettingsModel(GuildID = "123456789", CommandPrefixDND5E = "!dnd", CommandPrefixMGT2E = ".mgt", RuleSetEnforcementMode = "Standard", MacroMasterRoleID = "998877")
        assert (ModelInstance.CommandPrefixDND == "!dnd")
        assert (ModelInstance.CommandPrefixTraveller == ".mgt")
        assert (ModelInstance.MacroMasterRoleID == "998877")

    @Pytest.mark.asyncio
    async def TestGetServerSettingsDirectMessage(self) -> None:
        ServiceInstance: ServerSettings.ServerSettingsService = ServerSettings.ServerSettingsService()
        ResultSettings : ServerSettings.ServerSettingsModel   = await ServiceInstance.GetServerSettings(None)
        assert (ResultSettings.GuildID == "DirectMessage")
        assert (ResultSettings.CommandPrefixDND5E == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)
        assert (ResultSettings.CommandPrefixMGT2E == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E)

    @Pytest.mark.asyncio
    async def TestGetServerSettingsFetchedAndCached(self) -> None:
        MockPlatformClient: MockLibrary.AsyncMock             = MockLibrary.AsyncMock()
        MockPlatformClient.FetchServerSettings.return_value   = {
            "GuildID"               : "888888",
            "CommandPrefixDND5E"    : "$dnd",
            "CommandPrefixMGT2E"    : "$mgt",
            "RuleSetEnforcementMode": "ModernOnly",
            "MacroMasterRoleID"     : "333444"
        }
        ServiceInstance   : ServerSettings.ServerSettingsService = ServerSettings.ServerSettingsService(PlatformClientInstance = MockPlatformClient)

        FirstResult: ServerSettings.ServerSettingsModel = await ServiceInstance.GetServerSettings("888888")
        assert (FirstResult.CommandPrefixDND5E == "$dnd")
        assert (FirstResult.RuleSetEnforcementMode == "ModernOnly")
        assert (MockPlatformClient.FetchServerSettings.call_count == 1)

        SecondResult: ServerSettings.ServerSettingsModel = await ServiceInstance.GetServerSettings("888888")
        assert (SecondResult.CommandPrefixDND5E == "$dnd")
        assert (MockPlatformClient.FetchServerSettings.call_count == 1)

    @Pytest.mark.asyncio
    async def TestGetServerSettingsPlatformErrorFallback(self) -> None:
        MockPlatformClient: MockLibrary.AsyncMock             = MockLibrary.AsyncMock()
        MockPlatformClient.FetchServerSettings.side_effect    = RuntimeError("Platform Connection Failed")
        ServiceInstance   : ServerSettings.ServerSettingsService = ServerSettings.ServerSettingsService(PlatformClientInstance = MockPlatformClient)

        FallbackResult: ServerSettings.ServerSettingsModel = await ServiceInstance.GetServerSettings("999999")
        assert (FallbackResult.GuildID == "999999")
        assert (FallbackResult.CommandPrefixDND5E == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)
        assert (FallbackResult.CommandPrefixMGT2E == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E)

    @Pytest.mark.asyncio
    async def TestUpdateServerSettings(self) -> None:
        MockPlatformClient: MockLibrary.AsyncMock             = MockLibrary.AsyncMock()
        MockPlatformClient.FetchServerSettings.return_value   = {
            "GuildID": "777777"
        }
        MockPlatformClient.SaveServerSettings.return_value    = {
            "GuildID"               : "777777",
            "CommandPrefixDND5E"    : "/dnd",
            "CommandPrefixMGT2E"    : "/mgt",
            "RuleSetEnforcementMode": "Standard",
            "MacroMasterRoleID"     : "111222"
        }
        ServiceInstance   : ServerSettings.ServerSettingsService = ServerSettings.ServerSettingsService(PlatformClientInstance = MockPlatformClient)

        UpdatedModel: ServerSettings.ServerSettingsModel = await ServiceInstance.UpdateServerSettings(GuildID = "777777", CommandPrefixDND5E = "/dnd", CommandPrefixMGT2E = "/mgt", MacroMasterRoleID = "111222")
        assert (UpdatedModel.CommandPrefixDND5E == "/dnd")
        assert (UpdatedModel.CommandPrefixMGT2E == "/mgt")
        assert (ServiceInstance.GetCachedDND5EPrefix("777777") == "/dnd")
        assert (ServiceInstance.GetCachedMGT2EPrefix("777777") == "/mgt")

    @Pytest.mark.asyncio
    async def TestResetServerSettings(self) -> None:
        MockPlatformClient: MockLibrary.AsyncMock             = MockLibrary.AsyncMock()
        MockPlatformClient.SaveServerSettings.return_value    = {
            "GuildID"           : "666666",
            "CommandPrefixDND5E": Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E,
            "CommandPrefixMGT2E": Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E
        }
        ServiceInstance   : ServerSettings.ServerSettingsService = ServerSettings.ServerSettingsService(PlatformClientInstance = MockPlatformClient)

        ResetModel: ServerSettings.ServerSettingsModel = await ServiceInstance.ResetServerSettings("666666")
        assert (ResetModel.CommandPrefixDND5E == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)
        assert (ResetModel.CommandPrefixMGT2E == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E)
