import typing                as Typing
import discord               as Discord
import discord.ext.commands  as Commands
import d20                   as D20Library
import Configuration.Config  as Config
import Services.DebugService as Debug
import Services.DiceService  as DiceService

COLOR_CRITICAL_HIT : int = 0x005E00
COLOR_CRITICAL_MISS: int = 0xA60000
COLOR_STANDARD_ROLL: int = 0x0030A6

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class DiceCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot) -> None:
        self.BotInstance: Commands.Bot                 = BotInstance
        self.DiceRoller : DiceService.DiceRollerService = DiceService.DiceRollerService()

    async def ExecuteRoll(self, Context: Commands.Context, DiceArguments: str) -> None:
        try:
            RollResults: Typing.List[DiceService.RollOutcome] = self.DiceRoller.EvaluateMultipleRolls(DiceArguments)
            if (len(RollResults) == 1):
                SingleResult: DiceService.RollOutcome = RollResults[0]
                EmbedColor  : int                     = COLOR_STANDARD_ROLL
                CritText    : str                     = ""
                if SingleResult.IsCriticalHit:
                    EmbedColor = COLOR_CRITICAL_HIT
                    CritText   = "\n\n🎯 **Critical Hit!**"

                elif SingleResult.IsCriticalMiss:
                    EmbedColor = COLOR_CRITICAL_MISS
                    CritText   = "\n\n💥 **Critical Miss!**"

                TitleText    : str           = f"Roll: {SingleResult.Comment}" if (SingleResult.Comment is not None) else "Dice Roll"
                ResponseEmbed: Discord.Embed = Discord.Embed(title = TitleText, description = f"{SingleResult.Breakdown}\n\n# **{SingleResult.Total}**{CritText}", color = EmbedColor)
                ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
                ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}r)")
                await Context.send(embed = ResponseEmbed)

            else:
                TitleText    : str           = f"Multi-Roll ({len(RollResults)} iterations)"
                ResponseEmbed: Discord.Embed = Discord.Embed(title = TitleText, color = COLOR_STANDARD_ROLL)
                ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
                for RollIndex, SingleResult in enumerate(RollResults):
                    CritBadge : str = " *(Critical Hit!)*" if SingleResult.IsCriticalHit else (" *(Critical Miss!)*" if SingleResult.IsCriticalMiss else "")
                    FieldName : str = f"Roll #{RollIndex + 1}"
                    FieldValue: str = f"{SingleResult.Breakdown} = **{SingleResult.Total}**{CritBadge}"
                    ResponseEmbed.add_field(name = FieldName, value = FieldValue, inline = False)

                ResponseEmbed.set_footer(text = f"MIS-Bot • D&D 5E ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}r)")
                await Context.send(embed = ResponseEmbed)

        except D20Library.errors.RollSyntaxError as SyntaxException:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Dice Syntax Error: Input=\"{DiceArguments}\", Error=\"{str(SyntaxException)}\"")
            ErrorEmbed: Discord.Embed = Discord.Embed(title = "Invalid Dice Expression", description = f"Could not parse dice formula: `{DiceArguments}`\n\nEnsure expression follows standard dice format (e.g. `1d20+5`, `4d6kh3`, `2d8+3 [Radiant]`).", color = COLOR_CRITICAL_MISS)
            await Context.send(embed = ErrorEmbed)

        except D20Library.errors.TooManyRolls:
            Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Too Many Rolls Requested: Input=\"{DiceArguments}\"")
            LimitEmbed: Discord.Embed = Discord.Embed(title = "Dice Limit Exceeded", description = "Too many dice rolled in a single expression.", color = COLOR_CRITICAL_MISS)
            await Context.send(embed = LimitEmbed)

    @Commands.command(name = "roll", aliases = ["r"])
    @Commands.check(CheckDNDPrefix)
    async def RollCommand(self, Context: Commands.Context, *, DiceArguments: str = "1d20") -> None:
        await self.ExecuteRoll(Context, DiceArguments)

    @Commands.command(name = "multiroll", aliases = ["rr"])
    @Commands.check(CheckDNDPrefix)
    async def MultiRollCommand(self, Context: Commands.Context, Iterations: int, *, DiceArguments: str = "1d20") -> None:
        CombinedArguments: str = f"{DiceArguments} -rr {Iterations}"
        await self.ExecuteRoll(Context, CombinedArguments)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(DiceCommands(BotInstance))
