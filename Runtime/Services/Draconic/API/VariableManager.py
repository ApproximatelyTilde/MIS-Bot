import re                                       as RegularExpressions
import typing                                   as Typing
import Runtime.Services.DebugService            as Debug
import Runtime.Services.PlatformClient          as PlatformClient
import Runtime.Services.Draconic.SandboxedScope as SandboxedScope

UUID_REGEX_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

class GvarCallableDictionary(SandboxedScope.DraconicDictionary):
    def __call__(self, KeyValue: Typing.Any, DefaultValue: Typing.Any = None) -> Typing.Any:
        return self.get(KeyValue, DefaultValue)

class VariableManager:
    def __init__(self, CharacterRecord: Typing.Optional[dict[str, Typing.Any]] = None, UserID: str | int = "", GuildID: Typing.Optional[str | int] = None, PlatformClientInstance: Typing.Optional[PlatformClient.TallyPlatformClient] = None, UserVariables: Typing.Optional[dict[str, Typing.Any]] = None, ServerVariables: Typing.Optional[dict[str, Typing.Any]] = None, GlobalVariables: Typing.Optional[dict[str, Typing.Any]] = None) -> None:
        self.CharacterRecord: Typing.Optional[dict[str, Typing.Any]] = CharacterRecord
        self.UserID         : str                                   = str(UserID)
        self.GuildID        : Typing.Optional[str]                  = str(GuildID) if (GuildID is not None) else None
        self.PlatformClient : PlatformClient.TallyPlatformClient      = PlatformClientInstance if (PlatformClientInstance is not None) else PlatformClient.TallyPlatformClient()

        CharacterVars: dict[str, Typing.Any]       = dict(CharacterRecord.get("DetailData", dict()).get("Variables", dict())) if (CharacterRecord is not None) else dict()
        self.cvar    : SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary(CharacterVars)
        self.uvar    : SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary(UserVariables or dict())
        self.svar    : SandboxedScope.DraconicDictionary = SandboxedScope.DraconicDictionary(ServerVariables or dict())
        self.gvar    : GvarCallableDictionary            = GvarCallableDictionary(GlobalVariables or dict())

    async def LoadPlatformVariables(self) -> None:
        if self.UserID:
            try:
                UserVarsPayload: dict[str, Typing.Any] = await self.PlatformClient.FetchUserVariables(self.UserID)
                LoadedUserVars : dict[str, Typing.Any] = UserVarsPayload.get("Variables", {})
                self.uvar.update(LoadedUserVars)

            except Exception as UserVariableError:
                Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Could not load user variables: {str(UserVariableError)}")

        if self.GuildID:
            try:
                ServerVarsPayload: dict[str, Typing.Any] = await self.PlatformClient.FetchServerVariables(self.GuildID)
                LoadedServerVars : dict[str, Typing.Any] = ServerVarsPayload.get("Variables", {})
                self.svar.update(LoadedServerVars)

            except Exception as ServerVariableError:
                Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Could not load server variables: {str(ServerVariableError)}")

    def GetVariable(self, VariableName: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        CleanKey: str = VariableName.strip()

        if CleanKey in self.cvar:
            return self.cvar[CleanKey]

        elif CleanKey in self.uvar:
            return self.uvar[CleanKey]

        elif CleanKey in self.svar:
            return self.svar[CleanKey]

        elif CleanKey in self.gvar:
            return self.gvar[CleanKey]

        return DefaultValue

    def GetCVAR(self, Name: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        return self.cvar.get(Name, DefaultValue)

    def SetCVAR(self, Name: str, Value: Typing.Any) -> None:
        self.cvar[Name] = Value
        if (self.CharacterRecord is not None):
            DetailData: dict[str, Typing.Any] = self.CharacterRecord.setdefault("DetailData", {})
            Variables : dict[str, Typing.Any] = DetailData.setdefault("Variables", {})
            Variables[Name] = Value

    def DeleteCVAR(self, Name: str) -> bool:
        if Name in self.cvar:
            del self.cvar[Name]
            if (self.CharacterRecord is not None):
                DetailData: dict[str, Typing.Any] = self.CharacterRecord.get("DetailData", {})
                Variables : dict[str, Typing.Any] = DetailData.get("Variables", {})
                if Name in Variables:
                    del Variables[Name]

            return True

        return False

    def GetUVAR(self, Name: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        return self.uvar.get(Name, DefaultValue)

    def SetUVAR(self, Name: str, Value: Typing.Any) -> None:
        self.uvar[Name] = Value

    def DeleteUVAR(self, Name: str) -> bool:
        if Name in self.uvar:
            del self.uvar[Name]
            return True

        return False

    def GetSVAR(self, Name: str, DefaultValue: Typing.Any = None) -> Typing.Any:
        return self.svar.get(Name, DefaultValue)

    def SetSVAR(self, Name: str, Value: Typing.Any) -> None:
        self.svar[Name] = Value

    def DeleteSVAR(self, Name: str) -> bool:
        if Name in self.svar:
            del self.svar[Name]
            return True

        return False

    def GetGVAR(self, GvarID: str) -> Typing.Optional[str]:
        return self.gvar.get(GvarID)

    def SetGVAR(self, GvarID: str, Content: str) -> None:
        self.gvar[GvarID] = Content

    async def SaveCVARToPlatform(self, Name: str, Value: Typing.Any) -> None:
        self.SetCVAR(Name, Value)
        if (self.CharacterRecord is not None):
            CharacterID: str = str(self.CharacterRecord.get("ID", ""))
            if CharacterID:
                try:
                    await self.PlatformClient.SetCharacterVariables(CharacterID, {Name: Value})

                except Exception as Error:
                    Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to persist CVAR: {str(Error)}")

    async def SaveUVARToPlatform(self, Name: str, Value: Typing.Any) -> None:
        self.SetUVAR(Name, Value)
        if self.UserID:
            try:
                await self.PlatformClient.SaveUserVariable(self.UserID, Name, Value)

            except Exception as Error:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to persist UVAR: {str(Error)}")

    async def DeleteUVARFromPlatform(self, Name: str) -> bool:
        IsDeleted: bool = self.DeleteUVAR(Name)
        if self.UserID:
            try:
                await self.PlatformClient.SaveUserVariable(self.UserID, Name, None)

            except Exception as Error:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to delete UVAR on platform: {str(Error)}")

        return IsDeleted

    async def SaveSVARToPlatform(self, Name: str, Value: Typing.Any) -> None:
        self.SetSVAR(Name, Value)
        if self.GuildID:
            try:
                await self.PlatformClient.SaveServerVariable(self.GuildID, Name, Value)

            except Exception as Error:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to persist SVAR: {str(Error)}")

    async def DeleteSVARFromPlatform(self, Name: str) -> bool:
        IsDeleted: bool = self.DeleteSVAR(Name)
        if self.GuildID:
            try:
                await self.PlatformClient.SaveServerVariable(self.GuildID, Name, None)

            except Exception as Error:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to delete SVAR on platform: {str(Error)}")

        return IsDeleted

    async def FetchGVARFromPlatform(self, GvarID: str) -> Typing.Optional[str]:
        if GvarID in self.gvar:
            return self.gvar[GvarID]

        try:
            ResultData: dict[str, Typing.Any] = await self.PlatformClient.FetchGlobalVariable(GvarID)
            Content   : str                   = str(ResultData.get("Content", ""))
            self.gvar[GvarID]                 = Content
            return Content

        except Exception as Error:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to fetch GVAR '{GvarID}': {str(Error)}")
            return None

    async def CreateGVAROnPlatform(self, Content: str, Name: Typing.Optional[str] = None) -> str:
        CreatedID: str = await self.PlatformClient.CreateGlobalVariable(Content, Name = Name, OwnerID = self.UserID)
        self.gvar[CreatedID] = Content
        return CreatedID
