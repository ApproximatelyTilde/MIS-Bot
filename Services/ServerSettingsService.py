import typing                  as Typing
import pydantic                as Pydantic
import Configuration.Config    as Config
import Services.DebugService   as Debug
import Services.PlatformClient as PlatformClient

class ServerSettingsModel(Pydantic.BaseModel):
    GuildID               : str
    CommandPrefixDND5E    : str                  = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E
    CommandPrefixMGT2E    : str                  = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E
    RuleSetEnforcementMode: str                  = "Standard"
    MacroMasterRoleID     : Typing.Optional[str] = None

class ServerSettingsService:
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.PlatformClient: PlatformClient.MISPlatformClient       = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.MISPlatformClient()
        self.SettingsCache : dict[str, ServerSettingsModel]         = dict()

    async def GetServerSettings(self, GuildID: Typing.Optional[str | int]) -> ServerSettingsModel:
        if (GuildID is None):
            DefaultModel: ServerSettingsModel = ServerSettingsModel(GuildID = "DirectMessage", CommandPrefixDND5E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E, CommandPrefixMGT2E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E, RuleSetEnforcementMode = "Standard", MacroMasterRoleID = None)
            return DefaultModel

        StringGuildID: str = str(GuildID)
        if StringGuildID in self.SettingsCache:
            return self.SettingsCache[StringGuildID]

        try:
            FetchedPayload: dict[str, Typing.Any] = await self.PlatformClient.FetchServerSettings(StringGuildID)
            SettingsRecord: ServerSettingsModel   = ServerSettingsModel(GuildID = str(FetchedPayload.get("GuildID", StringGuildID)), CommandPrefixDND5E = str(FetchedPayload["CommandPrefixDND5E"]), CommandPrefixMGT2E = str(FetchedPayload["CommandPrefixMGT2E"]), RuleSetEnforcementMode = str(FetchedPayload.get("RuleSetEnforcementMode", "Standard")), MacroMasterRoleID = FetchedPayload.get("MacroMasterRoleID"))
            self.SettingsCache[StringGuildID]     = SettingsRecord
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Loaded Server Settings into Cache: GuildID={StringGuildID}")
            return SettingsRecord

        except Exception as FetchError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Fetch Server Settings for GuildID={StringGuildID}: {str(FetchError)}")
            DefaultSettings: ServerSettingsModel = ServerSettingsModel(GuildID = StringGuildID, CommandPrefixDND5E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E, CommandPrefixMGT2E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E, RuleSetEnforcementMode = "Standard", MacroMasterRoleID = None)
            return DefaultSettings

    async def UpdateServerSettings(self, GuildID: str | int, CommandPrefixDND5E: Typing.Optional[str] = None, CommandPrefixMGT2E: Typing.Optional[str] = None, RuleSetEnforcementMode: Typing.Optional[str] = None, MacroMasterRoleID: Typing.Optional[str] = None) -> ServerSettingsModel:
        StringGuildID: str                 = str(GuildID)
        CurrentSettings: ServerSettingsModel = await self.GetServerSettings(StringGuildID)

        TargetDND5EPrefix: str                  = CommandPrefixDND5E if (CommandPrefixDND5E is not None) else CurrentSettings.CommandPrefixDND5E
        TargetMGT2EPrefix: str                  = CommandPrefixMGT2E if (CommandPrefixMGT2E is not None) else CurrentSettings.CommandPrefixMGT2E
        TargetEnforcementMode: str                  = RuleSetEnforcementMode if (RuleSetEnforcementMode is not None) else CurrentSettings.RuleSetEnforcementMode
        TargetRoleID         : Typing.Optional[str] = MacroMasterRoleID if (MacroMasterRoleID is not None) else CurrentSettings.MacroMasterRoleID

        SavePayload: dict[str, Typing.Any] = {
            "CommandPrefixDND5E": TargetDND5EPrefix,
            "CommandPrefixMGT2E": TargetMGT2EPrefix,
            "RuleSetEnforcementMode": TargetEnforcementMode,
            "MacroMasterRoleID"     : TargetRoleID
        }

        SavedPayload: dict[str, Typing.Any] = await self.PlatformClient.SaveServerSettings(StringGuildID, SavePayload)
        UpdatedModel: ServerSettingsModel   = ServerSettingsModel(GuildID = str(SavedPayload.get("GuildID", StringGuildID)), CommandPrefixDND5E = str(SavedPayload["CommandPrefixDND5E"]), CommandPrefixMGT2E = str(SavedPayload["CommandPrefixMGT2E"]), RuleSetEnforcementMode = str(SavedPayload.get("RuleSetEnforcementMode", TargetEnforcementMode)), MacroMasterRoleID = SavedPayload.get("MacroMasterRoleID", TargetRoleID))
        self.SettingsCache[StringGuildID]   = UpdatedModel
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Server Settings in Cache: GuildID={StringGuildID}")
        return UpdatedModel

    async def ResetServerSettings(self, GuildID: str | int) -> ServerSettingsModel:
        StringGuildID: str                 = str(GuildID)
        ResetPayload : dict[str, Typing.Any] = {
            "CommandPrefixDND5E": Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E,
            "CommandPrefixMGT2E": Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E,
            "RuleSetEnforcementMode": "Standard",
            "MacroMasterRoleID"     : None
        }

        SavedPayload: dict[str, Typing.Any] = await self.PlatformClient.SaveServerSettings(StringGuildID, ResetPayload)
        UpdatedModel: ServerSettingsModel   = ServerSettingsModel(GuildID = str(SavedPayload.get("GuildID", StringGuildID)), CommandPrefixDND5E = str(SavedPayload["CommandPrefixDND5E"]), CommandPrefixMGT2E = str(SavedPayload["CommandPrefixMGT2E"]), RuleSetEnforcementMode = str(SavedPayload.get("RuleSetEnforcementMode", "Standard")), MacroMasterRoleID = SavedPayload.get("MacroMasterRoleID"))
        self.SettingsCache[StringGuildID]   = UpdatedModel
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Reset Server Settings in Cache: GuildID={StringGuildID}")
        return UpdatedModel

    def GetCachedDND5EPrefix(self, GuildID: Typing.Optional[str | int]) -> str:
        if (GuildID is None):
            return Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E

        StringGuildID: str = str(GuildID)
        if StringGuildID in self.SettingsCache:
            return self.SettingsCache[StringGuildID].CommandPrefixDND5E

        return Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E

    def GetCachedMGT2EPrefix(self, GuildID: Typing.Optional[str | int]) -> str:
        if (GuildID is None):
            return Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E

        StringGuildID: str = str(GuildID)
        if StringGuildID in self.SettingsCache:
            return self.SettingsCache[StringGuildID].CommandPrefixMGT2E

        return Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E
