import re                                 as RegularExpressions
import typing                             as Typing
import discord                            as Discord
import discord.ext.commands               as Commands
import Configuration.Config               as Config
import Services.DebugService              as Debug
import Services.MGT2EStateService         as MGT2EState
import Decorators.AuthorizationDecorators as AuthorizationDecorators

COLOR_MGT2E_EMBED  : int = 0x005E5E
COLOR_SUCCESS_EMBED: int = 0x005E00
COLOR_FAILURE_EMBED: int = 0xA60000

DIFF_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-diff|--difficulty)\s+(\d+)", RegularExpressions.IGNORECASE)
BOON_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-boon|--boon|\bboon\b|-adv|\badv\b)", RegularExpressions.IGNORECASE)
BANE_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-bane|--bane|\bbane\b|-dis|\bdis\b)", RegularExpressions.IGNORECASE)
MODIFIER_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"([+-]\s*\d+)")
COMMENT_PATTERN : RegularExpressions.Pattern = RegularExpressions.compile(r"\[(.*?)\]|#(.*)$")

class MGT2EDiceCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[MGT2EState.MGT2EStateService] = None) -> None:
        self.BotInstance : Commands.Bot                         = BotInstance
        self.StateService: MGT2EState.MGT2EStateService = StateService if (StateService is not None) else MGT2EState.MGT2EStateService()

    @Commands.command(name = "r", aliases = ["roll"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def RollCommand(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        WorkingText: str                 = ArgumentsText.strip()
        TargetDiff : Typing.Optional[int] = None
        NetBoons   : int                 = 0
        Modifier   : int                 = 0
        CommentText: Typing.Optional[str] = None

        DiffMatch = DIFF_PATTERN.search(WorkingText)
        if (DiffMatch is not None):
            TargetDiff  = int(DiffMatch.group(1))
            WorkingText = DIFF_PATTERN.sub("", WorkingText).strip()

        if BOON_PATTERN.search(WorkingText):
            NetBoons   += 1
            WorkingText = BOON_PATTERN.sub("", WorkingText).strip()

        if BANE_PATTERN.search(WorkingText):
            NetBoons   -= 1
            WorkingText = BANE_PATTERN.sub("", WorkingText).strip()

        CommentMatch = COMMENT_PATTERN.search(WorkingText)
        if (CommentMatch is not None):
            CommentText = (CommentMatch.group(1) or CommentMatch.group(2) or "").strip()
            WorkingText = COMMENT_PATTERN.sub("", WorkingText).strip()

        for ModifierMatch in MODIFIER_PATTERN.finditer(WorkingText):
            ModifierString: str = ModifierMatch.group(1).replace(" ", "")
            if ModifierString.lstrip("+-").isdigit():
                Modifier += int(ModifierString)

        EffectiveDifficulty: int = TargetDiff if (TargetDiff is not None) else MGT2EState.DEFAULT_DIFFICULTY_AVERAGE
        RollOutcome: MGT2EState.MGT2ERollOutcome = self.StateService.EvaluateRoll(Modifier = Modifier, NetBoons = NetBoons, TargetDifficulty = EffectiveDifficulty)

        EmbedColor: int = COLOR_SUCCESS_EMBED if (RollOutcome.IsSuccess) else COLOR_FAILURE_EMBED
        TitleText : str = f"Mongoose Traveller Roll: {RollOutcome.RawFormula}"
        if CommentText:
            TitleText = f"{CommentText} ({RollOutcome.RawFormula})"

        ResponseEmbed: Discord.Embed = Discord.Embed(title = TitleText, color = EmbedColor)
        ResponseEmbed.add_field(name = "Result", value = RollOutcome.BreakdownString, inline = False)
        ResponseEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = "MIS-Bot • Mongoose Traveller Engine")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[MGT2EState.MGT2EStateService] = getattr(BotInstance, "MGT2EStateService", None)
    await BotInstance.add_cog(MGT2EDiceCommands(BotInstance, StateService = StateServiceInstance))
