import datetime                         as DateTime
import typing                           as Typing
import discord                          as Discord
import discord.ext.commands             as Commands
import Configuration.Config             as Config
import Services.DebugService            as Debug
import Services.CharacterStateService   as CharacterState
import Services.EncounterManagerService as EncounterManager
import Services.DraconicScriptService   as DraconicScript
import Services.AliasingService         as Aliasing
import Services.MGT2EStateService       as MGT2EState
import Services.ServerSettingsService   as ServerSettings
import Services.RateLimitService        as RateLimit
import Decorators.RateLimitDecorator    as RateLimitDecorator

def GetDynamicPrefixes(BotInstance: Commands.Bot, DiscordMessage: Discord.Message) -> list[str]:
    GuildID               : Typing.Optional[int]                                = DiscordMessage.guild.id if (DiscordMessage.guild is not None) else None
    ServerSettingsInstance: Typing.Optional[ServerSettings.ServerSettingsService] = getattr(BotInstance, "ServerSettingsService", None)
    PrefixDND5E           : str                                                 = ServerSettingsInstance.GetCachedDND5EPrefix(GuildID) if (ServerSettingsInstance is not None) else Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E
    PrefixMGT2E           : str                                                 = ServerSettingsInstance.GetCachedMGT2EPrefix(GuildID) if (ServerSettingsInstance is not None) else Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E
    MentionPrefixes       : list[str]                                           = Commands.when_mentioned(BotInstance, DiscordMessage)
    return MentionPrefixes + [PrefixDND5E, PrefixMGT2E]

