import datetime                           as DateTime
import typing                             as Typing
import discord                            as Discord
import discord.ext.commands               as Commands
import Configuration.Config               as Config
import Services.DebugService              as Debug
import Services.ServerSettingsService     as ServerSettings
import Decorators.AuthorizationDecorators as AuthorizationDecorators

COLOR_SYSTEM_EMBED : int = 0x0030A6
COLOR_SUCCESS_EMBED: int = 0x005E00
COLOR_ERROR_EMBED  : int = 0xA60000

def CheckBotMentionOrDND5EPrefix(Context: Commands.Context) -> bool:
    ValidMentions: tuple[str, ...] = Commands.when_mentioned(Context.bot, Context.message)
    if (Context.prefix in ValidMentions):
        return True

    return AuthorizationDecorators.CheckDND5EPrefix(Context)

class SystemCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot) -> None:
        self.BotInstance: Commands.Bot = BotInstance

    @Commands.command(name = "ping")
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    async def PingCommand(self, Context: Commands.Context) -> None:
        LatencyMilliseconds: int = round(self.BotInstance.latency * 1000)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"System Mention Ping Executed: Latency={LatencyMilliseconds}ms, UserID={Context.author.id}")
        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Pong!", description = f"Gateway Latency: {LatencyMilliseconds} ms", color = COLOR_SYSTEM_EMBED)
        ResponseEmbed.set_footer(text = "MIS-Bot • System Diagnostics")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "status")
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    async def StatusCommand(self, Context: Commands.Context) -> None:
        LatencyMilliseconds   : int                                                        = round(self.BotInstance.latency * 1000)
        ServerSettingsInstance: Typing.Optional[ServerSettings.ServerSettingsService] = getattr(self.BotInstance, "ServerSettingsService", None)
        GuildID               : Typing.Optional[int]                                       = Context.guild.id if (Context.guild is not None) else None
        PrefixDND5E           : str                                                        = ServerSettingsInstance.GetCachedDND5EPrefix(GuildID) if (ServerSettingsInstance is not None) else Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E
        PrefixMGT2E           : str                                                        = ServerSettingsInstance.GetCachedMGT2EPrefix(GuildID) if (ServerSettingsInstance is not None) else Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E

        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"System Status Executed: UserID={Context.author.id}")
        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Marten's Information System Bot - Status", description = "Operational - Gateway Connected", color = COLOR_SYSTEM_EMBED)
        ResponseEmbed.add_field(name = "Environment", value = Config.GLOBAL_SETTINGS.ENVIRONMENT, inline = True)
        ResponseEmbed.add_field(name = "Dungeons & Dragons Prefix", value = f"`{PrefixDND5E}`", inline = True)
        ResponseEmbed.add_field(name = "Mongoose Traveller Prefix", value = f"`{PrefixMGT2E}`", inline = True)
        ResponseEmbed.add_field(name = "Platform URL", value = Config.GLOBAL_SETTINGS.PLATFORM_API_URL, inline = False)
        ResponseEmbed.add_field(name = "Gateway Latency", value = f"{LatencyMilliseconds} ms", inline = True)
        ResponseEmbed.set_footer(text = "MIS-Bot • System Diagnostics")
        await Context.send(embed = ResponseEmbed)

    @Commands.group(name = "servsettings", aliases = ["serversettings"], invoke_without_command = True)
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def ServerSettingsGroup(self, Context: Commands.Context) -> None:
        await self.ViewSettings(Context)

    @ServerSettingsGroup.command(name = "view")
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def ViewSettings(self, Context: Commands.Context) -> None:
        if (Context.guild is None):
            await Context.send("Server settings can only be configured within a guild.")
            return

        ServerSettingsInstance: ServerSettings.ServerSettingsService = getattr(self.BotInstance, "ServerSettingsService", ServerSettings.ServerSettingsService())
        SettingsRecord        : ServerSettings.ServerSettingsModel   = await ServerSettingsInstance.GetServerSettings(Context.guild.id)

        RoleDisplayString: str           = f"<@&{SettingsRecord.MacroMasterRoleID}>" if (SettingsRecord.MacroMasterRoleID is not None) else f"None (Default: role named `{Config.GLOBAL_SETTINGS.PLATFORM_SUPER_USER}`)"
        ResponseEmbed    : Discord.Embed = Discord.Embed(title = f"Server Settings: {Context.guild.name}", color = COLOR_SYSTEM_EMBED)
        ResponseEmbed.add_field(name = "Dungeons & Dragons Command Prefix", value = f"`{SettingsRecord.CommandPrefixDND5E}`", inline = True)
        ResponseEmbed.add_field(name = "Mongoose Traveller Command Prefix", value = f"`{SettingsRecord.CommandPrefixMGT2E}`", inline = True)
        ResponseEmbed.add_field(name = "Rule-Set Enforcement", value = f"`{SettingsRecord.RuleSetEnforcementMode}`", inline = True)
        ResponseEmbed.add_field(name = "Macro Master Role", value = RoleDisplayString, inline = False)
        ResponseEmbed.set_footer(text = "MIS-Bot • Server Settings Configuration")
        await Context.send(embed = ResponseEmbed)

    @ServerSettingsGroup.group(name = "prefix", invoke_without_command = True)
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def PrefixGroup(self, Context: Commands.Context) -> None:
        await Context.send("Usage: `servsettings prefix dnd <prefix>` or `servsettings prefix traveller <prefix>`")

    @PrefixGroup.command(name = "dnd", aliases = ["dnd5e", "5e"])
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def SetDNDPrefix(self, Context: Commands.Context, NewPrefix: str) -> None:
        if (Context.guild is None):
            await Context.send("Server prefixes can only be configured within a guild.")
            return

        CleanPrefix           : str                                         = NewPrefix.strip()
        ServerSettingsInstance: ServerSettings.ServerSettingsService = getattr(self.BotInstance, "ServerSettingsService", ServerSettings.ServerSettingsService())
        UpdatedSettings       : ServerSettings.ServerSettingsModel   = await ServerSettingsInstance.UpdateServerSettings(Context.guild.id, CommandPrefixDND5E = CleanPrefix)

        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Dungeons & Dragons Command Prefix Updated", description = f"The Dungeons & Dragons command prefix for this server has been updated to **`{UpdatedSettings.CommandPrefixDND5E}`**.", color = COLOR_SUCCESS_EMBED)
        ResponseEmbed.set_footer(text = "MIS-Bot • Server Settings Configuration")
        await Context.send(embed = ResponseEmbed)

    @PrefixGroup.command(name = "traveller", aliases = ["mgt2e", "trav"])
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def SetTravellerPrefix(self, Context: Commands.Context, NewPrefix: str) -> None:
        if (Context.guild is None):
            await Context.send("Server prefixes can only be configured within a guild.")
            return

        CleanPrefix           : str                                  = NewPrefix.strip()
        ServerSettingsInstance: ServerSettings.ServerSettingsService = getattr(self.BotInstance, "ServerSettingsService", ServerSettings.ServerSettingsService())
        UpdatedSettings       : ServerSettings.ServerSettingsModel   = await ServerSettingsInstance.UpdateServerSettings(Context.guild.id, CommandPrefixMGT2E = CleanPrefix)

        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Mongoose Traveller Command Prefix Updated", description = f"The Mongoose Traveller command prefix for this server has been updated to **`{UpdatedSettings.CommandPrefixMGT2E}`**.", color = COLOR_SUCCESS_EMBED)
        ResponseEmbed.set_footer(text = "MIS-Bot • Server Settings Configuration")
        await Context.send(embed = ResponseEmbed)

    @ServerSettingsGroup.command(name = "ruleset", aliases = ["enforcement"])
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def SetRuleSetEnforcement(self, Context: Commands.Context, ModeName: str) -> None:
        if (Context.guild is None):
            await Context.send("Server settings can only be configured within a guild.")
            return

        ValidModes : list[str]            = ["Standard", "Nudge2024", "Strict2024", "LegacyPermissive"]
        CleanMode  : str                  = ModeName.strip()
        MatchedMode: Typing.Optional[str] = None
        for Candidate in ValidModes:
            if (Candidate.lower() == CleanMode.lower()):
                MatchedMode = Candidate
                break

        if (MatchedMode is None):
            await Context.send(f"Invalid ruleset mode `{ModeName}`. Valid modes: {", ".join(f'`{M}`' for M in ValidModes)}.")
            return

        ServerSettingsInstance: ServerSettings.ServerSettingsService = getattr(self.BotInstance, "ServerSettingsService", ServerSettings.ServerSettingsService())
        UpdatedSettings       : ServerSettings.ServerSettingsModel   = await ServerSettingsInstance.UpdateServerSettings(Context.guild.id, RuleSetEnforcementMode = MatchedMode)

        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Rule-Set Enforcement Updated", description = f"Rule-Set enforcement for this server is now set to **`{UpdatedSettings.RuleSetEnforcementMode}`**.", color = COLOR_SUCCESS_EMBED)
        ResponseEmbed.set_footer(text = "MIS-Bot • Server Settings Configuration")
        await Context.send(embed = ResponseEmbed)

    @ServerSettingsGroup.command(name = "role")
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def SetMacroMasterRole(self, Context: Commands.Context, TargetRole: Discord.Role) -> None:
        if (Context.guild is None):
            await Context.send("Server settings can only be configured within a guild.")
            return

        ServerSettingsInstance: ServerSettings.ServerSettingsService = getattr(self.BotInstance, "ServerSettingsService", ServerSettings.ServerSettingsService())
        UpdatedSettings       : ServerSettings.ServerSettingsModel   = await ServerSettingsInstance.UpdateServerSettings(Context.guild.id, MacroMasterRoleID = str(TargetRole.id))

        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Macro Master Role Updated", description = f"The Macro Master role for this server is now **`{TargetRole.name}`** (`{UpdatedSettings.MacroMasterRoleID}`).", color = COLOR_SUCCESS_EMBED)
        ResponseEmbed.set_footer(text = "MIS-Bot • Server Settings Configuration")
        await Context.send(embed = ResponseEmbed)

    @ServerSettingsGroup.command(name = "reset")
    @Commands.check(CheckBotMentionOrDND5EPrefix)
    @AuthorizationDecorators.RequireMacroMasterOrAdmin()
    async def ResetSettings(self, Context: Commands.Context) -> None:
        if (Context.guild is None):
            await Context.send("Server settings can only be reset within a guild.")
            return

        ServerSettingsInstance: ServerSettings.ServerSettingsService = getattr(self.BotInstance, "ServerSettingsService", ServerSettings.ServerSettingsService())
        ResetSettingsRecord   : ServerSettings.ServerSettingsModel   = await ServerSettingsInstance.ResetServerSettings(Context.guild.id)

        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Server Settings Reset", description = f"Server settings have been reset to system defaults.\n\n• Dungeons & Dragons Prefix: **`{ResetSettingsRecord.CommandPrefixDND5E}`**\n• Mongoose Traveller Prefix: **`{ResetSettingsRecord.CommandPrefixMGT2E}`**\n• Rule-Set: **`{ResetSettingsRecord.RuleSetEnforcementMode}`**", color = COLOR_SUCCESS_EMBED)
        ResponseEmbed.set_footer(text = "MIS-Bot • Server Settings Configuration")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(SystemCommands(BotInstance))
