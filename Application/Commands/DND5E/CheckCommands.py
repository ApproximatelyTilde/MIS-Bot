import re                             as RegularExpressions
import typing                         as Typing
import discord                        as Discord
import discord.ext.commands           as Commands
import Configuration.Config           as Config
import Services.DebugService          as Debug
import Services.DiceService           as Dice
import Services.CharacterStateService as CharacterState

COLOR_CRITICAL_HIT : int = 0x005E00
COLOR_CRITICAL_MISS: int = 0xA60000
COLOR_STANDARD_ROLL: int = 0x0030A6
COLOR_ERROR_EMBED  : int = 0xA60000

DC_PATTERN      : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-dc|--dc)\s+(\d+)", RegularExpressions.IGNORECASE)
BOON_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-adv|--adv|\badv\b|-advantage|\badvantage\b)", RegularExpressions.IGNORECASE)
BANE_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-dis|--dis|\bdis\b|-disadvantage|\bdisadvantage\b)", RegularExpressions.IGNORECASE)
MODIFIER_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"([+-]\s*\d+)")

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E5E)

class CheckCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[CharacterState.CharacterStateService] = None) -> None:
        self.BotInstance : Commands.Bot                        = BotInstance
        self.StateService: CharacterState.CharacterStateService = StateService if (StateService is not None) else CharacterState.CharacterStateService()
        self.DiceRoller  : Dice.DiceRollerService               = Dice.DiceRollerService()

    @Commands.command(name = "check", aliases = ["c"])
    @Commands.check(CheckDND5EPrefix)
    async def CheckCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        WorkingText: str                   = ArgumentsText.strip()
        TargetDC   : Typing.Optional[int]  = None
        DCMatch                            = DC_PATTERN.search(WorkingText)
        if (DCMatch is not None):
            TargetDC    = int(DCMatch.group(1))
            WorkingText = DC_PATTERN.sub("", WorkingText).strip()

        Tokens: list[str] = WorkingText.split()
        if not Tokens:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}c <skill|ability> [flags]`")
            return

        FirstToken   : str  = Tokens[0].lower()
        TrailingFlags: str  = " ".join(Tokens[1:])
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName     : str  = str(ActiveRecord.get("Name", "Hero"))

        if FirstToken in CharacterState.ABILITY_ALIASES:
            AbilityName, _, AbilityModifier = self.StateService.GetAbilityModifier(DetailData, FirstToken)
            JackNote: str              = ""
            if self.StateService.HasJackOfAllTrades(DetailData):
                ProfBonus : int = int(DetailData.get("ProficiencyBonus", 2))
                JackBonus : int = ProfBonus // 2
                AbilityModifier     += JackBonus
                JackNote        = " (Jack of All Trades)"

            RollFormula: str                     = f"1d20{"+" if (AbilityModifier >= 0) else ""}{AbilityModifier} {TrailingFlags}".strip()
            Outcome    : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(RollFormula)

            EmbedColor  : int = COLOR_STANDARD_ROLL
            CritText    : str = ""
            OutcomeBadge: str = ""

            if Outcome.IsCriticalHit:
                EmbedColor = COLOR_CRITICAL_HIT
                CritText   = "\n\n🎯 **Critical Hit!**"

            elif Outcome.IsCriticalMiss:
                EmbedColor = COLOR_CRITICAL_MISS
                CritText   = "\n\n💥 **Critical Miss!**"

            if (TargetDC is not None):
                Margin   : int  = Outcome.Total - TargetDC
                IsSuccess: bool = (Outcome.Total >= TargetDC) or Outcome.IsCriticalHit
                if Outcome.IsCriticalMiss:
                    IsSuccess = False

                if IsSuccess:
                    EmbedColor   = COLOR_CRITICAL_HIT
                    OutcomeBadge = f"✅ **Success!** (vs DC {TargetDC}, {"+" if (Margin >= 0) else ""}{Margin})"

                else:
                    EmbedColor   = COLOR_CRITICAL_MISS
                    OutcomeBadge = f"❌ **Failure!** (vs DC {TargetDC}, {Margin})"

            ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {AbilityName} Check{JackNote}", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**{CritText}", color = EmbedColor)
            if OutcomeBadge:
                ResponseEmbed.add_field(name = "DC Comparison", value = OutcomeBadge, inline = False)

            ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
            ResponseEmbed.set_footer(text = "MIS-Bot • Dungeons & Dragons Check")
            await Context.send(embed = ResponseEmbed)
            return

        SkillTitle, AssocAbil, SkillModifier, TierName = self.StateService.GetSkillModifier(DetailData, FirstToken)
        RollFormula = f"1d20{"+" if (SkillModifier >= 0) else ""}{SkillModifier} {TrailingFlags}".strip()
        Outcome     = self.DiceRoller.EvaluateRoll(RollFormula)

        EmbedColor   = COLOR_STANDARD_ROLL
        CritText     = ""
        OutcomeBadge = ""

        if Outcome.IsCriticalHit:
            EmbedColor = COLOR_CRITICAL_HIT
            CritText   = "\n\n🎯 **Critical Hit!**"

        elif Outcome.IsCriticalMiss:
            EmbedColor = COLOR_CRITICAL_MISS
            CritText   = "\n\n💥 **Critical Miss!**"

        if (TargetDC is not None):
            Margin    = Outcome.Total - TargetDC
            IsSuccess = (Outcome.Total >= TargetDC) or Outcome.IsCriticalHit
            if Outcome.IsCriticalMiss:
                IsSuccess = False

            if IsSuccess:
                EmbedColor   = COLOR_CRITICAL_HIT
                OutcomeBadge = f"✅ **Success!** (vs DC {TargetDC}, {"+" if (Margin >= 0) else ""}{Margin})"

            else:
                EmbedColor   = COLOR_CRITICAL_MISS
                OutcomeBadge = f"❌ **Failure!** (vs DC {TargetDC}, {Margin})"

        TierNote     : str           = f" ({TierName})" if (TierName != "None") else ""
        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {SkillTitle} Check{TierNote}", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**{CritText}", color = EmbedColor)
        if OutcomeBadge:
            ResponseEmbed.add_field(name = "DC Comparison", value = OutcomeBadge, inline = False)

        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = f"MIS-Bot • Dungeons & Dragons Skill Check ({AssocAbil})")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "save", aliases = ["s"])
    @Commands.check(CheckDND5EPrefix)
    async def SaveCommand(self, Context: Commands.Context, *, ArgumentsText: str) -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        WorkingText: str                   = ArgumentsText.strip()
        TargetDC   : Typing.Optional[int]  = None
        DCMatch                            = DC_PATTERN.search(WorkingText)
        if (DCMatch is not None):
            TargetDC    = int(DCMatch.group(1))
            WorkingText = DC_PATTERN.sub("", WorkingText).strip()

        Tokens: list[str] = WorkingText.split()
        if not Tokens:
            await Context.send(f"Usage: `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}s <ability> [flags]`")
            return

        AbilityQuery : str  = Tokens[0].lower()
        TrailingFlags: str  = " ".join(Tokens[1:])
        DetailData   : dict = ActiveRecord.get("DetailData", {})
        CharacterName     : str  = str(ActiveRecord.get("Name", "Hero"))

        AbilityName, SaveModifier, IsProf = self.StateService.GetSavingThrowModifier(DetailData, AbilityQuery)
        RollFormula  : str           = f"1d20{"+" if (SaveModifier >= 0) else ""}{SaveModifier} {TrailingFlags}".strip()
        Outcome      : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(RollFormula)

        EmbedColor  : int = COLOR_STANDARD_ROLL
        CritText    : str = ""
        OutcomeBadge: str = ""

        if Outcome.IsCriticalHit:
            EmbedColor = COLOR_CRITICAL_HIT
            CritText   = "\n\n🎯 **Critical Hit!**"

        elif Outcome.IsCriticalMiss:
            EmbedColor = COLOR_CRITICAL_MISS
            CritText   = "\n\n💥 **Critical Miss!**"

        if (TargetDC is not None):
            Margin   : int  = Outcome.Total - TargetDC
            IsSuccess: bool = (Outcome.Total >= TargetDC) or Outcome.IsCriticalHit
            if Outcome.IsCriticalMiss:
                IsSuccess = False

            if IsSuccess:
                EmbedColor   = COLOR_CRITICAL_HIT
                OutcomeBadge = f"✅ **Success!** (vs DC {TargetDC}, {"+" if (Margin >= 0) else ""}{Margin})"

            else:
                EmbedColor   = COLOR_CRITICAL_MISS
                OutcomeBadge = f"❌ **Failure!** (vs DC {TargetDC}, {Margin})"

        ProfNote     : str           = " *(Proficient)*" if (IsProf) else ""
        ResponseEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {AbilityName} Saving Throw{ProfNote}", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**{CritText}", color = EmbedColor)
        if OutcomeBadge:
            ResponseEmbed.add_field(name = "DC Comparison", value = OutcomeBadge, inline = False)

        ResponseEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        ResponseEmbed.set_footer(text = "MIS-Bot • Dungeons & Dragons Saving Throw")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "passive", aliases = ["pass", "pp"])
    @Commands.check(CheckDND5EPrefix)
    async def PassiveCommand(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        ActiveRecord: Typing.Optional[dict] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active character selected.\n\nSelect a character with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        DetailData: dict[str, Typing.Any] = ActiveRecord.get("DetailData", {})
        CharacterName  : str                   = str(ActiveRecord.get("Name", "Hero"))
        CleanText : str                   = ArgumentsText.strip()

        if not CleanText:
            AllPassives     : dict[str, int] = self.StateService.GetAllPassiveScores(DetailData)
            PercScore       : int            = AllPassives.get("Perception", 10)
            InvestigationScore        : int            = AllPassives.get("Investigation", 10)
            InsScore        : int            = AllPassives.get("Insight", 10)
            OverviewEmbed   : Discord.Embed  = Discord.Embed(title = f"{CharacterName}: Passive Scores", description = "Core passive awareness scores and all skill checks.", color = COLOR_STANDARD_ROLL)
            CorePassivesText: str            = f"👁️ **Passive Perception**: **{PercScore}**\n🔍 **Passive Investigation**: **{InvestigationScore}**\n💡 **Passive Insight**: **{InsScore}**"
            OverviewEmbed.add_field(name = "Core Passives", value = CorePassivesText, inline = False)

            SkillLines: list[str] = []
            for SkillTitle, ScoreValue in sorted(AllPassives.items()):
                SkillLines.append(f"• **{SkillTitle}**: {ScoreValue}")

            HalfLength : int       = len(SkillLines) // 2
            LeftColumn : list[str] = SkillLines[:HalfLength]
            RightColumn: list[str] = SkillLines[HalfLength:]
            OverviewEmbed.add_field(name = "Skills", value = "\n".join(LeftColumn), inline = True)
            OverviewEmbed.add_field(name = "Skills (Cont.)", value = "\n".join(RightColumn), inline = True)

            AbilityLines: list[str] = []
            for AbilityKey in ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]:
                _, _, ModifierValue = self.StateService.GetAbilityModifier(DetailData, AbilityKey)
                JackBonus: int = (int(DetailData.get("ProficiencyBonus", 2)) // 2) if (self.StateService.HasJackOfAllTrades(DetailData)) else 0
                ScoreVal : int = 10 + ModifierValue + JackBonus
                AbilityLines.append(f"• **{AbilityKey[:3].upper()}**: {ScoreVal}")

            OverviewEmbed.add_field(name = "Abilities", value = "\n".join(AbilityLines), inline = False)
            OverviewEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
            OverviewEmbed.set_footer(text = "MIS-Bot • Dungeons & Dragons Passive Engine")
            await Context.send(embed = OverviewEmbed)
            return

        AdvantageState: int = 0
        if BOON_PATTERN.search(CleanText):
            AdvantageState += 1
            CleanText       = BOON_PATTERN.sub("", CleanText).strip()

        if BANE_PATTERN.search(CleanText):
            AdvantageState -= 1
            CleanText       = BANE_PATTERN.sub("", CleanText).strip()

        SituationalBonus: int = 0
        for ModifierMatch in MODIFIER_PATTERN.finditer(CleanText):
            ModifierString: str = ModifierMatch.group(1).replace(" ", "")
            if ModifierString.lstrip("+-").isdigit():
                SituationalBonus += int(ModifierString)

        CleanText = MODIFIER_PATTERN.sub("", CleanText).strip()
        ResolvedTitle, PassiveTotal, BreakdownText = self.StateService.CalculatePassiveScore(DetailData = DetailData, QueryName = CleanText, AdvantageState = AdvantageState, SituationalBonus = SituationalBonus)

        SingleEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: Passive {ResolvedTitle}", description = f"{BreakdownText}\n\n# **{PassiveTotal}**", color = COLOR_STANDARD_ROLL)
        SingleEmbed.set_author(name = Context.author.display_name, icon_url = Context.author.display_avatar.url)
        SingleEmbed.set_footer(text = "MIS-Bot • Dungeons & Dragons Passive Check")
        await Context.send(embed = SingleEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(CheckCommands(BotInstance))
