import re                                             as RegularExpressions
import typing                                         as Typing
import discord                                        as Discord
import discord.ext.commands                           as Commands
import Runtime.Configuration.Config                   as Config
import Runtime.Services.MGT2EStateService             as MGT2EState
import Runtime.Services.EncounterManagerService       as EncounterManager
import Runtime.Services.TargetResolverService         as TargetResolver
import Runtime.Services.Draconic.API.ArgumentParser   as ArgumentParser
import Runtime.Application.Components.MGT2ERollView   as MGT2ERollView
import Runtime.Application.Components.RollRequestView as RollRequestView
import Runtime.Decorators.AuthorizationDecorators     as AuthorizationDecorators

COLOR_SUCCESS_EMBED: int = 0x005E00
COLOR_FAILURE_EMBED: int = 0xA60000
COLOR_ERROR_EMBED  : int = 0xA60000
COLOR_MGT2E_EMBED  : int = 0x005E5E

DIFF_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-diff|--difficulty)\s+(\d+)", RegularExpressions.IGNORECASE)
BOON_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-boon|--boon|\bboon\b|-adv|\badv\b)", RegularExpressions.IGNORECASE)
BANE_PATTERN    : RegularExpressions.Pattern = RegularExpressions.compile(r"(?:^|\s)(?:-bane|--bane|\bbane\b|-dis|\bdis\b)", RegularExpressions.IGNORECASE)
MODIFIER_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"([+-]\s*\d+)")