class MISBotClient(Commands.Bot):
    def __init__(self) -> None:
        IntentsInstance: Discord.Intents = Discord.Intents.default()
        IntentsInstance.message_content  = True
        IntentsInstance.guilds           = True
        IntentsInstance.members          = True
        super().__init__(command_prefix = GetDynamicPrefixes, intents = IntentsInstance, help_command = None)
        self.StartedAt            : DateTime.datetime                                         = DateTime.datetime.now(DateTime.timezone.utc)
        self.ServerSettingsService: ServerSettings.ServerSettingsService                      = ServerSettings.ServerSettingsService()
        self.CharacterStateService: CharacterState.CharacterStateService                      = CharacterState.CharacterStateService()
        self.MGT2EStateService    : MGT2EState.MGT2EStateService                              = MGT2EState.MGT2EStateService()
        self.EncounterManager     : EncounterManager.EncounterManagerService                  = EncounterManager.EncounterManagerService()
        self.AliasingService      : Aliasing.AliasingService                                  = Aliasing.AliasingService()
        self.RateLimitService     : RateLimit.RateLimitService                                = RateLimit.RateLimitService()
        self.DND5ECommands        : dict[str, Commands.Command[Typing.Any, ..., Typing.Any]] = dict()
        self.MGT2ECommands        : dict[str, Commands.Command[Typing.Any, ..., Typing.Any]] = dict()

    def add_command(self, command: Commands.Command[Typing.Any, ..., Typing.Any]) -> None:
        CogModule: str = getattr(command.cog, "__module__", "")
        if ("MGT2E" in CogModule):
            self.MGT2ECommands[command.name] = command
            for Alias in command.aliases:
                self.MGT2ECommands[Alias] = command

            return

        if ("DND5E" in CogModule):
            self.DND5ECommands[command.name] = command
            for Alias in command.aliases:
                self.DND5ECommands[Alias] = command

            return

        super().add_command(command)

    def remove_command(self, name: str) -> Typing.Optional[Commands.Command[Typing.Any, ..., Typing.Any]]:
        RemovedCommand: Typing.Optional[Commands.Command[Typing.Any, ..., Typing.Any]] = super().remove_command(name)
        self.MGT2ECommands.pop(name, None)
        self.DND5ECommands.pop(name, None)
        return RemovedCommand

    async def get_context(self, origin: Typing.Union[Discord.Message, Discord.Interaction], /, *, cls: Typing.Type[Commands.Context] = Commands.Context) -> Commands.Context:
        ContextInstance: Commands.Context = await super().get_context(origin, cls = cls)
        if (ContextInstance.prefix is not None) and (ContextInstance.invoked_with is not None):
            GuildID    : Typing.Optional[int] = ContextInstance.guild.id if (ContextInstance.guild is not None) else None
            PrefixMGT2E: str                  = self.ServerSettingsService.GetCachedMGT2EPrefix(GuildID)
            PrefixDND5E: str                  = self.ServerSettingsService.GetCachedDND5EPrefix(GuildID)

            if (ContextInstance.prefix == PrefixMGT2E):
                ContextInstance.command = self.MGT2ECommands.get(ContextInstance.invoked_with)

            elif (ContextInstance.prefix == PrefixDND5E):
                ContextInstance.command = self.DND5ECommands.get(ContextInstance.invoked_with) or self.all_commands.get(ContextInstance.invoked_with)

        return ContextInstance

    async def setup_hook(self) -> None:
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = "Loading Application Command Extensions")
        await self.load_extension("Application.Commands.SystemCommands")
        await self.load_extension("Application.Commands.DND5E.DiceCommands")
        await self.load_extension("Application.Commands.DND5E.LookupCommands")
        await self.load_extension("Application.Commands.DND5E.CharacterCommands")
        await self.load_extension("Application.Commands.DND5E.CheckCommands")
        await self.load_extension("Application.Commands.DND5E.TrackingCommands")
        await self.load_extension("Application.Commands.DND5E.InitiativeCommands")
        await self.load_extension("Application.Commands.DND5E.ActionCommands")
        await self.load_extension("Application.Commands.DND5E.AliasingCommands")
        await self.load_extension("Application.Commands.MGT2E.DiceCommands")
        await self.load_extension("Application.Commands.MGT2E.CharacterCommands")
        await self.load_extension("Application.Commands.MGT2E.CheckCommands")
        await self.load_extension("Application.Commands.MGT2E.CombatCommands")
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = "Application Command Extensions Loaded")

    async def on_ready(self) -> None:
        BotUsername: str = self.user.name if (self.user is not None) else "Unknown"
        GuildCount : int = len(self.guilds)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Gateway Connection Established: Username=\"{BotUsername}\", GuildCount={GuildCount}")
        ActivityInstance: Discord.Activity = Discord.Activity(type = Discord.ActivityType.listening, name = f"{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}r (Dungeons & Dragons) | {Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E}r (Mongoose Traveller)")
        await self.change_presence(activity = ActivityInstance, status = Discord.Status.online)

    async def on_message(self, DiscordMessage: Discord.Message) -> None:
        if DiscordMessage.author.bot:
            return

        GuildID        : Typing.Optional[int]                      = DiscordMessage.guild.id if (DiscordMessage.guild is not None) else None
        SettingsRecord : ServerSettingsService.ServerSettingsModel = await self.ServerSettingsService.GetServerSettings(GuildID)
        PrefixDND5E    : str                                       = SettingsRecord.CommandPrefixDND5E
        PrefixMGT2E    : str                                       = SettingsRecord.CommandPrefixMGT2E

        MessageContent: str                                 = DiscordMessage.content.strip()
        BotUser       : Typing.Optional[Discord.ClientUser] = self.user
        MentionTokens : list[str]                    = [f"<@{BotUser.id}>", f"<@!{BotUser.id}>"] if (BotUser is not None) else []

        for MentionToken in MentionTokens:
            if (MessageContent == MentionToken):
                await self.SendMentionHelpEmbed(DiscordMessage, PrefixDND5E, PrefixMGT2E)
                return

            if MessageContent.startswith(MentionToken):
                Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Bot Mention Command Intercepted: Content=\"{MessageContent[:30]}\"")
                await self.process_commands(DiscordMessage)
                return

        if MessageContent.startswith(PrefixMGT2E):
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"MGT2E Command Prefix Intercepted: Message=\"{MessageContent[:25]}\"")
            await self.process_commands(DiscordMessage)
            return

        if MessageContent.startswith(PrefixDND5E):
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"DND5E Command Prefix Intercepted: Message=\"{MessageContent[:25]}\"")
            SplitTokens: list[str] = MessageContent.split(" ", 1)
            if (len(SplitTokens) > 1):
                ExpandedArguments: str = self.AliasingService.ExpandSnippets(SplitTokens[1], DiscordMessage.author.id, DiscordMessage.guild.id if (DiscordMessage.guild) else None)
                DiscordMessage.content = f"{SplitTokens[0]} {ExpandedArguments}"

            await self.process_commands(DiscordMessage)
            return

    async def SendMentionHelpEmbed(self, DiscordMessage: Discord.Message, PrefixDND5E: str, PrefixMGT2E: str) -> None:
        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Marten's Information System Bot", description = "Operational. Tabletop assistant powered by 5e.tools and MIS Platform.", color = 0x0030A6)
        ResponseEmbed.add_field(name = "System Commands", value = "`@MIS-Bot ping` - Check gateway latency\n`@MIS-Bot status` - Check operational status\n`@MIS-Bot servsettings` - Configure server prefixes and rules", inline = False)
        ResponseEmbed.add_field(name = "Dungeons & Dragons", value = f"`{PrefixDND5E}r <dice>` - Roll dice (e.g. `{PrefixDND5E}r 1d20+5 -adv`)\n`{PrefixDND5E}rr <N> <dice>` - Repeat dice rolls\n`{PrefixDND5E}alias <name> <content>` - Custom alias\n`{PrefixDND5E}snippet <name> <content>` - Inline snippet", inline = False)
        ResponseEmbed.add_field(name = "Mongoose Traveller", value = f"`{PrefixMGT2E}r [flags]` - Roll 2d6 (e.g. `{PrefixMGT2E}r -boon -diff 10`)\n`{PrefixMGT2E}c <skill|stat>` - Skill check (e.g. `{PrefixMGT2E}c Pilot DEX`)\n`{PrefixMGT2E}sheet` - Character sheet\n`{PrefixMGT2E}damage <N> [-attr <stat>]` - Physical damage\n`{PrefixMGT2E}init <begin|join|next|end>` - Turn tracker", inline = False)
        ResponseEmbed.set_footer(text = "MIS-Bot • 5e.tools & Mongoose Traveller Tabletop Engine")
        await DiscordMessage.channel.send(embed = ResponseEmbed)

    async def on_command_error(self, Context: Commands.Context, CommandError: Commands.CommandError) -> None:
        if isinstance(CommandError, Commands.CommandNotFound):
            InvokedAliasName: str = str(Context.invoked_with).lower()
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Command Not Found, Checking Aliases: InvokedWith=\"{InvokedAliasName}\"")

            FoundAlias: Typing.Optional[Aliasing.AliasEntry] = self.AliasingService.GetAlias(InvokedAliasName, Context.author.id, Context.guild.id if (Context.guild) else None)
            if (FoundAlias is not None):
                ActiveCharacter: Typing.Optional[dict]                                    = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
                Encounter      : Typing.Optional[EncounterManager.CombatEncounter]        = self.EncounterManager.GetEncounter(Context.channel.id)

                GuildID             : Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
                CachedDND5EPrefix   : str                  = self.ServerSettingsService.GetCachedDND5EPrefix(GuildID)
                PrefixText          : str                  = Context.prefix if (Context.prefix is not None) else CachedDND5EPrefix
                RawMessageContent   : str                  = Context.message.content.strip()
                MessageWithoutPrefix: str                  = RawMessageContent[len(PrefixText):].strip()
                ArgumentsTokens     : list[str]            = MessageWithoutPrefix.split(" ", 1)
                RawArguments        : str                  = ArgumentsTokens[1].strip() if (len(ArgumentsTokens) > 1) else ""

                EvaluationContext: DraconicScript.DraconicEvaluationContext = DraconicScript.DraconicEvaluationContext(CharacterData = ActiveCharacter, EncounterData = Encounter, AuthorID = str(Context.author.id), AuthorName = Context.author.display_name, ChannelID = str(Context.channel.id), ArgumentsString = RawArguments)

                ExecutedResult: str = self.AliasingService.ExecuteAlias(FoundAlias, RawArguments, EvaluationContext)
                if ExecutedResult:
                    if ExecutedResult.startswith(CachedDND5EPrefix) or ExecutedResult.startswith(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E):
                        Context.message.content = ExecutedResult
                        await self.process_commands(Context.message)

                    else:
                        await Context.send(ExecutedResult)

                return

            return

        if isinstance(CommandError, RateLimitDecorator.RateLimitExceeded):
            CooldownEmbed: Discord.Embed = RateLimitDecorator.BuildRateLimitCooldownEmbed(CommandError.WaitSeconds, CommandError.Category)
            await Context.send(embed = CooldownEmbed)
            return

        if isinstance(CommandError, Commands.CheckFailure):
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Command Check Failed: InvokedWith=\"{Context.invoked_with}\", Prefix=\"{Context.prefix}\"")
            return

        if isinstance(CommandError, Commands.MissingRequiredArgument):
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Command Missing Argument: Param=\"{CommandError.param.name}\"")
            await Context.send(f"Missing required parameter: `{CommandError.param.name}`")
            return

        Debug.LogMessage(Level = Debug.LogLevel.Error, Message = f"Unhandled Command Error: Type=\"{type(CommandError).__name__}\", Detail=\"{str(CommandError)}\"")
        await Context.send(f"An unexpected error occurred executing `{Context.invoked_with}`.")
