import shlex                          as ShellLexer
import typing                         as Typing
import pydantic                       as Pydantic
import Services.DebugService          as Debug
import Services.DraconicScriptService as DraconicScript
import Services.PlatformClient        as PlatformClient

class AliasEntry(Pydantic.BaseModel):
    ID              : Typing.Optional[str] = None
    Name            : str
    Content         : str
    CreatorDiscordID: str
    ServerID        : Typing.Optional[str] = None
    CollaboratorIDs : list[str]            = Pydantic.Field(default_factory = list)
    CreatedAt       : Typing.Optional[str] = None
    UpdatedAt       : Typing.Optional[str] = None

class SnippetEntry(Pydantic.BaseModel):
    ID              : Typing.Optional[str] = None
    Name            : str
    Content         : str
    CreatorDiscordID: str
    ServerID        : Typing.Optional[str] = None
    CollaboratorIDs : list[str]            = Pydantic.Field(default_factory = list)
    CreatedAt       : Typing.Optional[str] = None
    UpdatedAt       : Typing.Optional[str] = None

class AliasingService:
    def __init__(self, DraconicService: Typing.Optional[DraconicScript.DraconicScriptService] = None, PlatformClientInstance: Typing.Optional[PlatformClient.MISPlatformClient] = None) -> None:
        self.UserAliases    : dict[str, dict[str, AliasEntry]]                  = dict()
        self.ServerAliases  : dict[str, dict[str, AliasEntry]]                  = dict()
        self.UserSnippets   : dict[str, dict[str, SnippetEntry]]                = dict()
        self.ServerSnippets : dict[str, dict[str, SnippetEntry]]                = dict()
        self.PlatformClient : Typing.Optional[PlatformClient.MISPlatformClient] = PlatformClientInstance
        self.DraconicService: DraconicScript.DraconicScriptService       = DraconicService if (DraconicService is not None) else DraconicScript.DraconicScriptService(PlatformClientInstance = self.PlatformClient)

    def SetUserAlias(self, UserID: str | int, Name: str, Content: str) -> AliasEntry:
        UserKey  : str        = str(UserID)
        CleanName: str        = Name.strip().lower()
        NewEntry : AliasEntry = AliasEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = UserKey)

        if UserKey not in self.UserAliases:
            self.UserAliases[UserKey] = dict()

        self.UserAliases[UserKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Alias Created: UserID={UserKey}, Name=\"{CleanName}\"")
        return NewEntry

    def SetServerAlias(self, ServerID: str | int, CreatorDiscordID: str | int, Name: str, Content: str) -> AliasEntry:
        ServerKey : str        = str(ServerID)
        CreatorKey: str        = str(CreatorDiscordID)
        CleanName : str        = Name.strip().lower()
        NewEntry  : AliasEntry = AliasEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = CreatorKey, ServerID = ServerKey)

        if ServerKey not in self.ServerAliases:
            self.ServerAliases[ServerKey] = dict()

        self.ServerAliases[ServerKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Alias Created: ServerID={ServerKey}, Name=\"{CleanName}\"")
        return NewEntry

    def GetAlias(self, Name: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None) -> Typing.Optional[AliasEntry]:
        CleanName: str = Name.strip().lower()
        UserKey  : str = str(UserID)

        if UserKey in self.UserAliases:
            if CleanName in self.UserAliases[UserKey]:
                return self.UserAliases[UserKey][CleanName]

        for OtherUserID, UserMap in self.UserAliases.items():
            if CleanName in UserMap:
                CandidateEntry: AliasEntry = UserMap[CleanName]
                if UserKey in CandidateEntry.CollaboratorIDs:
                    return CandidateEntry

        if (ServerID is not None):
            ServerKey: str = str(ServerID)
            if ServerKey in self.ServerAliases:
                if CleanName in self.ServerAliases[ServerKey]:
                    return self.ServerAliases[ServerKey][CleanName]

        return None

    def DeleteUserAlias(self, UserID: str | int, Name: str) -> bool:
        UserKey  : str = str(UserID)
        CleanName: str = Name.strip().lower()

        if UserKey in self.UserAliases:
            if CleanName in self.UserAliases[UserKey]:
                del self.UserAliases[UserKey][CleanName]
                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Alias Deleted: UserID={UserKey}, Name=\"{CleanName}\"")
                return True

        return False

    def DeleteServerAlias(self, ServerID: str | int, Name: str) -> bool:
        ServerKey: str = str(ServerID)
        CleanName: str = Name.strip().lower()

        if ServerKey in self.ServerAliases:
            if CleanName in self.ServerAliases[ServerKey]:
                del self.ServerAliases[ServerKey][CleanName]
                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Alias Deleted: ServerID={ServerKey}, Name=\"{CleanName}\"")
                return True

        return False

    def ListUserAliases(self, UserID: str | int) -> list[AliasEntry]:
        UserKey: str = str(UserID)
        OwnedList: list[AliasEntry] = list(self.UserAliases.get(UserKey, dict()).values())
        SharedList: list[AliasEntry] = []

        for OtherUserID, UserMap in self.UserAliases.items():
            if (OtherUserID != UserKey):
                for Entry in UserMap.values():
                    if (UserKey in Entry.CollaboratorIDs) and (Entry not in SharedList):
                        SharedList.append(Entry)

        return OwnedList + SharedList

    def ListServerAliases(self, ServerID: str | int) -> list[AliasEntry]:
        ServerKey: str = str(ServerID)
        return list(self.ServerAliases.get(ServerKey, dict()).values())

    async def LoadUserAliases(self, UserID: str | int) -> list[AliasEntry]:
        UserKey: str = str(UserID)
        if (self.PlatformClient is not None):
            try:
                Records: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchAliases(Scope = "User", OwnerID = UserKey)
                if UserKey not in self.UserAliases:
                    self.UserAliases[UserKey] = dict()

                for Record in Records:
                    LoadedEntry = AliasEntry(ID = Record.get("ID"), Name = Record.get("Name", ""), Content = Record.get("Content", ""), CreatorDiscordID = Record.get("OwnerID", UserKey), ServerID = Record.get("ServerID"), CollaboratorIDs = Record.get("CollaboratorIDs", []), CreatedAt = Record.get("CreatedAt"), UpdatedAt = Record.get("UpdatedAt"))
                    self.UserAliases[UserKey][LoadedEntry.Name] = LoadedEntry

            except Exception as LoadError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to load user aliases from Platform: {str(LoadError)}")

        return self.ListUserAliases(UserKey)

    async def LoadServerAliases(self, ServerID: str | int) -> list[AliasEntry]:
        ServerKey: str = str(ServerID)
        if (self.PlatformClient is not None):
            try:
                Records: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchAliases(Scope = "Server", ServerID = ServerKey)
                if ServerKey not in self.ServerAliases:
                    self.ServerAliases[ServerKey] = dict()

                for Record in Records:
                    LoadedEntry = AliasEntry(ID = Record.get("ID"), Name = Record.get("Name", ""), Content = Record.get("Content", ""), CreatorDiscordID = Record.get("OwnerID", ""), ServerID = Record.get("ServerID", ServerKey), CollaboratorIDs = Record.get("CollaboratorIDs", []), CreatedAt = Record.get("CreatedAt"), UpdatedAt = Record.get("UpdatedAt"))
                    self.ServerAliases[ServerKey][LoadedEntry.Name] = LoadedEntry

            except Exception as LoadError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to load server aliases from Platform: {str(LoadError)}")

        return self.ListServerAliases(ServerKey)

    async def SetUserAliasAsync(self, UserID: str | int, Name: str, Content: str) -> AliasEntry:
        UserKey      : str                         = str(UserID)
        CleanName    : str                         = Name.strip().lower()
        ExistingEntry: Typing.Optional[AliasEntry] = self.UserAliases.get(UserKey, dict()).get(CleanName)
        RecordID     : Typing.Optional[str]        = ExistingEntry.ID if (ExistingEntry is not None) else None
        Collaborators: list[str]                   = ExistingEntry.CollaboratorIDs if (ExistingEntry is not None) else []

        if (self.PlatformClient is not None):
            try:
                if (RecordID is not None):
                    UpdatedRecord = await self.PlatformClient.UpdateAlias(RecordID, {"Content": Content.strip()})
                    if isinstance(UpdatedRecord, dict):
                        RecordID = UpdatedRecord.get("ID", RecordID)

                else:
                    CreatedRecord = await self.PlatformClient.CreateAlias({
                        "Name"           : CleanName,
                        "Content"        : Content.strip(),
                        "Scope"          : "User",
                        "OwnerID"        : UserKey,
                        "CollaboratorIDs": Collaborators
                    })
                    if isinstance(CreatedRecord, dict):
                        RecordID = CreatedRecord.get("ID")

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync user alias to platform: {str(SyncError)}")

        NewEntry: AliasEntry = AliasEntry(ID = RecordID, Name = CleanName, Content = Content.strip(), CreatorDiscordID = UserKey, CollaboratorIDs = Collaborators)
        if UserKey not in self.UserAliases:
            self.UserAliases[UserKey] = dict()

        self.UserAliases[UserKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Alias Saved: UserID={UserKey}, Name=\"{CleanName}\"")
        return NewEntry

    async def SetServerAliasAsync(self, ServerID: str | int, CreatorDiscordID: str | int, Name: str, Content: str) -> AliasEntry:
        ServerKey    : str                         = str(ServerID)
        CreatorKey   : str                         = str(CreatorDiscordID)
        CleanName    : str                         = Name.strip().lower()
        ExistingEntry: Typing.Optional[AliasEntry] = self.ServerAliases.get(ServerKey, dict()).get(CleanName)
        RecordID     : Typing.Optional[str]        = ExistingEntry.ID if (ExistingEntry is not None) else None
        Collaborators: list[str]                   = ExistingEntry.CollaboratorIDs if (ExistingEntry is not None) else []

        if (self.PlatformClient is not None):
            try:
                if (RecordID is not None):
                    UpdatedRecord = await self.PlatformClient.UpdateAlias(RecordID, {"Content": Content.strip()})
                    if isinstance(UpdatedRecord, dict):
                        RecordID = UpdatedRecord.get("ID", RecordID)

                else:
                    CreatedRecord = await self.PlatformClient.CreateAlias({
                        "Name"           : CleanName,
                        "Content"        : Content.strip(),
                        "Scope"          : "Server",
                        "OwnerID"        : CreatorKey,
                        "ServerID"       : ServerKey,
                        "CollaboratorIDs": Collaborators
                    })
                    if isinstance(CreatedRecord, dict):
                        RecordID = CreatedRecord.get("ID")

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync server alias to platform: {str(SyncError)}")

        NewEntry: AliasEntry = AliasEntry(ID = RecordID, Name = CleanName, Content = Content.strip(), CreatorDiscordID = CreatorKey, ServerID = ServerKey, CollaboratorIDs = Collaborators)
        if ServerKey not in self.ServerAliases:
            self.ServerAliases[ServerKey] = dict()

        self.ServerAliases[ServerKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Alias Saved: ServerID={ServerKey}, Name=\"{CleanName}\"")
        return NewEntry

    def CanEditAlias(self, Alias: AliasEntry, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        if IsAdminOrMacroMaster:
            return True

        UserStr: str = str(RequestingUserID)
        if (Alias.CreatorDiscordID == UserStr):
            return True

        if UserStr in Alias.CollaboratorIDs:
            return True

        return False

    def CanShareAlias(self, Alias: AliasEntry, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        if IsAdminOrMacroMaster:
            return True

        UserStr: str = str(RequestingUserID)
        if (Alias.CreatorDiscordID == UserStr):
            return True

        return False

    async def EditAliasAsync(self, Name: str, Content: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None, IsAdminOrMacroMaster: bool = False) -> Typing.Optional[AliasEntry]:
        CleanName: str                         = Name.strip().lower()
        Target   : Typing.Optional[AliasEntry] = self.GetAlias(CleanName, UserID, ServerID)
        if (Target is None):
            for UserMap in self.UserAliases.values():
                if CleanName in UserMap:
                    Target = UserMap[CleanName]
                    break

            if (Target is None):
                for ServerMap in self.ServerAliases.values():
                    if CleanName in ServerMap:
                        Target = ServerMap[CleanName]
                        break

        if (Target is None):
            return None

        if not self.CanEditAlias(Target, UserID, IsAdminOrMacroMaster):
            raise PermissionError(f"User {UserID} is not authorized to edit alias '{CleanName}'")

        Target.Content = Content.strip()
        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.UpdateAlias(Target.ID, {"Content": Target.Content})

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync edit alias on platform: {str(SyncError)}")

        return Target

    async def ShareAliasAsync(self, Name: str, TargetUserID: str | int, RequestingUserID: str | int, ServerID: Typing.Optional[str | int] = None, IsAdminOrMacroMaster: bool = False) -> Typing.Optional[AliasEntry]:
        CleanName: str                         = Name.strip().lower()
        Target   : Typing.Optional[AliasEntry] = self.GetAlias(CleanName, RequestingUserID, ServerID)
        if (Target is None) and IsAdminOrMacroMaster:
            for UserMap in self.UserAliases.values():
                if CleanName in UserMap:
                    Target = UserMap[CleanName]
                    break

            if (Target is None):
                for ServerMap in self.ServerAliases.values():
                    if CleanName in ServerMap:
                        Target = ServerMap[CleanName]
                        break

        if (Target is None):
            return None

        if not self.CanShareAlias(Target, RequestingUserID, IsAdminOrMacroMaster):
            raise PermissionError(f"User {RequestingUserID} is not authorized to share alias '{CleanName}'")

        TargetUserStr: str = str(TargetUserID)
        if TargetUserStr not in Target.CollaboratorIDs:
            Target.CollaboratorIDs.append(TargetUserStr)

        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.UpdateAlias(Target.ID, {"CollaboratorIDs": Target.CollaboratorIDs})

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync share alias on platform: {str(SyncError)}")

        return Target

    async def DeleteUserAliasAsync(self, UserID: str | int, Name: str, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        CleanName: str                         = Name.strip().lower()
        UserKey  : str                         = str(UserID)
        Target   : Typing.Optional[AliasEntry] = self.UserAliases.get(UserKey, dict()).get(CleanName)
        if (Target is None):
            return False

        if not self.CanShareAlias(Target, RequestingUserID, IsAdminOrMacroMaster):
            raise PermissionError(f"User {RequestingUserID} is not authorized to delete alias '{CleanName}'")

        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.DeleteAlias(Target.ID)

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to delete alias on platform: {str(SyncError)}")

        del self.UserAliases[UserKey][CleanName]
        return True

    async def DeleteServerAliasAsync(self, ServerID: str | int, Name: str, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        CleanName: str                         = Name.strip().lower()
        ServerKey: str                         = str(ServerID)
        Target   : Typing.Optional[AliasEntry] = self.ServerAliases.get(ServerKey, dict()).get(CleanName)
        if (Target is None):
            return False

        if not (IsAdminOrMacroMaster or (Target.CreatorDiscordID == str(RequestingUserID))):
            raise PermissionError(f"User {RequestingUserID} is not authorized to delete server alias '{CleanName}'")

        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.DeleteAlias(Target.ID)

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to delete server alias on platform: {str(SyncError)}")

        del self.ServerAliases[ServerKey][CleanName]
        return True

    def SetUserSnippet(self, UserID: str | int, Name: str, Content: str) -> SnippetEntry:
        UserKey  : str          = str(UserID)
        CleanName: str          = Name.strip().lower()
        NewEntry : SnippetEntry = SnippetEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = UserKey)

        if UserKey not in self.UserSnippets:
            self.UserSnippets[UserKey] = dict()

        self.UserSnippets[UserKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Snippet Created: UserID={UserKey}, Name=\"{CleanName}\"")
        return NewEntry

    def SetServerSnippet(self, ServerID: str | int, CreatorDiscordID: str | int, Name: str, Content: str) -> SnippetEntry:
        ServerKey : str          = str(ServerID)
        CreatorKey: str          = str(CreatorDiscordID)
        CleanName : str          = Name.strip().lower()
        NewEntry  : SnippetEntry = SnippetEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = CreatorKey, ServerID = ServerKey)

        if ServerKey not in self.ServerSnippets:
            self.ServerSnippets[ServerKey] = dict()

        self.ServerSnippets[ServerKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Snippet Created: ServerID={ServerKey}, Name=\"{CleanName}\"")
        return NewEntry

    def GetSnippet(self, Name: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None) -> Typing.Optional[SnippetEntry]:
        CleanName: str = Name.strip().lower()
        UserKey  : str = str(UserID)

        if UserKey in self.UserSnippets:
            if CleanName in self.UserSnippets[UserKey]:
                return self.UserSnippets[UserKey][CleanName]

        for OtherUserID, SnippetMap in self.UserSnippets.items():
            if CleanName in SnippetMap:
                CandidateEntry: SnippetEntry = SnippetMap[CleanName]
                if UserKey in CandidateEntry.CollaboratorIDs:
                    return CandidateEntry

        if (ServerID is not None):
            ServerKey: str = str(ServerID)
            if ServerKey in self.ServerSnippets:
                if CleanName in self.ServerSnippets[ServerKey]:
                    return self.ServerSnippets[ServerKey][CleanName]

        return None

    def DeleteUserSnippet(self, UserID: str | int, Name: str) -> bool:
        UserKey  : str = str(UserID)
        CleanName: str = Name.strip().lower()

        if UserKey in self.UserSnippets:
            if CleanName in self.UserSnippets[UserKey]:
                del self.UserSnippets[UserKey][CleanName]
                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Snippet Deleted: UserID={UserKey}, Name=\"{CleanName}\"")
                return True

        return False

    def DeleteServerSnippet(self, ServerID: str | int, Name: str) -> bool:
        ServerKey: str = str(ServerID)
        CleanName: str = Name.strip().lower()

        if ServerKey in self.ServerSnippets:
            if CleanName in self.ServerSnippets[ServerKey]:
                del self.ServerSnippets[ServerKey][CleanName]
                Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Snippet Deleted: ServerID={ServerKey}, Name=\"{CleanName}\"")
                return True

        return False

    def ListUserSnippets(self, UserID: str | int) -> list[SnippetEntry]:
        UserKey: str = str(UserID)
        OwnedList: list[SnippetEntry] = list(self.UserSnippets.get(UserKey, dict()).values())
        SharedList: list[SnippetEntry] = []

        for OtherUserID, SnippetMap in self.UserSnippets.items():
            if (OtherUserID != UserKey):
                for Entry in SnippetMap.values():
                    if (UserKey in Entry.CollaboratorIDs) and (Entry not in SharedList):
                        SharedList.append(Entry)

        return OwnedList + SharedList

    def ListServerSnippets(self, ServerID: str | int) -> list[SnippetEntry]:
        ServerKey: str = str(ServerID)
        return list(self.ServerSnippets.get(ServerKey, dict()).values())

    async def LoadUserSnippets(self, UserID: str | int) -> list[SnippetEntry]:
        UserKey: str = str(UserID)
        if (self.PlatformClient is not None):
            try:
                Records: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchSnippets(Scope = "User", OwnerID = UserKey)
                if UserKey not in self.UserSnippets:
                    self.UserSnippets[UserKey] = dict()

                for Record in Records:
                    LoadedEntry = SnippetEntry(ID = Record.get("ID"), Name = Record.get("Name", ""), Content = Record.get("Content", ""), CreatorDiscordID = Record.get("OwnerID", UserKey), ServerID = Record.get("ServerID"), CollaboratorIDs = Record.get("CollaboratorIDs", []), CreatedAt = Record.get("CreatedAt"), UpdatedAt = Record.get("UpdatedAt"))
                    self.UserSnippets[UserKey][LoadedEntry.Name] = LoadedEntry

            except Exception as LoadError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to load user snippets from Platform: {str(LoadError)}")

        return self.ListUserSnippets(UserKey)

    async def LoadServerSnippets(self, ServerID: str | int) -> list[SnippetEntry]:
        ServerKey: str = str(ServerID)
        if (self.PlatformClient is not None):
            try:
                Records: list[dict[str, Typing.Any]] = await self.PlatformClient.FetchSnippets(Scope = "Server", ServerID = ServerKey)
                if ServerKey not in self.ServerSnippets:
                    self.ServerSnippets[ServerKey] = dict()

                for Record in Records:
                    LoadedEntry = SnippetEntry(ID = Record.get("ID"), Name = Record.get("Name", ""), Content = Record.get("Content", ""), CreatorDiscordID = Record.get("OwnerID", ""), ServerID = Record.get("ServerID", ServerKey), CollaboratorIDs = Record.get("CollaboratorIDs", []), CreatedAt = Record.get("CreatedAt"), UpdatedAt = Record.get("UpdatedAt"))
                    self.ServerSnippets[ServerKey][LoadedEntry.Name] = LoadedEntry

            except Exception as LoadError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to load server snippets from Platform: {str(LoadError)}")

        return self.ListServerSnippets(ServerKey)

    async def SetUserSnippetAsync(self, UserID: str | int, Name: str, Content: str) -> SnippetEntry:
        UserKey      : str                           = str(UserID)
        CleanName    : str                           = Name.strip().lower()
        ExistingEntry: Typing.Optional[SnippetEntry] = self.UserSnippets.get(UserKey, dict()).get(CleanName)
        RecordID     : Typing.Optional[str]          = ExistingEntry.ID if (ExistingEntry is not None) else None
        Collaborators: list[str]                     = ExistingEntry.CollaboratorIDs if (ExistingEntry is not None) else []

        if (self.PlatformClient is not None):
            try:
                if (RecordID is not None):
                    UpdatedRecord = await self.PlatformClient.UpdateSnippet(RecordID, {"Content": Content.strip()})
                    if isinstance(UpdatedRecord, dict):
                        RecordID = UpdatedRecord.get("ID", RecordID)

                else:
                    CreatedRecord = await self.PlatformClient.CreateSnippet({
                        "Name"           : CleanName,
                        "Content"        : Content.strip(),
                        "Scope"          : "User",
                        "OwnerID"        : UserKey,
                        "CollaboratorIDs": Collaborators
                    })
                    if isinstance(CreatedRecord, dict):
                        RecordID = CreatedRecord.get("ID")

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync user snippet to platform: {str(SyncError)}")

        NewEntry: SnippetEntry = SnippetEntry(ID = RecordID, Name = CleanName, Content = Content.strip(), CreatorDiscordID = UserKey, CollaboratorIDs = Collaborators)
        if UserKey not in self.UserSnippets:
            self.UserSnippets[UserKey] = dict()

        self.UserSnippets[UserKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Snippet Saved: UserID={UserKey}, Name=\"{CleanName}\"")
        return NewEntry

    async def SetServerSnippetAsync(self, ServerID: str | int, CreatorDiscordID: str | int, Name: str, Content: str) -> SnippetEntry:
        ServerKey    : str                           = str(ServerID)
        CreatorKey   : str                           = str(CreatorDiscordID)
        CleanName    : str                           = Name.strip().lower()
        ExistingEntry: Typing.Optional[SnippetEntry] = self.ServerSnippets.get(ServerKey, dict()).get(CleanName)
        RecordID     : Typing.Optional[str]          = ExistingEntry.ID if (ExistingEntry is not None) else None
        Collaborators: list[str]                     = ExistingEntry.CollaboratorIDs if (ExistingEntry is not None) else []

        if (self.PlatformClient is not None):
            try:
                if (RecordID is not None):
                    UpdatedRecord = await self.PlatformClient.UpdateSnippet(RecordID, {"Content": Content.strip()})
                    if isinstance(UpdatedRecord, dict):
                        RecordID = UpdatedRecord.get("ID", RecordID)

                else:
                    CreatedRecord = await self.PlatformClient.CreateSnippet({
                        "Name"           : CleanName,
                        "Content"        : Content.strip(),
                        "Scope"          : "Server",
                        "OwnerID"        : CreatorKey,
                        "ServerID"       : ServerKey,
                        "CollaboratorIDs": Collaborators
                    })
                    if isinstance(CreatedRecord, dict):
                        RecordID = CreatedRecord.get("ID")

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync server snippet to platform: {str(SyncError)}")

        NewEntry: SnippetEntry = SnippetEntry(ID = RecordID, Name = CleanName, Content = Content.strip(), CreatorDiscordID = CreatorKey, ServerID = ServerKey, CollaboratorIDs = Collaborators)
        if ServerKey not in self.ServerSnippets:
            self.ServerSnippets[ServerKey] = dict()

        self.ServerSnippets[ServerKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Snippet Saved: ServerID={ServerKey}, Name=\"{CleanName}\"")
        return NewEntry

    def CanEditSnippet(self, Snippet: SnippetEntry, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        if IsAdminOrMacroMaster:
            return True

        UserStr: str = str(RequestingUserID)
        if (Snippet.CreatorDiscordID == UserStr):
            return True

        if UserStr in Snippet.CollaboratorIDs:
            return True

        return False

    def CanShareSnippet(self, Snippet: SnippetEntry, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        if IsAdminOrMacroMaster:
            return True

        UserStr: str = str(RequestingUserID)
        if (Snippet.CreatorDiscordID == UserStr):
            return True

        return False

    async def EditSnippetAsync(self, Name: str, Content: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None, IsAdminOrMacroMaster: bool = False) -> Typing.Optional[SnippetEntry]:
        CleanName: str                           = Name.strip().lower()
        Target   : Typing.Optional[SnippetEntry] = self.GetSnippet(CleanName, UserID, ServerID)
        if (Target is None):
            for UserMap in self.UserSnippets.values():
                if CleanName in UserMap:
                    Target = UserMap[CleanName]
                    break

            if (Target is None):
                for ServerMap in self.ServerSnippets.values():
                    if CleanName in ServerMap:
                        Target = ServerMap[CleanName]
                        break

        if (Target is None):
            return None

        if not self.CanEditSnippet(Target, UserID, IsAdminOrMacroMaster):
            raise PermissionError(f"User {UserID} is not authorized to edit snippet '{CleanName}'")

        Target.Content = Content.strip()
        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.UpdateSnippet(Target.ID, {"Content": Target.Content})

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync edit snippet on platform: {str(SyncError)}")

        return Target

    async def ShareSnippetAsync(self, Name: str, TargetUserID: str | int, RequestingUserID: str | int, ServerID: Typing.Optional[str | int] = None, IsAdminOrMacroMaster: bool = False) -> Typing.Optional[SnippetEntry]:
        CleanName: str                           = Name.strip().lower()
        Target   : Typing.Optional[SnippetEntry] = self.GetSnippet(CleanName, RequestingUserID, ServerID)
        if (Target is None) and IsAdminOrMacroMaster:
            for UserMap in self.UserSnippets.values():
                if CleanName in UserMap:
                    Target = UserMap[CleanName]
                    break

            if (Target is None):
                for ServerMap in self.ServerSnippets.values():
                    if CleanName in ServerMap:
                        Target = ServerMap[CleanName]
                        break

        if (Target is None):
            return None

        if not self.CanShareSnippet(Target, RequestingUserID, IsAdminOrMacroMaster):
            raise PermissionError(f"User {RequestingUserID} is not authorized to share snippet '{CleanName}'")

        TargetUserStr: str = str(TargetUserID)
        if TargetUserStr not in Target.CollaboratorIDs:
            Target.CollaboratorIDs.append(TargetUserStr)

        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.UpdateSnippet(Target.ID, {"CollaboratorIDs": Target.CollaboratorIDs})

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to sync share snippet on platform: {str(SyncError)}")

        return Target

    async def DeleteUserSnippetAsync(self, UserID: str | int, Name: str, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        CleanName: str                           = Name.strip().lower()
        UserKey  : str                           = str(UserID)
        Target   : Typing.Optional[SnippetEntry] = self.UserSnippets.get(UserKey, dict()).get(CleanName)
        if (Target is None):
            return False

        if not self.CanShareSnippet(Target, RequestingUserID, IsAdminOrMacroMaster):
            raise PermissionError(f"User {RequestingUserID} is not authorized to delete snippet '{CleanName}'")

        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.DeleteSnippet(Target.ID)

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to delete snippet on platform: {str(SyncError)}")

        del self.UserSnippets[UserKey][CleanName]
        return True

    async def DeleteServerSnippetAsync(self, ServerID: str | int, Name: str, RequestingUserID: str | int, IsAdminOrMacroMaster: bool = False) -> bool:
        CleanName: str                           = Name.strip().lower()
        ServerKey: str                           = str(ServerID)
        Target   : Typing.Optional[SnippetEntry] = self.ServerSnippets.get(ServerKey, dict()).get(CleanName)
        if (Target is None):
            return False

        if not (IsAdminOrMacroMaster or (Target.CreatorDiscordID == str(RequestingUserID))):
            raise PermissionError(f"User {RequestingUserID} is not authorized to delete server snippet '{CleanName}'")

        if (Target.ID is not None) and (self.PlatformClient is not None):
            try:
                await self.PlatformClient.DeleteSnippet(Target.ID)

            except Exception as SyncError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to delete server snippet on platform: {str(SyncError)}")

        del self.ServerSnippets[ServerKey][CleanName]
        return True

    def ExpandSnippets(self, InputText: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None) -> str:
        AvailableSnippets: dict[str, str] = dict()

        if (ServerID is not None):
            ServerKey: str = str(ServerID)
            for Snippet in self.ServerSnippets.get(ServerKey, dict()).values():
                AvailableSnippets[Snippet.Name.lower()] = Snippet.Content

        UserKey: str = str(UserID)
        for OtherUserID, SnippetMap in self.UserSnippets.items():
            for Snippet in SnippetMap.values():
                if (UserKey in Snippet.CollaboratorIDs):
                    AvailableSnippets[Snippet.Name.lower()] = Snippet.Content

        for Snippet in self.UserSnippets.get(UserKey, dict()).values():
            AvailableSnippets[Snippet.Name.lower()] = Snippet.Content

        if not AvailableSnippets:
            return InputText

        Tokens        : list[str] = InputText.split(" ")
        ExpandedTokens: list[str] = []

        for Token in Tokens:
            TokenLower: str = Token.lower()
            if TokenLower in AvailableSnippets:
                ExpandedTokens.append(AvailableSnippets[TokenLower])

            else:
                ExpandedTokens.append(Token)

        return " ".join(ExpandedTokens)

    def ExecuteAlias(self, Alias: AliasEntry, RawArguments: str, Context: DraconicScript.DraconicEvaluationContext) -> str:
        ArgumentList: list[str] = []

        try:
            ArgumentList = ShellLexer.split(RawArguments)

        except ValueError:
            ArgumentList = RawArguments.split()

        Context.Arguments       = ArgumentList
        Context.ArgumentsString = RawArguments
        InterpolatedResult: str = self.DraconicService.InterpolateTemplate(Alias.Content, Context)
        FinalResult       : str = self.ExpandSnippets(InterpolatedResult, Context.AuthorID, Context.EncounterData.GuildID if (Context.EncounterData) else None)
        return FinalResult
