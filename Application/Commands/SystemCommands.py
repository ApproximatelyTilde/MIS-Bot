import datetime             as DateTime
import discord              as Discord
import discord.ext.commands as Commands
import Configuration.Config as Config
import Services.DebugService as Debug

def CheckBotMention(Context: Commands.Context) -> bool:
    ValidMentions: tuple[str, ...] = Commands.when_mentioned(Context.bot, Context.message)
    return (Context.prefix in ValidMentions)

class SystemCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot) -> None:
        self.BotInstance: Commands.Bot = BotInstance

    @Commands.command(name = "ping")
    @Commands.check(CheckBotMention)
    async def PingCommand(self, Context: Commands.Context) -> None:
        LatencyMilliseconds: int = round(self.BotInstance.latency * 1000)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"System Mention Ping Executed: Latency={LatencyMilliseconds}ms, UserID={Context.author.id}")
        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Pong!", description = f"Gateway Latency: {LatencyMilliseconds} ms", color = 0x0030A6)
        ResponseEmbed.set_footer(text = "MIS-Bot • System Diagnostics")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "status")
    @Commands.check(CheckBotMention)
    async def StatusCommand(self, Context: Commands.Context) -> None:
        LatencyMilliseconds: int = round(self.BotInstance.latency * 1000)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"System Mention Status Executed: UserID={Context.author.id}")
        ResponseEmbed: Discord.Embed = Discord.Embed(title = "Marten's Information System Bot - Status", description = "Operational - Gateway Connected", color = 0x0030A6)
        ResponseEmbed.add_field(name = "Environment", value = Config.GLOBAL_SETTINGS.ENVIRONMENT, inline = True)
        ResponseEmbed.add_field(name = "D&D 5E Prefix", value = f"`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}`", inline = True)
        ResponseEmbed.add_field(name = "Traveller 2E Prefix", value = f"`{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}`", inline = True)
        ResponseEmbed.add_field(name = "Platform URL", value = Config.GLOBAL_SETTINGS.PLATFORM_API_URL, inline = False)
        ResponseEmbed.add_field(name = "Gateway Latency", value = f"{LatencyMilliseconds} ms", inline = True)
        ResponseEmbed.set_footer(text = "MIS-Bot • Mention Commands")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(SystemCommands(BotInstance))

