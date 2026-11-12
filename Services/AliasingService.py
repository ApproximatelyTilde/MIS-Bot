import shlex                             as ShellLexer
import typing                            as Typing
import pydantic                          as Pydantic
import Services.DebugService             as Debug
import Services.DraconicScriptService    as DraconicScriptService

class AliasEntry(Pydantic.BaseModel):
    Name            : str
    Content         : str
    CreatorDiscordID: str
    ServerID        : Typing.Optional[str] = None

class SnippetEntry(Pydantic.BaseModel):
    Name            : str
    Content         : str
    CreatorDiscordID: str
    ServerID        : Typing.Optional[str] = None

class AliasingService:
    def __init__(self, DraconicService: Typing.Optional[DraconicScriptService.DraconicScriptService] = None) -> None:
        self.UserAliases    : dict[str, dict[str, AliasEntry]]   = {}
        self.ServerAliases  : dict[str, dict[str, AliasEntry]]   = {}
        self.UserSnippets   : dict[str, dict[str, SnippetEntry]] = {}
        self.ServerSnippets : dict[str, dict[str, SnippetEntry]] = {}
        self.DraconicService: DraconicScriptService.DraconicScriptService = DraconicService if (DraconicService is not None) else DraconicScriptService.DraconicScriptService()

    def SetUserAlias(self, UserID: str | int, Name: str, Content: str) -> AliasEntry:
        UserKey: str       = str(UserID)
        CleanName: str     = Name.strip().lower()
        NewEntry: AliasEntry = AliasEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = UserKey)

        if UserKey not in self.UserAliases:
            self.UserAliases[UserKey] = {}

        self.UserAliases[UserKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Alias Created: UserID={UserKey}, Name=\"{CleanName}\"")
        return NewEntry

    def SetServerAlias(self, ServerID: str | int, CreatorDiscordID: str | int, Name: str, Content: str) -> AliasEntry:
        ServerKey: str     = str(ServerID)
        CreatorKey: str    = str(CreatorDiscordID)
        CleanName: str     = Name.strip().lower()
        NewEntry: AliasEntry = AliasEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = CreatorKey, ServerID = ServerKey)

        if ServerKey not in self.ServerAliases:
            self.ServerAliases[ServerKey] = {}

        self.ServerAliases[ServerKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Alias Created: ServerID={ServerKey}, Name=\"{CleanName}\"")
        return NewEntry

    def GetAlias(self, Name: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None) -> Typing.Optional[AliasEntry]:
        CleanName: str = Name.strip().lower()
        UserKey  : str = str(UserID)

        if UserKey in self.UserAliases:
            if CleanName in self.UserAliases[UserKey]:
                return self.UserAliases[UserKey][CleanName]

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
        return list(self.UserAliases.get(UserKey, {}).values())

    def ListServerAliases(self, ServerID: str | int) -> list[AliasEntry]:
        ServerKey: str = str(ServerID)
        return list(self.ServerAliases.get(ServerKey, {}).values())

    def SetUserSnippet(self, UserID: str | int, Name: str, Content: str) -> SnippetEntry:
        UserKey: str         = str(UserID)
        CleanName: str       = Name.strip().lower()
        NewEntry: SnippetEntry = SnippetEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = UserKey)

        if UserKey not in self.UserSnippets:
            self.UserSnippets[UserKey] = {}

        self.UserSnippets[UserKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"User Snippet Created: UserID={UserKey}, Name=\"{CleanName}\"")
        return NewEntry

    def SetServerSnippet(self, ServerID: str | int, CreatorDiscordID: str | int, Name: str, Content: str) -> SnippetEntry:
        ServerKey: str       = str(ServerID)
        CreatorKey: str      = str(CreatorDiscordID)
        CleanName: str       = Name.strip().lower()
        NewEntry: SnippetEntry = SnippetEntry(Name = CleanName, Content = Content.strip(), CreatorDiscordID = CreatorKey, ServerID = ServerKey)

        if ServerKey not in self.ServerSnippets:
            self.ServerSnippets[ServerKey] = {}

        self.ServerSnippets[ServerKey][CleanName] = NewEntry
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Server Snippet Created: ServerID={ServerKey}, Name=\"{CleanName}\"")
        return NewEntry

    def GetSnippet(self, Name: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None) -> Typing.Optional[SnippetEntry]:
        CleanName: str = Name.strip().lower()
        UserKey  : str = str(UserID)

        if UserKey in self.UserSnippets:
            if CleanName in self.UserSnippets[UserKey]:
                return self.UserSnippets[UserKey][CleanName]

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
        return list(self.UserSnippets.get(UserKey, {}).values())

    def ListServerSnippets(self, ServerID: str | int) -> list[SnippetEntry]:
        ServerKey: str = str(ServerID)
        return list(self.ServerSnippets.get(ServerKey, {}).values())

    def ExpandSnippets(self, InputText: str, UserID: str | int, ServerID: Typing.Optional[str | int] = None) -> str:
        AvailableSnippets: dict[str, str] = {}

        if (ServerID is not None):
            ServerKey: str = str(ServerID)
            for Snippet in self.ServerSnippets.get(ServerKey, {}).values():
                AvailableSnippets[Snippet.Name.lower()] = Snippet.Content

        UserKey: str = str(UserID)
        for Snippet in self.UserSnippets.get(UserKey, {}).values():
            AvailableSnippets[Snippet.Name.lower()] = Snippet.Content

        if not AvailableSnippets:
            return InputText

        Tokens: list[str] = InputText.split(" ")
        ExpandedTokens: list[str] = []

        for Token in Tokens:
            TokenLower: str = Token.lower()
            if TokenLower in AvailableSnippets:
                ExpandedTokens.append(AvailableSnippets[TokenLower])

            else:
                ExpandedTokens.append(Token)

        return " ".join(ExpandedTokens)

    def ExecuteAlias(self, Alias: AliasEntry, RawArguments: str, Context: DraconicScriptService.DraconicEvaluationContext) -> str:
        ArgumentList: list[str] = []

        try:
            ArgumentList = ShellLexer.split(RawArguments)

        except ValueError:
            ArgumentList = RawArguments.split()

        Context.Arguments       = ArgumentList
        Context.ArgumentsString = RawArguments
        InterpolatedResult: str = self.DraconicService.InterpolateTemplate(Alias.Content, Context)
        FinalResult       : str = self.ExpandSnippets(InterpolatedResult, Context.AuthorID, Context.EncounterData.GuildID if Context.EncounterData else None)
        return FinalResult
