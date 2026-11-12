import datetime                          as DateTime
import typing                            as Typing
import discord                           as Discord
import discord.ext.commands              as Commands
import Configuration.Config              as Config
import Services.DebugService             as Debug
import Services.CharacterStateService    as CharacterStateService
import Services.EncounterManagerService  as EncounterManagerService
import Services.DraconicScriptService    as DraconicScriptService
import Services.AliasingService          as AliasingService
import Services.TravellerStateService    as TravellerStateService

class MISBotClient(Commands.Bot):
    def __init__(self) -> None:
        IntentsInstance: Discord.Intents = Discord.Intents.default()
        IntentsInstance.message_content  = True
        IntentsInstance.guilds           = True
        IntentsInstance.members          = True
        super().__init__(command_prefix = Commands.when_mentioned_or(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND, Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER), intents = IntentsInstance, help_command = None)
        self.StartedAt            : DateTime.datetime                           = DateTime.datetime.now(DateTime.timezone.utc)
        self.CharacterStateService: CharacterStateService.CharacterStateService = CharacterStateService.CharacterStateService()
        self.TravellerStateService: TravellerStateService.TravellerStateService = TravellerStateService.TravellerStateService()
        self.EncounterManager     : EncounterManagerService.EncounterManagerService = EncounterManagerService.EncounterManagerService()
        self.AliasingService      : AliasingService.AliasingService             = AliasingService.AliasingService()

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
        await self.load_extension("Application.Commands.Traveller2E.DiceCommands")
        await self.load_extension("Application.Commands.Traveller2E.CharacterCommands")
        await self.load_extension("Application.Commands.Traveller2E.CheckCommands")
        await self.load_extension("Application.Commands.Traveller2E.CombatCommands")
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = "Application Command Extensions Loaded")

    async def on_ready(self) -> None:
        BotUsername: str = self.user.name if (self.user is not None) else "Unknown"
        GuildCount : int = len(self.guilds)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Gateway Connection Established: Username=\"{BotUsername}\", GuildCount={GuildCount}")
        ActivityInstance: Discord.Activity = Discord.Activity(type = Discord.ActivityType.listening, name = f"{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}r (D&D) | {Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}r (Traveller)")
        await self.change_presence(activity = ActivityInstance, status = Discord.Status.online)

    async def on_message(self, DiscordMessage: Discord.Message) -> None:
        if DiscordMessage.author.bot:
            return

        MessageContent: str                          = DiscordMessage.content.strip()
        BotUser       : Typing.Optional[Discord.ClientUser] = self.user
        MentionTokens : Typing.List[str]             = [f"<@{BotUser.id}>", f"<@!{BotUser.id}>"] if (BotUser is not None) else []

        for MentionToken in MentionTokens:
            if (MessageContent == MentionToken):
                await self.SendMentionHelpEmbed(DiscordMessage)
                return

            if MessageContent.startswith(MentionToken):
                Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Bot Mention Command Intercepted: Content=\"{MessageContent[:30]}\"")
                await self.process_commands(DiscordMessage)
                return

        if MessageContent.startswith(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER):
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Traveller Command Prefix Intercepted: Message=\"{MessageContent[:25]}\"")
            PrefixLength : int       = len(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER)
            RestOfMessage: str       = MessageContent[PrefixLength:].strip()
            TokensList   : list[str] = RestOfMessage.split(" ", 1)
            CommandName  : str       = TokensList[0].lower()
            ArgumentsText: str       = TokensList[1].strip() if (len(TokensList) > 1) else ""

            TravellerCommandMap: dict[str, str] = {
                "r"        : "trav_r",
                "roll"     : "trav_roll",
                "c"        : "trav_c",
                "check"    : "trav_check",
                "sheet"    : "trav_sheet",
                "char"     : "trav_char",
                "character": "trav_character",
                "inv"      : "trav_inv",
                "inventory": "trav_inventory",
                "damage"   : "trav_damage",
                "dmg"      : "trav_dmg",
                "wound"    : "trav_wound",
                "heal"     : "trav_heal",
                "stat"     : "trav_stat",
                "credits"  : "trav_credits",
                "init"     : "trav_init"
            }

            if CommandName in TravellerCommandMap:
                TargetInternalName    : str = TravellerCommandMap[CommandName]
                DiscordMessage.content      = f"{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}{TargetInternalName} {ArgumentsText}".strip()

            await self.process_commands(DiscordMessage)
            return

        if MessageContent.startswith(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND):
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"DND5E Command Prefix Intercepted: Message=\"{MessageContent[:25]}\"")
            SplitTokens: list[str] = MessageContent.split(" ", 1)
            if (len(SplitTokens) > 1):
                ExpandedArguments: str = self.AliasingService.ExpandSnippets(SplitTokens[1], DiscordMessage.author.id, DiscordMessage.guild.id if DiscordMessage.guild else None)
                DiscordMessage.content = f"{SplitTokens[0]} {ExpandedArguments}"

            await self.process_commands(DiscordMessage)
            return

    async def SendMentionHelpEmbed(self, DiscordMessage: Discord.Message) -> None:
        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Marten's Information System Bot", description = "Operational. Tabletop assistant powered by 5eTools and MIS Platform.", color = 0x0030A6)
        ResponseEmbed.add_field(name = "System Commands", value = "`@MIS-Bot ping` - Check gateway latency\n`@MIS-Bot status` - Check operational status", inline = False)
        ResponseEmbed.add_field(name = "D&D 5th Edition", value = f"`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}r <dice>` - Roll dice (e.g. `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}r 1d20+5 -adv`)\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}rr <N> <dice>` - Repeat dice rolls\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}alias <name> <content>` - Custom alias\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}snippet <name> <content>` - Inline snippet", inline = False)
        ResponseEmbed.add_field(name = "Traveller 2nd Edition", value = f"`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}r [flags]` - Roll 2d6 (e.g. `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}r -boon -diff 10`)\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}c <skill|stat>` - Skill check (e.g. `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}c Pilot DEX`)\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}sheet` - Character sheet\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}damage <N> [-attr <stat>]` - Physical damage\n`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}init <begin|join|next|end>` - Turn tracker", inline = False)
        ResponseEmbed.set_footer(text = "MIS-Bot • 5eTools & MGT2E Tabletop Engine")
        await DiscordMessage.channel.send(embed = ResponseEmbed)

    async def HandleTravellerCommand(self, DiscordMessage: Discord.Message) -> None:
        await self.process_commands(DiscordMessage)

    async def on_command_error(self, Context: Commands.Context, CommandError: Commands.CommandError) -> None:
        if isinstance(CommandError, Commands.CommandNotFound):
            InvokedAliasName: str = str(Context.invoked_with).lower()
            Debug.LogMessage(Level = Debug.LogLevel.Debug, Message = f"Command Not Found, Checking Aliases: InvokedWith=\"{InvokedAliasName}\"")

            FoundAlias: Typing.Optional[AliasingService.AliasEntry] = self.AliasingService.GetAlias(InvokedAliasName, Context.author.id, Context.guild.id if Context.guild else None)
            if (FoundAlias is not None):
                ActiveChar: Typing.Optional[dict] = await self.CharacterStateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
                Encounter : Typing.Optional[EncounterManagerService.CombatEncounter] = self.EncounterManager.GetEncounter(Context.channel.id)

                PrefixText          : str       = Context.prefix if (Context.prefix is not None) else Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND
                RawMessageContent   : str       = Context.message.content.strip()
                MessageWithoutPrefix: str       = RawMessageContent[len(PrefixText):].strip()
                ArgumentsTokens     : list[str] = MessageWithoutPrefix.split(" ", 1)
                RawArguments        : str       = ArgumentsTokens[1].strip() if (len(ArgumentsTokens) > 1) else ""

                EvaluationContext: DraconicScriptService.DraconicEvaluationContext = DraconicScriptService.DraconicEvaluationContext(
                    CharacterData   = ActiveChar,
                    EncounterData   = Encounter,
                    AuthorID        = str(Context.author.id),
                    AuthorName      = Context.author.display_name,
                    ChannelID       = str(Context.channel.id),
                    ArgumentsString = RawArguments
                )

                ExecutedResult: str = self.AliasingService.ExecuteAlias(FoundAlias, RawArguments, EvaluationContext)
                if ExecutedResult:
                    if ExecutedResult.startswith(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND):
                        Context.message.content = ExecutedResult
                        await self.process_commands(Context.message)

                    else:
                        await Context.send(ExecutedResult)

                return

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