class MGT2ECheckCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, StateService: Typing.Optional[MGT2EState.MGT2EStateService] = None, EncounterManagerInstance: Typing.Optional[EncounterManager.EncounterManagerService] = None, TargetResolverInstance: Typing.Optional[TargetResolver.TargetResolverService] = None) -> None:
        self.BotInstance     : Commands.Bot                                  = BotInstance
        self.StateService    : MGT2EState.MGT2EStateService                  = StateService if (StateService is not None) else (getattr(BotInstance, "MGT2EStateService", None) or MGT2EState.MGT2EStateService())
        self.EncounterManager: EncounterManager.EncounterManagerService = EncounterManagerInstance if (EncounterManagerInstance is not None) else (getattr(BotInstance, "EncounterManager", None) or EncounterManager.EncounterManagerService(PlatformClientInstance = self.StateService.PlatformClient))
        self.TargetResolver  : TargetResolver.TargetResolverService          = TargetResolverInstance if (TargetResolverInstance is not None) else (getattr(BotInstance, "TargetResolverService", None) or TargetResolver.TargetResolverService(MGT2EStateInstance = self.StateService))

    @Commands.command(name = "c", aliases = ["check"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def CheckCommand(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        ActiveRecord: Typing.Optional[dict[str, Typing.Any]] = await self.StateService.ResolveActiveCharacter(Context.author.id, Context.channel.id)
        if (ActiveRecord is None):
            NoCharacterEmbed: Discord.Embed = Discord.Embed(title = "No Active Character", description = f"You do not have an active Mongoose Traveller character selected.\n\nSelect one with `{Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E}character select <Name>`.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = NoCharacterEmbed)
            return

        WorkingText: str        = ArgumentsText.strip()
        TargetDiff : int        = MGT2EState.DEFAULT_DIFFICULTY_AVERAGE
        DiffMatch  : Typing.Any = DIFF_PATTERN.search(WorkingText)
        if (DiffMatch is not None):
            TargetDiff  = int(DiffMatch.group(1))
            WorkingText = DIFF_PATTERN.sub("", WorkingText).strip()

        if not WorkingText:
            RollView   : MGT2ERollView.MGT2ERollView = MGT2ERollView.MGT2ERollView(StateService = self.StateService, CharacterRecord = ActiveRecord, TargetDifficulty = TargetDiff, InvokerDiscordID = Context.author.id, TargetResolverInstance = self.TargetResolver)
            PromptEmbed: Discord.Embed               = Discord.Embed(title = f"{ActiveRecord.get("Name", "Traveller")}: Interactive Check", description = f"Select Characteristic & Skill, toggle Boon/Bane, and click **Roll 2d6** (Difficulty {TargetDiff}).", color = COLOR_MGT2E_EMBED)
            await Context.send(embed = PromptEmbed, view = RollView)
            return

        NetBoons: int = 0
        if BOON_PATTERN.search(WorkingText):
            NetBoons   += 1
            WorkingText = BOON_PATTERN.sub("", WorkingText).strip()

        if BANE_PATTERN.search(WorkingText):
            NetBoons   -= 1
            WorkingText = BANE_PATTERN.sub("", WorkingText).strip()

        SituationalModifier: int = 0
        for ModifierMatch in MODIFIER_PATTERN.finditer(WorkingText):
            ModifierString: str = ModifierMatch.group(1).replace(" ", "")
            if ModifierString.lstrip("+-").isdigit():
                SituationalModifier += int(ModifierString)

        WorkingText = MODIFIER_PATTERN.sub("", WorkingText).strip()

        DetailData     : dict = ActiveRecord.get("DetailData", {})
        Characteristics: dict = DetailData.get("Characteristics", {})
        Skills         : dict = DetailData.get("Skills", {})
        CharacterName  : str  = str(ActiveRecord.get("Name", "Traveller"))

        Tokens: list[str] = WorkingText.split()
        if not Tokens:
            RollView    = MGT2ERollView.MGT2ERollView(StateService = self.StateService, CharacterRecord = ActiveRecord, TargetDifficulty = TargetDiff, InvokerDiscordID = Context.author.id, TargetResolverInstance = self.TargetResolver, SituationalModifier = SituationalModifier)
            PromptEmbed = Discord.Embed(title = f"{CharacterName}: Interactive Check", description = f"Select Characteristic & Skill, toggle Boon/Bane, and click **Roll 2d6** (Difficulty {TargetDiff}).", color = COLOR_MGT2E_EMBED)
            await Context.send(embed = PromptEmbed, view = RollView)
            return

        FirstTokenLower: str = Tokens[0].lower()
        if FirstTokenLower in MGT2EState.CHARACTERISTIC_LOOKUP:
            StatFullName : str = MGT2EState.CHARACTERISTIC_LOOKUP[FirstTokenLower]
            StatScore    : int = int(Characteristics.get(StatFullName, 7))
            StatDM       : int = self.StateService.CalculateCharacteristicModifier(StatScore)
            TotalModifier: int = StatDM + SituationalModifier

            RollOutcome  : MGT2EState.MGT2ERollOutcome = self.StateService.EvaluateRoll(Modifier = TotalModifier, NetBoons = NetBoons, TargetDifficulty = TargetDiff)
            EmbedColor   : int                         = COLOR_SUCCESS_EMBED if (RollOutcome.IsSuccess) else COLOR_FAILURE_EMBED
            StatDisplay  : str                         = f"{StatFullName} Check"
            ResponseEmbed: Discord.Embed               = Discord.Embed(title = f"{CharacterName}: {StatDisplay}", color = EmbedColor)
            BreakdownText: str                         = f"{RollOutcome.BreakdownString}\n*(Stat DM: {"+" if (StatDM >= 0) else ""}{StatDM}{f", Modifier: {SituationalModifier:+d}" if (SituationalModifier != 0) else ""})*"
            ResponseEmbed.add_field(name = "Result", value = BreakdownText, inline = False)
            ResponseEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
            ResponseEmbed.set_footer(text = "Tally │ Mongoose Traveller Check Engine")
            await Context.send(embed = ResponseEmbed)
            return

        SecondTokenIsStat: bool                 = (len(Tokens) > 1) and (Tokens[-1].lower() in MGT2EState.CHARACTERISTIC_LOOKUP)
        SelectedStatName : Typing.Optional[str] = None
        SkillTokens      : list[str]            = Tokens[:]

        if SecondTokenIsStat:
            SelectedStatName = MGT2EState.CHARACTERISTIC_LOOKUP[Tokens[-1].lower()]
            SkillTokens      = Tokens[:-1]

        SkillQueryName: str = " ".join(SkillTokens).strip()
        if not SelectedStatName:
            SelectedStatName = self.StateService.GetDefaultCharacteristicForSkill(SkillQueryName)

        SkillModifier : int = self.StateService.GetSkillModifier(Skills, SkillQueryName)
        StatScoreValue: int = int(Characteristics.get(SelectedStatName, 7))
        StatDMValue   : int = self.StateService.CalculateCharacteristicModifier(StatScoreValue)
        TotalModifier       = SkillModifier + StatDMValue + SituationalModifier

        RollOutcome        = self.StateService.EvaluateRoll(Modifier = TotalModifier, NetBoons = NetBoons, TargetDifficulty = TargetDiff)
        EmbedColor         = COLOR_SUCCESS_EMBED if (RollOutcome.IsSuccess) else COLOR_FAILURE_EMBED
        TitleText    : str = f"{CharacterName}: {SkillQueryName.title()} ({SelectedStatName[:3].upper()})"
        ResponseEmbed      = Discord.Embed(title = TitleText, color = EmbedColor)

        SkillTagText : str = f"Skill: {"+" if (SkillModifier >= 0) else ""}{SkillModifier}"
        StatTagText  : str = f"{SelectedStatName[:3].upper()} DM: {"+" if (StatDMValue >= 0) else ""}{StatDMValue}"
        SitTagText   : str = f", Modifier: {SituationalModifier:+d}" if (SituationalModifier != 0) else ""
        BreakdownText      = f"{RollOutcome.BreakdownString}\n*({SkillTagText}, {StatTagText}{SitTagText})*"

        ResponseEmbed.add_field(name = "Result", value = BreakdownText, inline = False)
        ResponseEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
        ResponseEmbed.set_footer(text = "Tally │ Mongoose Traveller Check Engine")
        await Context.send(embed = ResponseEmbed)

    @Commands.command(name = "request", aliases = ["req"])
    @Commands.check(AuthorizationDecorators.CheckMGT2EPrefix)
    async def RequestRollCommand(self, Context: Commands.Context, *, ArgumentsText: str = "") -> None:
        ParsedArguments: ArgumentParser.ParsedArguments = ArgumentParser.ParsedArguments(ArgumentsText)
        PositionalList : list[str]                      = list(ParsedArguments.PositionalArguments)
        if not PositionalList:
            await Context.send(f"Usage: `{Context.prefix}req <skill|stat> [stat] [-diff N] [-boon|-bane] [-b N] [-t <target>]`")
            return

        CharacteristicOverride: Typing.Optional[str] = None
        SkillTokens           : list[str]            = list(PositionalList)
        if (len(SkillTokens) > 1) and (SkillTokens[-1].lower() in MGT2EState.CHARACTERISTIC_LOOKUP):
            CharacteristicOverride = MGT2EState.CHARACTERISTIC_LOOKUP[SkillTokens[-1].lower()]
            SkillTokens            = SkillTokens[:-1]

        CheckQuery: str                  = " ".join(SkillTokens).strip()
        TargetDiff: int                  = MGT2EState.DEFAULT_DIFFICULTY_AVERAGE
        DiffArg   : Typing.Optional[str] = ParsedArguments.last("diff") or ParsedArguments.last("difficulty")
        if (DiffArg is not None) and DiffArg.strip().isdigit():
            TargetDiff = int(DiffArg.strip())

        NetBoons: int = 0
        if ("boon" in ParsedArguments.OptionsDictionary) or ("adv" in ParsedArguments.OptionsDictionary):
            NetBoons += 1

        if ("bane" in ParsedArguments.OptionsDictionary) or ("dis" in ParsedArguments.OptionsDictionary):
            NetBoons -= 1

        BonusMod: int                  = 0
        BonusArg: Typing.Optional[str] = ParsedArguments.last("b")
        if (BonusArg is not None):
            try:
                BonusMod = int(BonusArg.strip())

            except ValueError:
                BonusMod = 0

        TargetTokens: list[str]                                         = ParsedArguments.get("t") or []
        Encounter   : Typing.Optional[EncounterManager.CombatEncounter] = await self.EncounterManager.GetOrLoadEncounterAsync(Context.channel.id)
        TargetSlots : list[RollRequestView.RollRequestSlot]             = []

        if TargetTokens:
            ResolvedList: list[TargetResolver.ResolvedTarget] = await self.TargetResolver.ResolveTargets(TargetTokens, GameSystem = "MGT2E", ChannelID = Context.channel.id, Encounter = Encounter)
            for ResolvedTarget in ResolvedList:
                if ResolvedTarget.SystemMismatch and (ResolvedTarget.MentionedUserID is not None):
                    await Context.send(ResolvedTarget.ErrorMessage or "Target user does not have an active Mongoose Traveller character.")
                    return

                SlotIDValue : str  = str(ResolvedTarget.Combatant.ID if (ResolvedTarget.Combatant is not None) else (ResolvedTarget.MentionedUserID or ResolvedTarget.DisplayName))
                IsStrictUser: bool = (ResolvedTarget.MentionedUserID is not None) and ResolvedTarget.IsSynthetic
                TargetSlots.append(RollRequestView.RollRequestSlot(SlotID = SlotIDValue, DisplayName = ResolvedTarget.DisplayName, AllowedUserID = ResolvedTarget.ControllerDiscordID, StrictUserOnly = IsStrictUser, Combatant = ResolvedTarget.Combatant, CharacterRecord = ResolvedTarget.CharacterRecord))

        RequestViewInstance: RollRequestView.RollRequestView = RollRequestView.RollRequestView(GameSystem = "MGT2E", RollType = "check", CheckQuery = CheckQuery, RequesterName = Context.author.display_name, TargetResolverInstance = self.TargetResolver, CharacteristicOverride = CharacteristicOverride, TargetDifficultyOrDC = TargetDiff, AdvantageOrBoons = NetBoons, SituationalModifier = BonusMod, TargetSlots = TargetSlots)
        SentMessage        : Discord.Message                 = await Context.send(embed = RequestViewInstance.BuildRequestEmbed(), view = RequestViewInstance)
        RequestViewInstance.RequestMessage                   = SentMessage

async def setup(BotInstance: Commands.Bot) -> None:
    StateServiceInstance: Typing.Optional[MGT2EState.MGT2EStateService] = getattr(BotInstance, "MGT2EStateService", None)
    await BotInstance.add_cog(MGT2ECheckCommands(BotInstance, StateService = StateServiceInstance))
