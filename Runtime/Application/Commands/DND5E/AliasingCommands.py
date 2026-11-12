import typing                                             as Typing
import discord                                            as Discord
import discord.ext.commands                               as Commands
import Runtime.Configuration.Config                       as Config
import Runtime.Services.AliasingService                   as Aliasing
import Runtime.Services.CharacterStateService             as CharacterState
import Runtime.Services.PlatformClient                    as PlatformClient
import Runtime.Services.Draconic.API.CustomCounterManager as CounterManager
import Runtime.Decorators.AuthorizationDecorators         as AuthorizationDecorators

COLOR_ALIAS_EMBED  : int = 0x0030A6
COLOR_SNIPPET_EMBED: int = 0x005E00
COLOR_COUNTER_EMBED: int = 0x5E005E
COLOR_ERROR_EMBED  : int = 0xA60000

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance: Typing.Any = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E5E)

class AliasingCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, AliasingServiceInstance: Typing.Optional[Aliasing.AliasingService] = None, CharacterStateServiceInstance: Typing.Optional[CharacterState.CharacterStateService] = None) -> None:
        self.BotInstance          : Commands.Bot                                = BotInstance
        self.AliasingService      : Aliasing.AliasingService             = AliasingServiceInstance if (AliasingServiceInstance is not None) else Aliasing.AliasingService()
        self.CharacterStateService: CharacterState.CharacterStateService = CharacterStateServiceInstance if (CharacterStateServiceInstance is not None) else CharacterState.CharacterStateService()
        self.PlatformClient       : PlatformClient.TallyPlatformClient          = self.CharacterStateService.PlatformClient if (self.CharacterStateService.PlatformClient is not None) else PlatformClient.TallyPlatformClient()

        if (self.AliasingService.PlatformClient is None):
            self.AliasingService.PlatformClient = self.PlatformClient

    def IsMacroMasterOrAdmin(self, Context: Commands.Context) -> bool:
        return AuthorizationDecorators.IsMacroMasterOrAdmin(Context)

    @Commands.group(name = "alias", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def AliasGroup(self, Context: Commands.Context, AliasName: Typing.Optional[str] = None, *, AliasContent: Typing.Optional[str] = None) -> None:
        if (AliasName is None) or (AliasContent is None):
            await self.ListAliases(Context)
            return

        CreatedEntry: Aliasing.AliasEntry = await self.AliasingService.SetUserAliasAsync(Context.author.id, AliasName, AliasContent)
        SuccessEmbed: Discord.Embed       = Discord.Embed(title = "Alias Created", description = f"Alias **`{CreatedEntry.Name}`** has been registered.\n\n**Definition:**\n```\n{CreatedEntry.Content}\n```\nInvoke with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}{CreatedEntry.Name}`", color = COLOR_ALIAS_EMBED)
        SuccessEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @AliasGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListAliases(self, Context: Commands.Context) -> None:
        UserList  : list[Aliasing.AliasEntry] = await self.AliasingService.LoadUserAliases(Context.author.id)
        ServerList: list[Aliasing.AliasEntry] = await self.AliasingService.LoadServerAliases(Context.guild.id) if (Context.guild is not None) else []

        ListEmbed: Discord.Embed = Discord.Embed(title = "Configured Aliases", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}alias <name> <content>` to add a custom alias.", color = COLOR_ALIAS_EMBED)

        if UserList:
            UserText: str = "\n".join(f"• **`{A.Name}`**: `{A.Content[:50]}`" + (f" *(Shared with: {", ".join(A.CollaboratorIDs)})*" if (A.CollaboratorIDs) else "") for A in UserList)
            ListEmbed.add_field(name = "Personal Aliases", value = UserText[:1020], inline = False)

        else:
            ListEmbed.add_field(name = "Personal Aliases", value = "No personal aliases found.", inline = False)

        if ServerList:
            ServerText: str = "\n".join(f"• **`{A.Name}`**: `{A.Content[:50]}`" + (f" *(Shared with: {", ".join(A.CollaboratorIDs)})*" if (bool(A.CollaboratorIDs)) else "") for A in ServerList)
            ListEmbed.add_field(name = "Server Aliases", value = ServerText[:1020], inline = False)

        ListEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = ListEmbed)

    @AliasGroup.command(name = "edit")
    @Commands.check(CheckDND5EPrefix)
    async def EditAlias(self, Context: Commands.Context, TargetName: str, *, Content: str) -> None:
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        try:
            UpdatedEntry: Typing.Optional[Aliasing.AliasEntry] = await self.AliasingService.EditAliasAsync(TargetName, Content, Context.author.id, GuildID, self.IsMacroMasterOrAdmin(Context))
            if (UpdatedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Alias Edited", description = f"Alias **`{UpdatedEntry.Name}`** updated successfully.\n\n**New Definition:**\n```\n{UpdatedEntry.Content}\n```", color = COLOR_ALIAS_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Alias **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to edit alias **`{TargetName}`**.")

    @AliasGroup.command(name = "share")
    @Commands.check(CheckDND5EPrefix)
    async def ShareAlias(self, Context: Commands.Context, TargetName: str, TargetUser: Discord.User) -> None:
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        try:
            SharedEntry: Typing.Optional[Aliasing.AliasEntry] = await self.AliasingService.ShareAliasAsync(TargetName, TargetUser.id, Context.author.id, GuildID, self.IsMacroMasterOrAdmin(Context))
            if (SharedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Alias Shared", description = f"Alias **`{SharedEntry.Name}`** is now shared with <@{TargetUser.id}>.\nCollaborators: {", ".join(SharedEntry.CollaboratorIDs)}", color = COLOR_ALIAS_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Alias **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to share alias **`{TargetName}`**.")

    @AliasGroup.command(name = "remove", aliases = ["delete"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveAlias(self, Context: Commands.Context, TargetName: str) -> None:
        try:
            IsDeleted: bool = await self.AliasingService.DeleteUserAliasAsync(Context.author.id, TargetName, Context.author.id, self.IsMacroMasterOrAdmin(Context))
            if IsDeleted:
                await Context.send(f"Personal alias **`{TargetName.lower()}`** removed successfully.")

            else:
                await Context.send(f"Could not find personal alias **`{TargetName}`**.")

        except PermissionError:
            await Context.send(f"You do not have permission to delete alias **`{TargetName}`**.")

    @AliasGroup.group(name = "server", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def ServerAliasSubGroup(self, Context: Commands.Context, AliasName: Typing.Optional[str] = None, *, AliasContent: Typing.Optional[str] = None) -> None:
        if (Context.guild is None):
            await Context.send("Server aliases can only be configured within a guild.")
            return

        if not self.IsMacroMasterOrAdmin(Context):
            await Context.send("You require Manage Server permission or Macro Master role to configure server aliases.")
            return

        if (AliasName is None) or (AliasContent is None):
            await self.ListServerAliases(Context)
            return

        CreatedEntry: Aliasing.AliasEntry = await self.AliasingService.SetServerAliasAsync(Context.guild.id, Context.author.id, AliasName, AliasContent)
        SuccessEmbed: Discord.Embed       = Discord.Embed(title = "Server Alias Created", description = f"Server alias **`{CreatedEntry.Name}`** registered for this guild.\n\n**Definition:**\n```\n{CreatedEntry.Content}\n```", color = COLOR_ALIAS_EMBED)
        SuccessEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @ServerAliasSubGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListServerAliases(self, Context: Commands.Context) -> None:
        if (Context.guild is None):
            await Context.send("Server aliases can only be listed within a guild.")
            return

        ServerList: list[Aliasing.AliasEntry] = await self.AliasingService.LoadServerAliases(Context.guild.id)
        ListEmbed : Discord.Embed             = Discord.Embed(title = "Server Aliases", description = f"Server aliases available in **{Context.guild.name}**.", color = COLOR_ALIAS_EMBED)

        if ServerList:
            ServerText: str = "\n".join(f"• **`{A.Name}`**: `{A.Content[:50]}`" + (f" *(Shared with: {", ".join(A.CollaboratorIDs)})*" if (bool(A.CollaboratorIDs)) else "") for A in ServerList)
            ListEmbed.add_field(name = "Server Aliases", value = ServerText[:1020], inline = False)

        else:
            ListEmbed.add_field(name = "Server Aliases", value = "No server aliases found.", inline = False)

        ListEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = ListEmbed)

    @ServerAliasSubGroup.command(name = "edit")
    @Commands.check(CheckDND5EPrefix)
    async def EditServerAlias(self, Context: Commands.Context, TargetName: str, *, Content: str) -> None:
        if (Context.guild is None):
            await Context.send("Server aliases can only be edited within a guild.")
            return

        try:
            UpdatedEntry: Typing.Optional[Aliasing.AliasEntry] = await self.AliasingService.EditAliasAsync(TargetName, Content, Context.author.id, Context.guild.id, self.IsMacroMasterOrAdmin(Context))
            if (UpdatedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Server Alias Edited", description = f"Server alias **`{UpdatedEntry.Name}`** updated successfully.\n\n**New Definition:**\n```\n{UpdatedEntry.Content}\n```", color = COLOR_ALIAS_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Server alias **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to edit server alias **`{TargetName}`**.")

    @ServerAliasSubGroup.command(name = "share")
    @Commands.check(CheckDND5EPrefix)
    async def ShareServerAlias(self, Context: Commands.Context, TargetName: str, TargetUser: Discord.User) -> None:
        if (Context.guild is None):
            await Context.send("Server aliases can only be shared within a guild.")
            return

        try:
            SharedEntry: Typing.Optional[Aliasing.AliasEntry] = await self.AliasingService.ShareAliasAsync(TargetName, TargetUser.id, Context.author.id, Context.guild.id, self.IsMacroMasterOrAdmin(Context))
            if (SharedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Server Alias Shared", description = f"Server alias **`{SharedEntry.Name}`** collaborator added: <@{TargetUser.id}>.\nCollaborators: {", ".join(SharedEntry.CollaboratorIDs)}", color = COLOR_ALIAS_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Server alias **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to share server alias **`{TargetName}`**.")

    @ServerAliasSubGroup.command(name = "remove", aliases = ["delete"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveServerAlias(self, Context: Commands.Context, TargetName: str) -> None:
        if (Context.guild is None):
            await Context.send("Server aliases can only be deleted within a guild.")
            return

        try:
            IsDeleted: bool = await self.AliasingService.DeleteServerAliasAsync(Context.guild.id, TargetName, Context.author.id, self.IsMacroMasterOrAdmin(Context))
            if IsDeleted:
                await Context.send(f"Server alias **`{TargetName.lower()}`** removed successfully.")

            else:
                await Context.send(f"Could not find server alias **`{TargetName}`**.")

        except PermissionError:
            await Context.send(f"You do not have permission to delete server alias **`{TargetName}`**.")

    @Commands.group(name = "snippet", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def SnippetGroup(self, Context: Commands.Context, SnippetName: Typing.Optional[str] = None, *, SnippetContent: Typing.Optional[str] = None) -> None:
        if (SnippetName is None) or (SnippetContent is None):
            await self.ListSnippets(Context)
            return

        CreatedEntry: Aliasing.SnippetEntry = await self.AliasingService.SetUserSnippetAsync(Context.author.id, SnippetName, SnippetContent)
        SuccessEmbed: Discord.Embed         = Discord.Embed(title = "Snippet Created", description = f"Snippet **`{CreatedEntry.Name}`** registered.\n\n**Expansion:** `{CreatedEntry.Content}`\nUse inline in commands (e.g. `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}r 1d20 {CreatedEntry.Name}`)", color = COLOR_SNIPPET_EMBED)
        SuccessEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @SnippetGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListSnippets(self, Context: Commands.Context) -> None:
        UserList  : list[Aliasing.SnippetEntry] = await self.AliasingService.LoadUserSnippets(Context.author.id)
        ServerList: list[Aliasing.SnippetEntry] = await self.AliasingService.LoadServerSnippets(Context.guild.id) if (Context.guild is not None) else []

        ListEmbed: Discord.Embed = Discord.Embed(title = "Configured Snippets", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}snippet <name> <content>` to add a snippet.", color = COLOR_SNIPPET_EMBED)

        if UserList:
            UserText: str = "\n".join(f"• **`{S.Name}`**: `{S.Content}`" + (f" *(Shared with: {", ".join(S.CollaboratorIDs)})*" if (bool(S.CollaboratorIDs)) else "") for S in UserList)
            ListEmbed.add_field(name = "Personal Snippets", value = UserText[:1020], inline = False)

        else:
            ListEmbed.add_field(name = "Personal Snippets", value = "No personal snippets found.", inline = False)

        if ServerList:
            ServerText: str = "\n".join(f"• **`{S.Name}`**: `{S.Content}`" + (f" *(Shared with: {", ".join(S.CollaboratorIDs)})*" if (bool(S.CollaboratorIDs)) else "") for S in ServerList)
            ListEmbed.add_field(name = "Server Snippets", value = ServerText[:1020], inline = False)

        ListEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = ListEmbed)

    @SnippetGroup.command(name = "edit")
    @Commands.check(CheckDND5EPrefix)
    async def EditSnippet(self, Context: Commands.Context, TargetName: str, *, Content: str) -> None:
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        try:
            UpdatedEntry: Typing.Optional[Aliasing.SnippetEntry] = await self.AliasingService.EditSnippetAsync(TargetName, Content, Context.author.id, GuildID, self.IsMacroMasterOrAdmin(Context))
            if (UpdatedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Snippet Edited", description = f"Snippet **`{UpdatedEntry.Name}`** updated successfully.\n\n**New Expansion:** `{UpdatedEntry.Content}`", color = COLOR_SNIPPET_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Snippet **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to edit snippet **`{TargetName}`**.")

    @SnippetGroup.command(name = "share")
    @Commands.check(CheckDND5EPrefix)
    async def ShareSnippet(self, Context: Commands.Context, TargetName: str, TargetUser: Discord.User) -> None:
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        try:
            SharedEntry: Typing.Optional[Aliasing.SnippetEntry] = await self.AliasingService.ShareSnippetAsync(TargetName, TargetUser.id, Context.author.id, GuildID, self.IsMacroMasterOrAdmin(Context))
            if (SharedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Snippet Shared", description = f"Snippet **`{SharedEntry.Name}`** shared with <@{TargetUser.id}>.\nCollaborators: {", ".join(SharedEntry.CollaboratorIDs)}", color = COLOR_SNIPPET_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Snippet **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to share snippet **`{TargetName}`**.")

    @SnippetGroup.command(name = "remove", aliases = ["delete"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveSnippet(self, Context: Commands.Context, TargetName: str) -> None:
        try:
            IsDeleted: bool = await self.AliasingService.DeleteUserSnippetAsync(Context.author.id, TargetName, Context.author.id, self.IsMacroMasterOrAdmin(Context))
            if IsDeleted:
                await Context.send(f"Personal snippet **`{TargetName.lower()}`** removed successfully.")

            else:
                await Context.send(f"Could not find personal snippet **`{TargetName}`**.")

        except PermissionError:
            await Context.send(f"You do not have permission to delete snippet **`{TargetName}`**.")

    @SnippetGroup.group(name = "server", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def ServerSnippetSubGroup(self, Context: Commands.Context, SnippetName: Typing.Optional[str] = None, *, SnippetContent: Typing.Optional[str] = None) -> None:
        if (Context.guild is None):
            await Context.send("Server snippets can only be configured within a guild.")
            return

        if not self.IsMacroMasterOrAdmin(Context):
            await Context.send("You require Manage Server permission or Macro Master role to configure server snippets.")
            return

        if (SnippetName is None) or (SnippetContent is None):
            await self.ListServerSnippets(Context)
            return

        CreatedEntry: Aliasing.SnippetEntry = await self.AliasingService.SetServerSnippetAsync(Context.guild.id, Context.author.id, SnippetName, SnippetContent)
        SuccessEmbed: Discord.Embed         = Discord.Embed(title = "Server Snippet Created", description = f"Server snippet **`{CreatedEntry.Name}`** registered for this guild.\n\n**Expansion:** `{CreatedEntry.Content}`", color = COLOR_SNIPPET_EMBED)
        SuccessEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @ServerSnippetSubGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListServerSnippets(self, Context: Commands.Context) -> None:
        if (Context.guild is None):
            await Context.send("Server snippets can only be listed within a guild.")
            return

        ServerList: list[Aliasing.SnippetEntry] = await self.AliasingService.LoadServerSnippets(Context.guild.id)
        ListEmbed : Discord.Embed               = Discord.Embed(title = "Server Snippets", description = f"Server snippets available in **{Context.guild.name}**.", color = COLOR_SNIPPET_EMBED)

        if ServerList:
            ServerText: str = "\n".join(f"• **`{S.Name}`**: `{S.Content}`" + (f" *(Shared with: {", ".join(S.CollaboratorIDs)})*" if (bool(S.CollaboratorIDs)) else "") for S in ServerList)
            ListEmbed.add_field(name = "Server Snippets", value = ServerText[:1020], inline = False)

        else:
            ListEmbed.add_field(name = "Server Snippets", value = "No server snippets found.", inline = False)

        ListEmbed.set_footer(text = "Tally │ Draconic Aliasing Engine")
        await Context.send(embed = ListEmbed)

    @ServerSnippetSubGroup.command(name = "edit")
    @Commands.check(CheckDND5EPrefix)
    async def EditServerSnippet(self, Context: Commands.Context, TargetName: str, *, Content: str) -> None:
        if (Context.guild is None):
            await Context.send("Server snippets can only be edited within a guild.")
            return

        try:
            UpdatedEntry: Typing.Optional[Aliasing.SnippetEntry] = await self.AliasingService.EditSnippetAsync(TargetName, Content, Context.author.id, Context.guild.id, self.IsMacroMasterOrAdmin(Context))
            if (UpdatedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Server Snippet Edited", description = f"Server snippet **`{UpdatedEntry.Name}`** updated successfully.\n\n**New Expansion:** `{UpdatedEntry.Content}`", color = COLOR_SNIPPET_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Server snippet **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to edit server snippet **`{TargetName}`**.")

    @ServerSnippetSubGroup.command(name = "share")
    @Commands.check(CheckDND5EPrefix)
    async def ShareServerSnippet(self, Context: Commands.Context, TargetName: str, TargetUser: Discord.User) -> None:
        if (Context.guild is None):
            await Context.send("Server snippets can only be shared within a guild.")
            return

        try:
            SharedEntry: Typing.Optional[Aliasing.SnippetEntry] = await self.AliasingService.ShareSnippetAsync(TargetName, TargetUser.id, Context.author.id, Context.guild.id, self.IsMacroMasterOrAdmin(Context))
            if (SharedEntry is not None):
                SuccessEmbed: Discord.Embed = Discord.Embed(title = "Server Snippet Shared", description = f"Server snippet **`{SharedEntry.Name}`** collaborator added: <@{TargetUser.id}>.\nCollaborators: {", ".join(SharedEntry.CollaboratorIDs)}", color = COLOR_SNIPPET_EMBED)
                await Context.send(embed = SuccessEmbed)

            else:
                await Context.send(f"Server snippet **`{TargetName}`** could not be found.")

        except PermissionError:
            await Context.send(f"You do not have permission to share server snippet **`{TargetName}`**.")

    @ServerSnippetSubGroup.command(name = "remove", aliases = ["delete"])
    @Commands.check(CheckDND5EPrefix)
    async def RemoveServerSnippet(self, Context: Commands.Context, TargetName: str) -> None:
        if (Context.guild is None):
            await Context.send("Server snippets can only be deleted within a guild.")
            return

        try:
            IsDeleted: bool = await self.AliasingService.DeleteServerSnippetAsync(Context.guild.id, TargetName, Context.author.id, self.IsMacroMasterOrAdmin(Context))
            if IsDeleted:
                await Context.send(f"Server snippet **`{TargetName.lower()}`** removed successfully.")

            else:
                await Context.send(f"Could not find server snippet **`{TargetName}`**.")

        except PermissionError:
            await Context.send(f"You do not have permission to delete server snippet **`{TargetName}`**.")

    @Commands.group(name = "uvar", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def UserVariableGroup(self, Context: Commands.Context, VariableName: Typing.Optional[str] = None, *, VariableValue: Typing.Optional[str] = None) -> None:
        UserKey: str = str(Context.author.id)
        if (VariableName is None):
            await self.ListUserVariables(Context)
            return

        if (VariableValue is not None):
            try:
                await self.PlatformClient.SaveUserVariable(UserKey, VariableName, VariableValue)
                await Context.send(f"Saved user variable **`{VariableName}`** = `{VariableValue}`.")

            except Exception as Error:
                await Context.send(f"Failed to save user variable: {str(Error)}")

            return

        try:
            ResultData: dict[str, Typing.Any] = await self.PlatformClient.FetchUserVariables(UserKey, VariableName)
            Value     : Typing.Any            = ResultData.get("Value")
            await Context.send(f"User variable **`{VariableName}`** = `{Value}`")

        except Exception:
            await Context.send(f"User variable **`{VariableName}`** not found.")

    @UserVariableGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListUserVariables(self, Context: Commands.Context) -> None:
        UserKey: str = str(Context.author.id)
        try:
            ResultData  : dict[str, Typing.Any] = await self.PlatformClient.FetchUserVariables(UserKey)
            VariablesMap: dict[str, Typing.Any] = ResultData.get("Variables", {})
            ListEmbed   : Discord.Embed         = Discord.Embed(title = f"{Context.author.display_name} • User Variables", color = COLOR_COUNTER_EMBED)

            if VariablesMap:
                Lines: list[str] = [f"• **`{K}`**: `{V}`" for K, V in VariablesMap.items()]
                ListEmbed.description = "\n".join(Lines)

            else:
                ListEmbed.description = "No user variables set."

            ListEmbed.set_footer(text = "Tally │ Variables (&uvar)")
            await Context.send(embed = ListEmbed)

        except Exception as Error:
            await Context.send(f"Failed to fetch user variables: {str(Error)}")

    @UserVariableGroup.command(name = "delete", aliases = ["remove"])
    @Commands.check(CheckDND5EPrefix)
    async def DeleteUserVariable(self, Context: Commands.Context, VariableName: str) -> None:
        UserKey: str = str(Context.author.id)
        try:
            await self.PlatformClient.SaveUserVariable(UserKey, VariableName, None)
            await Context.send(f"Deleted user variable **`{VariableName}`**.")

        except Exception as Error:
            await Context.send(f"Failed to delete user variable: {str(Error)}")

    @Commands.group(name = "svar", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def ServerVariableGroup(self, Context: Commands.Context, VariableName: Typing.Optional[str] = None, *, VariableValue: Typing.Optional[str] = None) -> None:
        if (Context.guild is None):
            await Context.send("Server variables can only be viewed or modified within a guild.")
            return

        ServerKey: str = str(Context.guild.id)
        if (VariableName is None):
            await self.ListServerVariables(Context)
            return

        if (VariableValue is not None):
            if not self.IsMacroMasterOrAdmin(Context):
                await Context.send("You require Manage Server permission or Macro Master role to modify server variables.")
                return

            try:
                await self.PlatformClient.SaveServerVariable(ServerKey, VariableName, VariableValue)
                await Context.send(f"Saved server variable **`{VariableName}`** = `{VariableValue}` for **{Context.guild.name}**.")

            except Exception as Error:
                await Context.send(f"Failed to save server variable: {str(Error)}")

            return

        try:
            ResultData: dict[str, Typing.Any] = await self.PlatformClient.FetchServerVariables(ServerKey, VariableName)
            Value     : Typing.Any            = ResultData.get("Value")
            await Context.send(f"Server variable **`{VariableName}`** = `{Value}`")

        except Exception:
            await Context.send(f"Server variable **`{VariableName}`** not found.")

    @ServerVariableGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListServerVariables(self, Context: Commands.Context) -> None:
        if (Context.guild is None):
            await Context.send("Server variables can only be listed within a guild.")
            return

        ServerKey: str = str(Context.guild.id)
        try:
            ResultData  : dict[str, Typing.Any] = await self.PlatformClient.FetchServerVariables(ServerKey)
            VariablesMap: dict[str, Typing.Any] = ResultData.get("Variables", {})
            ListEmbed   : Discord.Embed         = Discord.Embed(title = f"{Context.guild.name} • Server Variables", color = COLOR_COUNTER_EMBED)

            if VariablesMap:
                Lines: list[str] = [f"• **`{K}`**: `{V}`" for K, V in VariablesMap.items()]
                ListEmbed.description = "\n".join(Lines)

            else:
                ListEmbed.description = "No server variables set."

            ListEmbed.set_footer(text = "Tally │ Variables (&svar)")
            await Context.send(embed = ListEmbed)

        except Exception as Error:
            await Context.send(f"Failed to fetch server variables: {str(Error)}")

    @ServerVariableGroup.command(name = "delete", aliases = ["remove"])
    @Commands.check(CheckDND5EPrefix)
    async def DeleteServerVariable(self, Context: Commands.Context, VariableName: str) -> None:
        if (Context.guild is None):
            await Context.send("Server variables can only be modified within a guild.")
            return

        if not self.IsMacroMasterOrAdmin(Context):
            await Context.send("You require Manage Server permission or Macro Master role to delete server variables.")
            return

        ServerKey: str = str(Context.guild.id)
        try:
            await self.PlatformClient.SaveServerVariable(ServerKey, VariableName, None)
            await Context.send(f"Deleted server variable **`{VariableName}`** from **{Context.guild.name}**.")

        except Exception as Error:
            await Context.send(f"Failed to delete server variable: {str(Error)}")

    @Commands.group(name = "gvar", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def GlobalVariableGroup(self, Context: Commands.Context, GvarID: Typing.Optional[str] = None) -> None:
        if (GvarID is None):
            await Context.send(f"Usage: `{Context.prefix}gvar <id>` or `{Context.prefix}gvar create <content>`")
            return

        try:
            ResultData: dict[str, Typing.Any] = await self.PlatformClient.FetchGlobalVariable(GvarID)
            Content   : str                   = str(ResultData.get("Content", ""))
            Name      : str                   = str(ResultData.get("Name", "Global Variable"))
            Embed     : Discord.Embed         = Discord.Embed(title = f"GVAR • {Name}", description = f"```\n{Content[:2000]}\n```", color = COLOR_COUNTER_EMBED)
            Embed.set_footer(text = f"ID: {GvarID} │ Tally Global Variable")
            await Context.send(embed = Embed)

        except Exception:
            await Context.send(f"Global variable **`{GvarID}`** not found.")

    @GlobalVariableGroup.command(name = "create")
    @Commands.check(CheckDND5EPrefix)
    async def CreateGlobalVariable(self, Context: Commands.Context, *, Content: str) -> None:
        try:
            CreatedID: str           = await self.PlatformClient.CreateGlobalVariable(Content = Content, OwnerID = str(Context.author.id))
            Embed    : Discord.Embed = Discord.Embed(title = "Global Variable Created", description = f"GVAR successfully registered.\n\n**ID:** `{CreatedID}`\nUse in Draconic scripts with `gvar(\"{CreatedID}\")`.", color = COLOR_COUNTER_EMBED)
            await Context.send(embed = Embed)

        except Exception as Error:
            await Context.send(f"Failed to create global variable: {str(Error)}")

    @GlobalVariableGroup.command(name = "edit")
    @Commands.check(CheckDND5EPrefix)
    async def EditGlobalVariable(self, Context: Commands.Context, GvarID: str, *, Content: str) -> None:
        try:
            UpdatedID: str           = await self.PlatformClient.CreateGlobalVariable(Content = Content, ID = GvarID, OwnerID = str(Context.author.id))
            Embed    : Discord.Embed = Discord.Embed(title = "Global Variable Updated", description = f"GVAR `{UpdatedID}` updated successfully.\n\n**Content:**\n```\n{Content[:2000]}\n```", color = COLOR_COUNTER_EMBED)
            await Context.send(embed = Embed)

        except Exception as Error:
            await Context.send(f"Failed to update global variable: {str(Error)}")

    @GlobalVariableGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListGlobalVariables(self, Context: Commands.Context) -> None:
        Embed: Discord.Embed = Discord.Embed(title = "Global Variables (GVAR)", description = f"Global variables are UUID-addressed data blobs referenced by Draconic scripts.\n\n• Look up: `{Context.prefix}gvar <uuid>`\n• Create: `{Context.prefix}gvar create <content>`\n• Edit: `{Context.prefix}gvar edit <uuid> <content>`", color = COLOR_COUNTER_EMBED)
        await Context.send(embed = Embed)

    @Commands.group(name = "cc", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def CustomCounterGroup(self, Context: Commands.Context, CounterName: Typing.Optional[str] = None, DeltaText: Typing.Optional[str] = None) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)

        if (CounterName is None):
            await self.ListCounters(Context)
            return

        if not Manager.CounterExists(CounterName):
            await Context.send(f"Counter **`{CounterName}`** does not exist on {ActiveCharacter.get("Name")}.")
            return

        if (DeltaText is not None):
            try:
                CleanDelta: int = int(DeltaText.strip().lstrip("+"))
                Manager.ModifyCounter(CounterName, CleanDelta)
                FormattedText: str = Manager.FormatCounter(CounterName)
                await Context.send(f"**{ActiveCharacter.get("Name")}**: **`{CounterName}`** modified by {DeltaText} (➔ **{FormattedText}**).")
                return

            except ValueError:
                await Context.send(f"Invalid delta value: `{DeltaText}`. Expected an integer (e.g. `-1` or `+2`).")
                return

        FormattedValue: str = Manager.FormatCounter(CounterName)
        StyleName     : str = Manager.GetCounterDisplayStyle(CounterName)
        await Context.send(f"**{ActiveCharacter.get("Name")}**: **`{CounterName}`**: **{FormattedValue}** *({StyleName})*")

    @CustomCounterGroup.command(name = "create")
    @Commands.check(CheckDND5EPrefix)
    async def CreateCounter(self, Context: Commands.Context, CounterName: str, *, OptionsText: str = "") -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)

        MinValue    : Typing.Optional[int] = 0
        MaxValue    : Typing.Optional[int] = None
        ResetOn     : str                  = "LongRest"
        DisplayStyle: Typing.Optional[str] = None
        Tokens      : list[str]            = OptionsText.split()
        Index       : int                  = 0

        while (Index < len(Tokens)):
            Token: str = Tokens[Index].lower()
            if (Token in ["-max", "--max"]) and (Index + 1 < len(Tokens)):
                if Tokens[Index + 1].lstrip("-").isdigit():
                    MaxValue = int(Tokens[Index + 1])

                Index += 2

            elif (Token in ["-min", "--min"]) and (Index + 1 < len(Tokens)):
                if Tokens[Index + 1].lstrip("-").isdigit():
                    MinValue = int(Tokens[Index + 1])

                Index += 2

            elif (Token in ["-reset", "--reset"]) and (Index + 1 < len(Tokens)):
                ResetOn = Tokens[Index + 1]
                Index += 2

            elif (Token in ["-display", "--display", "-s", "--style"]) and (Index + 1 < len(Tokens)):
                DisplayStyle = Tokens[Index + 1]
                Index += 2

            else:
                Index += 1

        Manager.CreateCounter(CounterName, MinValue = MinValue, MaxValue = MaxValue, ResetOn = ResetOn, DisplayStyle = DisplayStyle)
        FormattedPreview: str = Manager.FormatCounter(CounterName)
        StyleUsed       : str = Manager.GetCounterDisplayStyle(CounterName)
        await Context.send(f"Created counter **`{CounterName}`** on {ActiveCharacter.get("Name")}: **{FormattedPreview}** (style: {StyleUsed}).")

    @CustomCounterGroup.command(name = "display", aliases = ["style"])
    @Commands.check(CheckDND5EPrefix)
    async def DisplayCounter(self, Context: Commands.Context, CounterName: str, DisplayStyle: Typing.Optional[str] = None) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)
        if not Manager.CounterExists(CounterName):
            await Context.send(f"Counter **`{CounterName}`** does not exist on {ActiveCharacter.get("Name")}.")
            return

        if (DisplayStyle is not None):
            CleanStyle: str = DisplayStyle.strip().lower()
            if CleanStyle not in CounterManager.VALID_DISPLAY_STYLES:
                await Context.send(f"Invalid display style `{DisplayStyle}`. Valid options: {", ".join(f"`{StyleName}`" for StyleName in CounterManager.VALID_DISPLAY_STYLES)}.")
                return

            Manager.SetCounterDisplayStyle(CounterName, CleanStyle)
            FormattedPreview: str = Manager.FormatCounter(CounterName)
            await Context.send(f"Updated display style for **`{CounterName}`** on {ActiveCharacter.get("Name")} to **{CleanStyle}**: **{FormattedPreview}**")
            return

        CurrentStyle    : Typing.Any = Manager.GetCounterDisplayStyle(CounterName)
        FormattedPreview             = Manager.FormatCounter(CounterName)
        await Context.send(f"**{ActiveCharacter.get("Name")}**: **`{CounterName}`** display style is **{CurrentStyle}**: **{FormattedPreview}**")

    @CustomCounterGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListCounters(self, Context: Commands.Context) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager : CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)
        Counters: dict[str, dict[str, Typing.Any]]    = Manager.CustomCounters

        ListEmbed: Discord.Embed = Discord.Embed(title = f"{ActiveCharacter.get("Name")} • Custom Counters", color = COLOR_COUNTER_EMBED)
        if Counters:
            Lines: list[str] = []
            for Name in Counters.keys():
                FormattedText: str = Manager.FormatCounter(Name)
                StyleUsed    : str = Manager.GetCounterDisplayStyle(Name)
                Lines.append(f"• **`{Name}`**: {FormattedText} *({StyleUsed})*")

            ListEmbed.description = "\n".join(Lines)

        else:
            ListEmbed.description = "No custom counters configured."

        ListEmbed.set_footer(text = f"Tally │ Resource Counters ({Context.prefix}cc)")
        await Context.send(embed = ListEmbed)

    @CustomCounterGroup.command(name = "delete", aliases = ["remove"])
    @Commands.check(CheckDND5EPrefix)
    async def DeleteCounter(self, Context: Commands.Context, CounterName: str) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)
        Deleted: bool                                = Manager.DeleteCounter(CounterName)
        if Deleted:
            await Context.send(f"Deleted counter **`{CounterName}`** from {ActiveCharacter.get("Name")}.")

        else:
            await Context.send(f"Counter **`{CounterName}`** not found.")

    @CustomCounterGroup.command(name = "reset")
    @Commands.check(CheckDND5EPrefix)
    async def ResetCounter(self, Context: Commands.Context, CounterName: Typing.Optional[str] = None) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)
        if (CounterName is not None):
            if not Manager.CounterExists(CounterName):
                await Context.send(f"Counter **`{CounterName}`** not found.")
                return

            ResetValue: int = Manager.ResetCounter(CounterName)
            await Context.send(f"Reset **`{CounterName}`** to **{ResetValue}** on {ActiveCharacter.get("Name")}.")

        else:
            for Name in list(Manager.CustomCounters.keys()):
                Manager.ResetCounter(Name)

            await Context.send(f"Reset all custom counters on {ActiveCharacter.get("Name")}.")

    @Commands.group(name = "cvar", invoke_without_command = True)
    @Commands.check(CheckDND5EPrefix)
    async def CharacterVariableGroup(self, Context: Commands.Context, VariableName: Typing.Optional[str] = None, *, VariableValue: Typing.Optional[str] = None) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)

        if (VariableName is None):
            await self.ListVariables(Context)
            return

        if (VariableValue is not None):
            Manager.SetVariable(VariableName, VariableValue)
            await Context.send(f"Set **`{VariableName}`** = `{VariableValue}` on {ActiveCharacter.get("Name")}.")
            return

        CounterValue: Typing.Any = Manager.GetVariable(VariableName)
        if (CounterValue is not None):
            await Context.send(f"**{ActiveCharacter.get("Name")}**: **`{VariableName}`** = `{CounterValue}`")

        else:
            await Context.send(f"Variable **`{VariableName}`** not found on {ActiveCharacter.get("Name")}.")

    @CharacterVariableGroup.command(name = "list")
    @Commands.check(CheckDND5EPrefix)
    async def ListVariables(self, Context: Commands.Context) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager  : CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)
        Variables: dict[str, Typing.Any]               = Manager.Variables

        ListEmbed: Discord.Embed = Discord.Embed(title = f"{ActiveCharacter.get("Name")} • Character Variables", color = COLOR_COUNTER_EMBED)
        if Variables:
            Lines: list[str] = [f"• **`{K}`**: `{V}`" for K, V in Variables.items()]
            ListEmbed.description = "\n".join(Lines)

        else:
            ListEmbed.description = "No character variables set."

        ListEmbed.set_footer(text = "Tally │ Variables (&cvar)")
        await Context.send(embed = ListEmbed)

    @CharacterVariableGroup.command(name = "delete", aliases = ["remove"])
    @Commands.check(CheckDND5EPrefix)
    async def DeleteVariable(self, Context: Commands.Context, VariableName: str) -> None:
        ActiveCharacter: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveCharacter is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveCharacter, self.CharacterStateService.PlatformClient)
        Deleted: bool                                = Manager.DeleteVariable(VariableName)
        if Deleted:
            await Context.send(f"Deleted variable **`{VariableName}`** from {ActiveCharacter.get("Name")}.")

        else:
            await Context.send(f"Variable **`{VariableName}`** not found.")

async def setup(BotInstance: Commands.Bot) -> None:
    AliasingServiceInstance: Typing.Optional[Aliasing.AliasingService]             = getattr(BotInstance, "AliasingService", None)
    CharacterStateService  : Typing.Optional[CharacterState.CharacterStateService] = getattr(BotInstance, "CharacterStateService", None)
    await BotInstance.add_cog(AliasingCommands(BotInstance, AliasingServiceInstance = AliasingServiceInstance, CharacterStateServiceInstance = CharacterStateService))
