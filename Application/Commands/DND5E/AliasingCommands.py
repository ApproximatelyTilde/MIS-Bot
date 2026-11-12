import typing                                as Typing
import discord                               as Discord
import discord.ext.commands                  as Commands
import Configuration.Config                  as Config
import Services.DebugService                 as Debug
import Services.AliasingService              as AliasingService
import Services.CharacterStateService        as CharacterStateService
import Services.Draconic.API.CustomCounterManager as CounterManager

COLOR_ALIAS_EMBED  : int = 0x0030A6
COLOR_SNIPPET_EMBED: int = 0x005E00
COLOR_COUNTER_EMBED: int = 0x5E005E
COLOR_ERROR_EMBED  : int = 0xA60000

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class AliasingCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, AliasingServiceInstance: Typing.Optional[AliasingService.AliasingService] = None, CharacterStateServiceInstance: Typing.Optional[CharacterStateService.CharacterStateService] = None) -> None:
        self.BotInstance          : Commands.Bot                                    = BotInstance
        self.AliasingService      : AliasingService.AliasingService                 = AliasingServiceInstance if (AliasingServiceInstance is not None) else AliasingService.AliasingService()
        self.CharacterStateService: CharacterStateService.CharacterStateService     = CharacterStateServiceInstance if (CharacterStateServiceInstance is not None) else CharacterStateService.CharacterStateService()

    @Commands.group(name = "alias", invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def AliasGroup(self, Context: Commands.Context, AliasName: Typing.Optional[str] = None, *, AliasContent: Typing.Optional[str] = None) -> None:
        if (AliasName is None) or (AliasContent is None):
            await self.ListAliases(Context)
            return

        CreatedEntry: AliasingService.AliasEntry = self.AliasingService.SetUserAlias(Context.author.id, AliasName, AliasContent)
        SuccessEmbed: Discord.Embed              = Discord.Embed(title = "Alias Created", description = f"Alias **`{CreatedEntry.Name}`** has been registered.\n\n**Definition:**\n```\n{CreatedEntry.Content}\n```\nInvoke with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}{CreatedEntry.Name}`", color = COLOR_ALIAS_EMBED)
        SuccessEmbed.set_footer(text = "MIS-Bot • Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @AliasGroup.command(name = "list")
    @Commands.check(CheckDNDPrefix)
    async def ListAliases(self, Context: Commands.Context) -> None:
        UserList  : list[AliasingService.AliasEntry] = self.AliasingService.ListUserAliases(Context.author.id)
        ServerList: list[AliasingService.AliasEntry] = self.AliasingService.ListServerAliases(Context.guild.id) if (Context.guild is not None) else []

        ListEmbed: Discord.Embed = Discord.Embed(title = "Configured Aliases", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}alias <name> <content>` to add a custom alias.", color = COLOR_ALIAS_EMBED)

        if UserList:
            UserText: str = "\n".join(f"• **`{A.Name}`**: `{A.Content[:50]}`" for A in UserList)
            ListEmbed.add_field(name = "Personal Aliases", value = UserText[:1020], inline = False)

        else:
            ListEmbed.add_field(name = "Personal Aliases", value = "No personal aliases found.", inline = False)

        if ServerList:
            ServerText: str = "\n".join(f"• **`{A.Name}`**: `{A.Content[:50]}`" for A in ServerList)
            ListEmbed.add_field(name = "Server Aliases", value = ServerText[:1020], inline = False)

        ListEmbed.set_footer(text = "MIS-Bot • Draconic Aliasing Engine")
        await Context.send(embed = ListEmbed)

    @AliasGroup.command(name = "remove", aliases = ["delete"])
    @Commands.check(CheckDNDPrefix)
    async def RemoveAlias(self, Context: Commands.Context, TargetName: str) -> None:
        IsDeleted: bool = self.AliasingService.DeleteUserAlias(Context.author.id, TargetName)
        if IsDeleted:
            await Context.send(f"Personal alias **`{TargetName.lower()}`** removed successfully.")

        else:
            await Context.send(f"Could not find personal alias **`{TargetName}`**.")

    @AliasGroup.command(name = "server")
    @Commands.check(CheckDNDPrefix)
    @Commands.has_permissions(manage_guild = True)
    async def ServerAlias(self, Context: Commands.Context, AliasName: str, *, AliasContent: str) -> None:
        if (Context.guild is None):
            await Context.send("Server aliases can only be configured within a guild.")
            return

        CreatedEntry: AliasingService.AliasEntry = self.AliasingService.SetServerAlias(Context.guild.id, Context.author.id, AliasName, AliasContent)
        SuccessEmbed: Discord.Embed              = Discord.Embed(title = "Server Alias Created", description = f"Server alias **`{CreatedEntry.Name}`** registered for this guild.\n\n**Definition:**\n```\n{CreatedEntry.Content}\n```", color = COLOR_ALIAS_EMBED)
        SuccessEmbed.set_footer(text = "MIS-Bot • Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @Commands.group(name = "snippet", invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def SnippetGroup(self, Context: Commands.Context, SnippetName: Typing.Optional[str] = None, *, SnippetContent: Typing.Optional[str] = None) -> None:
        if (SnippetName is None) or (SnippetContent is None):
            await self.ListSnippets(Context)
            return

        CreatedEntry: AliasingService.SnippetEntry = self.AliasingService.SetUserSnippet(Context.author.id, SnippetName, SnippetContent)
        SuccessEmbed: Discord.Embed                = Discord.Embed(title = "Snippet Created", description = f"Snippet **`{CreatedEntry.Name}`** registered.\n\n**Expansion:** `{CreatedEntry.Content}`\nUse inline in commands (e.g. `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}r 1d20 {CreatedEntry.Name}`)", color = COLOR_SNIPPET_EMBED)
        SuccessEmbed.set_footer(text = "MIS-Bot • Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @SnippetGroup.command(name = "list")
    @Commands.check(CheckDNDPrefix)
    async def ListSnippets(self, Context: Commands.Context) -> None:
        UserList  : list[AliasingService.SnippetEntry] = self.AliasingService.ListUserSnippets(Context.author.id)
        ServerList: list[AliasingService.SnippetEntry] = self.AliasingService.ListServerSnippets(Context.guild.id) if (Context.guild is not None) else []

        ListEmbed: Discord.Embed = Discord.Embed(title = "Configured Snippets", description = f"Use `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}snippet <name> <content>` to add a snippet.", color = COLOR_SNIPPET_EMBED)

        if UserList:
            UserText: str = "\n".join(f"• **`{S.Name}`**: `{S.Content}`" for S in UserList)
            ListEmbed.add_field(name = "Personal Snippets", value = UserText[:1020], inline = False)

        else:
            ListEmbed.add_field(name = "Personal Snippets", value = "No personal snippets found.", inline = False)

        if ServerList:
            ServerText: str = "\n".join(f"• **`{S.Name}`**: `{S.Content}`" for S in ServerList)
            ListEmbed.add_field(name = "Server Snippets", value = ServerText[:1020], inline = False)

        ListEmbed.set_footer(text = "MIS-Bot • Draconic Aliasing Engine")
        await Context.send(embed = ListEmbed)

    @SnippetGroup.command(name = "remove", aliases = ["delete"])
    @Commands.check(CheckDNDPrefix)
    async def RemoveSnippet(self, Context: Commands.Context, TargetName: str) -> None:
        IsDeleted: bool = self.AliasingService.DeleteUserSnippet(Context.author.id, TargetName)
        if IsDeleted:
            await Context.send(f"Personal snippet **`{TargetName.lower()}`** removed successfully.")

        else:
            await Context.send(f"Could not find personal snippet **`{TargetName}`**.")

    @SnippetGroup.command(name = "server")
    @Commands.check(CheckDNDPrefix)
    @Commands.has_permissions(manage_guild = True)
    async def ServerSnippet(self, Context: Commands.Context, SnippetName: str, *, SnippetContent: str) -> None:
        if (Context.guild is None):
            await Context.send("Server snippets can only be configured within a guild.")
            return

        CreatedEntry: AliasingService.SnippetEntry = self.AliasingService.SetServerSnippet(Context.guild.id, Context.author.id, SnippetName, SnippetContent)
        SuccessEmbed: Discord.Embed                = Discord.Embed(title = "Server Snippet Created", description = f"Server snippet **`{CreatedEntry.Name}`** registered for this guild.\n\n**Expansion:** `{CreatedEntry.Content}`", color = COLOR_SNIPPET_EMBED)
        SuccessEmbed.set_footer(text = "MIS-Bot • Draconic Aliasing Engine")
        await Context.send(embed = SuccessEmbed)

    @Commands.group(name = "cc", invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def CustomCounterGroup(self, Context: Commands.Context, CounterName: Typing.Optional[str] = None, DeltaText: Typing.Optional[str] = None) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)

        if (CounterName is None):
            await self.ListCounters(Context)
            return

        if not Manager.CounterExists(CounterName):
            await Context.send(f"Counter **`{CounterName}`** does not exist on {ActiveChar.get('Name')}.")
            return

        if (DeltaText is not None):
            try:
                CleanDelta: int = int(DeltaText.strip().lstrip("+"))
                NewVal    : int = Manager.ModifyCounter(CounterName, CleanDelta)
                MaxVal    : Typing.Optional[int] = Manager.GetCounterMax(CounterName)
                MaxDisplay: str = f" / {MaxVal}" if (MaxVal is not None) else ""
                await Context.send(f"**{ActiveChar.get('Name')}**: **`{CounterName}`** modified by {DeltaText} (➔ **{NewVal}**{MaxDisplay}).")
                return

            except ValueError:
                await Context.send(f"Invalid delta value: `{DeltaText}`. Expected an integer (e.g. `-1` or `+2`).")
                return

        CurrentVal: int = Manager.GetCounter(CounterName)
        MaxVal    : Typing.Optional[int] = Manager.GetCounterMax(CounterName)
        MaxDisplay: str = f" / {MaxVal}" if (MaxVal is not None) else ""
        await Context.send(f"**{ActiveChar.get('Name')}**: **`{CounterName}`**: **{CurrentVal}**{MaxDisplay}")

    @CustomCounterGroup.command(name = "create")
    @Commands.check(CheckDNDPrefix)
    async def CreateCounter(self, Context: Commands.Context, CounterName: str, *, OptionsText: str = "") -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)

        MinValue : Typing.Optional[int] = 0
        MaxValue : Typing.Optional[int] = None
        ResetOn  : str                  = "LongRest"
        Tokens   : list[str]            = OptionsText.split()
        Idx      : int                  = 0

        while (Idx < len(Tokens)):
            Token: str = Tokens[Idx].lower()
            if (Token in ["-max", "--max"]) and (Idx + 1 < len(Tokens)):
                try:
                    MaxValue = int(Tokens[Idx + 1])

                except ValueError:
                    pass

                Idx += 2

            elif (Token in ["-min", "--min"]) and (Idx + 1 < len(Tokens)):
                try:
                    MinValue = int(Tokens[Idx + 1])

                except ValueError:
                    pass

                Idx += 2

            elif (Token in ["-reset", "--reset"]) and (Idx + 1 < len(Tokens)):
                ResetOn = Tokens[Idx + 1]
                Idx += 2

            else:
                Idx += 1

        Manager.CreateCounter(CounterName, MinValue = MinValue, MaxValue = MaxValue, ResetOn = ResetOn)
        MaxDisplay: str = f" (Max: {MaxValue})" if (MaxValue is not None) else ""
        await Context.send(f"Created counter **`{CounterName}`** on {ActiveChar.get('Name')}{MaxDisplay}.")

    @CustomCounterGroup.command(name = "list")
    @Commands.check(CheckDNDPrefix)
    async def ListCounters(self, Context: Commands.Context) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager : CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)
        Counters: dict[str, dict[str, Typing.Any]]    = Manager.CustomCounters

        ListEmbed: Discord.Embed = Discord.Embed(title = f"{ActiveChar.get('Name')} • Custom Counters", color = COLOR_COUNTER_EMBED)
        if Counters:
            Lines: list[str] = []
            for Name, Data in Counters.items():
                Val: int               = int(Data.get("Value", 0))
                Max: Typing.Optional[int] = Data.get("MaxValue")
                MaxStr: str            = f" / {Max}" if (Max is not None) else ""
                Lines.append(f"• **`{Name}`**: **{Val}**{MaxStr}")

            ListEmbed.description = "\n".join(Lines)

        else:
            ListEmbed.description = "No custom counters configured."

        ListEmbed.set_footer(text = "MIS-Bot • Resource Counters (&cc)")
        await Context.send(embed = ListEmbed)

    @CustomCounterGroup.command(name = "delete", aliases = ["remove"])
    @Commands.check(CheckDNDPrefix)
    async def DeleteCounter(self, Context: Commands.Context, CounterName: str) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)
        Deleted: bool = Manager.DeleteCounter(CounterName)
        if Deleted:
            await Context.send(f"Deleted counter **`{CounterName}`** from {ActiveChar.get('Name')}.")

        else:
            await Context.send(f"Counter **`{CounterName}`** not found.")

    @CustomCounterGroup.command(name = "reset")
    @Commands.check(CheckDNDPrefix)
    async def ResetCounter(self, Context: Commands.Context, CounterName: Typing.Optional[str] = None) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)
        if (CounterName is not None):
            if not Manager.CounterExists(CounterName):
                await Context.send(f"Counter **`{CounterName}`** not found.")
                return

            ResetVal: int = Manager.ResetCounter(CounterName)
            await Context.send(f"Reset **`{CounterName}`** to **{ResetVal}** on {ActiveChar.get('Name')}.")

        else:
            for Name in list(Manager.CustomCounters.keys()):
                Manager.ResetCounter(Name)

            await Context.send(f"Reset all custom counters on {ActiveChar.get('Name')}.")

    @Commands.group(name = "cvar", invoke_without_command = True)
    @Commands.check(CheckDNDPrefix)
    async def CharacterVariableGroup(self, Context: Commands.Context, VariableName: Typing.Optional[str] = None, *, VariableValue: Typing.Optional[str] = None) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)

        if (VariableName is None):
            await self.ListVariables(Context)
            return

        if (VariableValue is not None):
            Manager.SetVariable(VariableName, VariableValue)
            await Context.send(f"Set **`{VariableName}`** = `{VariableValue}` on {ActiveChar.get('Name')}.")
            return

        Val: Typing.Any = Manager.GetVariable(VariableName)
        if (Val is not None):
            await Context.send(f"**{ActiveChar.get('Name')}**: **`{VariableName}`** = `{Val}`")

        else:
            await Context.send(f"Variable **`{VariableName}`** not found on {ActiveChar.get('Name')}.")

    @CharacterVariableGroup.command(name = "list")
    @Commands.check(CheckDNDPrefix)
    async def ListVariables(self, Context: Commands.Context) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager  : CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)
        Variables: dict[str, Typing.Any]               = Manager.Variables

        ListEmbed: Discord.Embed = Discord.Embed(title = f"{ActiveChar.get('Name')} • Character Variables", color = COLOR_COUNTER_EMBED)
        if Variables:
            Lines: list[str] = [f"• **`{K}`**: `{V}`" for K, V in Variables.items()]
            ListEmbed.description = "\n".join(Lines)

        else:
            ListEmbed.description = "No character variables set."

        ListEmbed.set_footer(text = "MIS-Bot • Variables (&cvar)")
        await Context.send(embed = ListEmbed)

    @CharacterVariableGroup.command(name = "delete", aliases = ["remove"])
    @Commands.check(CheckDNDPrefix)
    async def DeleteVariable(self, Context: Commands.Context, VariableName: str) -> None:
        ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveChar is None):
            await Context.send("You do not have an active character selected.")
            return

        Manager: CounterManager.CustomCounterManager = CounterManager.CustomCounterManager(ActiveChar, self.CharacterStateService.PlatformClient)
        Deleted: bool = Manager.DeleteVariable(VariableName)
        if Deleted:
            await Context.send(f"Deleted variable **`{VariableName}`** from {ActiveChar.get('Name')}.")

        else:
            await Context.send(f"Variable **`{VariableName}`** not found.")

async def setup(BotInstance: Commands.Bot) -> None:
    AliasingServiceInstance: Typing.Optional[AliasingService.AliasingService] = getattr(BotInstance, "AliasingService", None)
    CharStateService       : Typing.Optional[CharacterStateService.CharacterStateService] = getattr(BotInstance, "CharacterStateService", None)
    await BotInstance.add_cog(AliasingCommands(BotInstance, AliasingServiceInstance = AliasingServiceInstance, CharacterStateServiceInstance = CharStateService))
