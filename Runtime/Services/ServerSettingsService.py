import time                            as TimeLibrary
import typing                          as Typing
import pydantic                        as Pydantic
import Runtime.Configuration.Config    as Config
import Runtime.Services.DebugService   as Debug
import Runtime.Services.PlatformClient as PlatformClient

DEFAULT_SETTINGS_TTL_SECONDS: float = 300.0

class ServerSettingsModel(Pydantic.BaseModel):
    GuildID               : str
    CommandPrefixDND5E    : str                  = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E
    CommandPrefixMGT2E    : str                  = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E
    RuleSetEnforcementMode: str                  = "Standard"
    MacroMasterRoleID     : Typing.Optional[str] = None

    @property
    def CommandPrefixDND(self) -> str:
        return self.CommandPrefixDND5E

    @property
    def CommandPrefixTraveller(self) -> str:
        return self.CommandPrefixMGT2E

class ServerSettingsService:
    def __init__(self, PlatformClientInstance: Typing.Optional[PlatformClient.TallyPlatformClient] = None) -> None:
        self.PlatformClient         : PlatformClient.TallyPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.TallyPlatformClient()
        self.SettingsCache          : dict[str, ServerSettingsModel]     = dict()
        self.SettingsCacheTimestamps: dict[str, float]                   = dict()

    async def GetServerSettings(self, GuildID: Typing.Optional[str | int]) -> ServerSettingsModel:
        if (GuildID is None):
            DefaultModel: ServerSettingsModel = ServerSettingsModel(GuildID = "DirectMessage", CommandPrefixDND5E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E, CommandPrefixMGT2E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E, RuleSetEnforcementMode = "Standard", MacroMasterRoleID = None)
            return DefaultModel

        StringGuildID: str   = str(GuildID)
        CurrentTime  : float = TimeLibrary.monotonic()
        if (StringGuildID in self.SettingsCache):
            CachedTimestamp: float = self.SettingsCacheTimestamps.get(StringGuildID, CurrentTime)
            if ((CurrentTime - CachedTimestamp) < DEFAULT_SETTINGS_TTL_SECONDS):
                return self.SettingsCache[StringGuildID]

        try:
            FetchedPayload: dict[str, Typing.Any] = await self.PlatformClient.FetchServerSettings(StringGuildID)
            DNDPrefix     : str                   = str(FetchedPayload.get("CommandPrefixDND5E") or FetchedPayload.get("CommandPrefixDND") or Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)
            MGTPrefix     : str                   = str(FetchedPayload.get("CommandPrefixMGT2E") or FetchedPayload.get("CommandPrefixTraveller") or Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E)
            SettingsRecord: ServerSettingsModel   = ServerSettingsModel(GuildID = str(FetchedPayload.get("GuildID", StringGuildID)), CommandPrefixDND5E = DNDPrefix, CommandPrefixMGT2E = MGTPrefix, RuleSetEnforcementMode = str(FetchedPayload.get("RuleSetEnforcementMode", "Standard")), MacroMasterRoleID = FetchedPayload.get("MacroMasterRoleID"))
            self.SettingsCache[StringGuildID]           = SettingsRecord
            self.SettingsCacheTimestamps[StringGuildID] = CurrentTime
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Loaded Server Settings into Cache: GuildID={StringGuildID}")
            return SettingsRecord

        except Exception as FetchError:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Fetch Server Settings for GuildID={StringGuildID}: {str(FetchError)}")
            if (StringGuildID in self.SettingsCache):
                return self.SettingsCache[StringGuildID]

            DefaultSettings: ServerSettingsModel = ServerSettingsModel(GuildID = StringGuildID, CommandPrefixDND5E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E, CommandPrefixMGT2E = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E, RuleSetEnforcementMode = "Standard", MacroMasterRoleID = None)
            return DefaultSettings

    async def UpdateServerSettings(self, GuildID: str | int, CommandPrefixDND5E: Typing.Optional[str] = None, CommandPrefixMGT2E: Typing.Optional[str] = None, RuleSetEnforcementMode: Typing.Optional[str] = None, MacroMasterRoleID: Typing.Optional[str] = None, CommandPrefixDND: Typing.Optional[str] = None, CommandPrefixTraveller: Typing.Optional[str] = None) -> ServerSettingsModel:
        StringGuildID        : str                  = str(GuildID)
        CurrentSettings      : ServerSettingsModel  = await self.GetServerSettings(StringGuildID)
        TargetDND5EPrefix    : str                  = CommandPrefixDND5E if (CommandPrefixDND5E is not None) else (CommandPrefixDND if (CommandPrefixDND is not None) else CurrentSettings.CommandPrefixDND5E)
        TargetMGT2EPrefix    : str                  = CommandPrefixMGT2E if (CommandPrefixMGT2E is not None) else (CommandPrefixTraveller if (CommandPrefixTraveller is not None) else CurrentSettings.CommandPrefixMGT2E)
        TargetEnforcementMode: str                  = RuleSetEnforcementMode if (RuleSetEnforcementMode is not None) else CurrentSettings.RuleSetEnforcementMode
        TargetRoleID         : Typing.Optional[str] = MacroMasterRoleID if (MacroMasterRoleID is not None) else CurrentSettings.MacroMasterRoleID

        SavePayload: dict[str, Typing.Any] = {
            "CommandPrefixDND5E"    : TargetDND5EPrefix,
            "CommandPrefixMGT2E"    : TargetMGT2EPrefix,
            "CommandPrefixDND"      : TargetDND5EPrefix,
            "CommandPrefixTraveller": TargetMGT2EPrefix,
            "RuleSetEnforcementMode": TargetEnforcementMode,
            "MacroMasterRoleID"     : TargetRoleID
        }

        SavedPayload: dict[str, Typing.Any] = await self.PlatformClient.SaveServerSettings(StringGuildID, SavePayload)
        SavedDND5E  : str                   = str(SavedPayload.get("CommandPrefixDND5E") or SavedPayload.get("CommandPrefixDND") or TargetDND5EPrefix)
        SavedMGT2E  : str                   = str(SavedPayload.get("CommandPrefixMGT2E") or SavedPayload.get("CommandPrefixTraveller") or TargetMGT2EPrefix)
        UpdatedModel: ServerSettingsModel   = ServerSettingsModel(GuildID = str(SavedPayload.get("GuildID", StringGuildID)), CommandPrefixDND5E = SavedDND5E, CommandPrefixMGT2E = SavedMGT2E, RuleSetEnforcementMode = str(SavedPayload.get("RuleSetEnforcementMode", TargetEnforcementMode)), MacroMasterRoleID = SavedPayload.get("MacroMasterRoleID", TargetRoleID))
        self.SettingsCache[StringGuildID]           = UpdatedModel
        self.SettingsCacheTimestamps[StringGuildID] = TimeLibrary.monotonic()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Updated Server Settings in Cache: GuildID={StringGuildID}")
        return UpdatedModel

    async def ResetServerSettings(self, GuildID: str | int) -> ServerSettingsModel:
        StringGuildID: str                 = str(GuildID)
        ResetPayload : dict[str, Typing.Any] = {
            "CommandPrefixDND5E"    : Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E,
            "CommandPrefixMGT2E"    : Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E,
            "CommandPrefixDND"      : Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E,
            "CommandPrefixTraveller": Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E,
            "RuleSetEnforcementMode": "Standard",
            "MacroMasterRoleID"     : None
        }

        SavedPayload: dict[str, Typing.Any] = await self.PlatformClient.SaveServerSettings(StringGuildID, ResetPayload)
        SavedDND5E  : str                   = str(SavedPayload.get("CommandPrefixDND5E") or SavedPayload.get("CommandPrefixDND") or Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)
        SavedMGT2E  : str                   = str(SavedPayload.get("CommandPrefixMGT2E") or SavedPayload.get("CommandPrefixTraveller") or Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E)
        UpdatedModel: ServerSettingsModel   = ServerSettingsModel(GuildID = str(SavedPayload.get("GuildID", StringGuildID)), CommandPrefixDND5E = SavedDND5E, CommandPrefixMGT2E = SavedMGT2E, RuleSetEnforcementMode = str(SavedPayload.get("RuleSetEnforcementMode", "Standard")), MacroMasterRoleID = SavedPayload.get("MacroMasterRoleID"))
        self.SettingsCache[StringGuildID]           = UpdatedModel
        self.SettingsCacheTimestamps[StringGuildID] = TimeLibrary.monotonic()
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

    def GetCachedDNDPrefix(self, GuildID: Typing.Optional[str | int]) -> str:
        return self.GetCachedDND5EPrefix(GuildID)

    def GetCachedTravellerPrefix(self, GuildID: Typing.Optional[str | int]) -> str:
        return self.GetCachedMGT2EPrefix(GuildID)
