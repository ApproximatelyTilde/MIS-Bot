import re                             as RegularExpressions
import typing                         as Typing
import discord                        as Discord
import discord.ext.commands          as Commands
import Configuration.Config           as Config
import Services.DebugService          as Debug
import Services.TravellerStateService as TravellerStateService

COLOR_SUCCESS_EMBED: int = 0x005E00
COLOR_FAILURE_EMBED: int = 0xA60000
COLOR_ERROR_EMBED  : int = 0xA60000

DIFF_PATTERN       : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-diff|--difficulty)\s+(\d+)", RegularExpressions.IGNORECASE)
BOON_PATTERN       : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-boon|--boon|\bboon\b|-adv|\badv\b)", RegularExpressions.IGNORECASE)
BANE_PATTERN       : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-bane|--bane|\bbane\b|-dis|\bdis\b)", RegularExpressions.IGNORECASE)
MODIFIER_PATTERN   : RegularExpressions.Pattern = RegularExpressions.compile(r"([+-]\s*\d+)")

def CheckTravellerPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER)

class TravellerCheckCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[TravellerStateService.TravellerStateService] = None) -> None:
        self.BotInstance  : Commands.Bot                                = BotInstance
        self.StateService : TravellerStateService.TravellerStateService = StateService if (StateService is not None) else TravellerStateService.TravellerStateService()

    @Commands.command(name = "trav_c", aliases = ["trav_check"])
    @Commands.check(CheckTravellerPrefix)
    async def CheckCommand(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active Traveller character selected.\n\nSelect one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharEmbed)
            return

        WorkingText: str = ArgumentsText.strip()
        if not WorkingText:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_TRAVELLER}c <Skill|Stat> [Stat] [-diff <N>] [-boon|-bane]`")
            return

        TargetDiff: int = TravellerStateService.DEFAULT_DIFFICULTY_AVERAGE
        DiffMatch       = DIFF_PATTERN.search(WorkingText)
        if (DiffMatch is not None):
            TargetDiff  = int(DiffMatch.group(1))
            WorkingText = DIFF_PATTERN.sub("", WorkingText).strip()

        NetBoons: int = 0
        if BOON_PATTERN.search(WorkingText):
            NetBoons   += 1
            WorkingText = BOON_PATTERN.sub("", WorkingText).strip()

        if BANE_PATTERN.search(WorkingText):
            NetBoons   -= 1
            WorkingText = BANE_PATTERN.sub("", WorkingText).strip()

        SituationalMod: int = 0
        for ModMatch in MODIFIER_PATTERN.finditer(WorkingText):
            ModString: str = ModMatch.group(1).replace(" ", "")
            try:
                SituationalMod += int(ModString)

            except ValueError:
                pass

        WorkingText = MODIFIER_PATTERN.sub("", WorkingText).strip()

        DetailData     : dict = ActiveRecord.get("DetailData", {})
        Characteristics: dict = DetailData.get("Characteristics", {})
        Skills         : dict = DetailData.get("Skills", {})
        CharName       : str  = str(ActiveRecord.get("Name", "Hero"))

        Tokens: list[str] = WorkingText.split()
        if not Tokens:
            await Context.send(f"Missing skill or characteristic name.")
            return

        FirstTokenLower: str = Tokens[0].lower()
        if FirstTokenLower in TravellerStateService.CHARACTERISTIC_LOOKUP:
            StatFullName : str = TravellerStateService.CHARACTERISTIC_LOOKUP[FirstTokenLower]
            StatScore    : int = int(Characteristics.get(StatFullName, 7))
            StatDM       : int = self.StateService.CalculateCharacteristicModifier(StatScore)
            TotalModifier: int = StatDM + SituationalMod

            RollOutcome: TravellerStateService.TravellerRollOutcome = self.StateService.EvaluateRoll(
                Modifier         = TotalModifier,
                NetBoons         = NetBoons,
                TargetDifficulty = TargetDiff
            )

            EmbedColor: int              = COLOR_SUCCESS_EMBED if RollOutcome.IsSuccess else COLOR_FAILURE_EMBED
            StatDisplay: str             = f"{StatFullName} Check"
            ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharName}: {StatDisplay}", color = EmbedColor)
            BreakdownText: str           = f"{RollOutcome.BreakdownString}\n*(Stat DM: {'+' if StatDM >= 0 else ''}{StatDM}{f', Mod: {SituationalMod:+d}' if SituationalMod != 0 else ''})*"
            ResponseEmbed.add_field(name = "Result", value = BreakdownText, inline = False)
            ResponseEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
            ResponseEmbed.set_footer(text = "MIS-Bot • MGT2E Check Engine")
            await Context.send(embed = ResponseEmbed)
            return

        SecondTokenIsStat: bool                       = (len(Tokens) > 1) and (Tokens[-1].lower() in TravellerStateService.CHARACTERISTIC_LOOKUP)
        SelectedStatName : Typing.Optional[str]       = None
        SkillTokens      : list[str]                  = Tokens[:]

        if SecondTokenIsStat:
            SelectedStatName = TravellerStateService.CHARACTERISTIC_LOOKUP[Tokens[-1].lower()]
            SkillTokens      = Tokens[:-1]

        SkillQueryName: str = " ".join(SkillTokens).strip()
        if not SelectedStatName:
            SelectedStatName = self.StateService.GetDefaultCharacteristicForSkill(SkillQueryName)

        SkillModifier: int = self.StateService.GetSkillModifier(Skills, SkillQueryName)
        StatScoreValue: int = int(Characteristics.get(SelectedStatName, 7))
        StatDMValue  : int = self.StateService.CalculateCharacteristicModifier(StatScoreValue)
        TotalModifier = SkillModifier + StatDMValue + SituationalMod

        RollOutcome = self.StateService.EvaluateRoll(
            Modifier         = TotalModifier,
            NetBoons         = NetBoons,
            TargetDifficulty = TargetDiff
        )

        EmbedColor   = COLOR_SUCCESS_EMBED if RollOutcome.IsSuccess else COLOR_FAILURE_EMBED
        TitleText    = f"{CharName}: {SkillQueryName.title()} ({SelectedStatName[:3].upper()})"
        ResponseEmbed = Discord.Embed(title = TitleText, color = EmbedColor)

        SkillTagText: str = f"Skill: {'+' if SkillModifier >= 0 else ''}{SkillModifier}"
        StatTagText : str = f"{SelectedStatName[:3].upper()} DM: {'+' if StatDMValue >= 0 else ''}{StatDMValue}"
        SitTagText  : str = f", Mod: {SituationalMod:+d}" if (SituationalMod != 0) else ""
        BreakdownText = f"{RollOutcome.BreakdownString}\n*({SkillTagText}, {StatTagText}{SitTagText})*"

        ResponseEmbed.add_field(name = "Result", value = BreakdownText, inline = False)
        ResponseEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
        ResponseEmbed.set_footer(text = "MIS-Bot • MGT2E Check Engine")
        await Context.send(embed = ResponseEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[TravellerStateService.TravellerStateService] = getattr(BotInstance, "TravellerStateService", None)
    await BotInstance.add_cog(TravellerCheckCommands(BotInstance, StateService = StateServiceInstance))
