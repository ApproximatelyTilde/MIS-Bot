import typing                                 as Typing
import discord                                as Discord
import discord.ui                             as UserInterface
import Runtime.Services.DiceService           as Dice
import Runtime.Services.CharacterStateService as CharacterState
import Runtime.Services.TargetResolverService as TargetResolver

COLOR_STANDARD_ROLL: int = 0x0030A6
COLOR_CRITICAL_HIT : int = 0x005E00
COLOR_CRITICAL_MISS: int = 0xA60000

class DND5ERollView(UserInterface.View):
    def __init__(self, StateService: CharacterState.CharacterStateService, CharacterRecord: dict[str, Typing.Any], DiceRoller: Typing.Optional[Dice.DiceRollerService] = None, InitialMode: str = "Check", SelectedQuery: Typing.Optional[str] = None, TargetDC: Typing.Optional[int] = None, AdvantageState: int = 0, SituationalBonus: int = 0, InvokerDiscordID: Typing.Optional[int] = None, TargetResolverInstance: Typing.Optional[TargetResolver.TargetResolverService] = None, CompletionCallback: Typing.Optional[Typing.Any] = None) -> None:
        super().__init__(timeout = 180.0)
        self.StateService      : CharacterState.CharacterStateService           = StateService
        self.CharacterRecord   : dict[str, Typing.Any]                          = CharacterRecord
        self.DiceRoller        : Dice.DiceRollerService                         = DiceRoller if (DiceRoller is not None) else Dice.DiceRollerService()
        self.RollMode          : str                                            = "Save" if (InitialMode.lower() == "save") else "Check"
        self.SelectedQuery     : str                                            = SelectedQuery if (SelectedQuery is not None) else ("dex" if (self.RollMode == "Save") else "perception")
        self.TargetDC          : Typing.Optional[int]                           = TargetDC
        self.AdvantageState    : int                                            = AdvantageState
        self.SituationalBonus  : int                                            = SituationalBonus
        self.InvokerDiscordID  : Typing.Optional[int]                           = InvokerDiscordID
        self.TargetResolver    : Typing.Optional[TargetResolver.TargetResolverService] = TargetResolverInstance
        self.CompletionCallback: Typing.Optional[Typing.Any]                    = CompletionCallback

        self.ModeButton    : UserInterface.Button = UserInterface.Button(label = f"Mode: {self.RollMode}", style = Discord.ButtonStyle.secondary, row = 0)
        self.ModeButton.callback                  = self.OnModeToggled
        self.add_item(self.ModeButton)

        self.AdvButton     : UserInterface.Button = UserInterface.Button(label = self.GetAdvantageLabel(), style = self.GetAdvantageStyle(), row = 0)
        self.AdvButton.callback                   = self.OnAdvantageClicked
        self.add_item(self.AdvButton)

        self.FinalizeButton: UserInterface.Button = UserInterface.Button(label = "Roll d20", style = Discord.ButtonStyle.primary, emoji = "🎲", row = 0)
        self.FinalizeButton.callback              = self.OnFinalizeClicked
        self.add_item(self.FinalizeButton)

        self.BuildTargetSelect()

    def GetAdvantageLabel(self) -> str:
        if (self.AdvantageState > 0):
            return "✨ Advantage"

        if (self.AdvantageState < 0):
            return "⚡ Disadvantage"

        return "Normal Roll"

    def GetAdvantageStyle(self) -> Discord.ButtonStyle:
        if (self.AdvantageState > 0):
            return Discord.ButtonStyle.success

        if (self.AdvantageState < 0):
            return Discord.ButtonStyle.danger

        return Discord.ButtonStyle.secondary

    def BuildTargetSelect(self) -> None:
        DetailData: dict                       = self.CharacterRecord.get("DetailData", {})
        Options   : list[Discord.SelectOption] = []

        if (self.RollMode == "Save"):
            for AbilityKey in ("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"):
                AbilityTitle, SaveMod, IsProf = self.StateService.GetSavingThrowModifier(DetailData, AbilityKey)
                ModStr: str = f"{"+" if (SaveMod >= 0) else ""}{SaveMod}"
                ProfBadge: str                = " ★" if IsProf else ""
                IsDef    : bool               = (AbilityKey.lower().startswith(self.SelectedQuery.lower()) or self.SelectedQuery.lower() == AbilityKey[:3].lower())
                Options.append(Discord.SelectOption(label = f"{AbilityTitle} Save ({ModStr}){ProfBadge}", value = AbilityKey.lower(), default = IsDef))

        else:
            for AbilityKey in ("Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"):
                AbilityTitle, _, AbilityMod = self.StateService.GetAbilityModifier(DetailData, AbilityKey)
                ModStr                      = f"{"+" if (AbilityMod >= 0) else ""}{AbilityMod}"
                IsDef                       = (AbilityKey.lower() == self.SelectedQuery.lower() or AbilityKey[:3].lower() == self.SelectedQuery.lower())
                Options.append(Discord.SelectOption(label = f"{AbilityTitle} Check ({ModStr})", value = AbilityKey.lower(), default = IsDef))

            for SkillKey in sorted(CharacterState.SKILL_ABILITY_MAPPING.keys()):
                SkillTitle, _, SkillMod, _ = self.StateService.GetSkillModifier(DetailData, SkillKey)
                ModStr                     = f"{"+" if (SkillMod >= 0) else ""}{SkillMod}"
                IsDef                      = (SkillKey.lower() == self.SelectedQuery.lower())
                Options.append(Discord.SelectOption(label = f"{SkillTitle} ({ModStr})", value = SkillKey, default = IsDef))

        if not any(Opt.default for Opt in Options) and Options:
            Options[0].default = True
            self.SelectedQuery = Options[0].value

        self.TargetMenu: UserInterface.Select = UserInterface.Select(placeholder = "Select Ability or Skill", options = Options[:25], row = 1)
        self.TargetMenu.callback              = self.OnTargetSelected
        self.add_item(self.TargetMenu)

    async def CheckAuthorization(self, Interaction: Discord.Interaction) -> bool:
        if (self.InvokerDiscordID is not None) and (Interaction.user.id != self.InvokerDiscordID):
            await Interaction.response.send_message("Only the player who opened this interactive roll may modify or execute it.", ephemeral = True)
            return False

        if (self.TargetResolver is not None) and (Interaction.channel is not None):
            IsValid, _, GuardMessage = await self.TargetResolver.ValidateSystemGuard(Interaction.user.id, Interaction.channel.id, "DND5E")
            if not IsValid:
                await Interaction.response.send_message(GuardMessage or "Switch to a Dungeons & Dragons character before using this control.", ephemeral = True)
                return False

        return True

    async def OnModeToggled(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        self.RollMode         = "Check" if (self.RollMode == "Save") else "Save"
        self.ModeButton.label = f"Mode: {self.RollMode}"
        self.remove_item(self.TargetMenu)
        self.BuildTargetSelect()
        await Interaction.response.edit_message(view = self)

    async def OnAdvantageClicked(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        if (self.AdvantageState == 0):
            self.AdvantageState = 1

        elif (self.AdvantageState > 0):
            self.AdvantageState = -1

        else:
            self.AdvantageState = 0

        self.AdvButton.label = self.GetAdvantageLabel()
        self.AdvButton.style = self.GetAdvantageStyle()
        await Interaction.response.edit_message(view = self)

    async def OnTargetSelected(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        if self.TargetMenu.values:
            self.SelectedQuery = str(self.TargetMenu.values[0])

        for Opt in self.TargetMenu.options:
            Opt.default = (Opt.value == self.SelectedQuery)

        await Interaction.response.edit_message(view = self)

    async def OnFinalizeClicked(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        DetailData   : dict = self.CharacterRecord.get("DetailData", {})
        CharacterName: str  = str(self.CharacterRecord.get("Name", "Hero"))

        if (self.RollMode == "Save"):
            AbilityTitle, BaseModifier, _ = self.StateService.GetSavingThrowModifier(DetailData, self.SelectedQuery)
            CheckLabel: str               = f"{AbilityTitle} Saving Throw"

        elif (self.SelectedQuery.lower() in CharacterState.ABILITY_ALIASES):
            AbilityTitle, _, BaseModifier = self.StateService.GetAbilityModifier(DetailData, self.SelectedQuery)
            if self.StateService.HasJackOfAllTrades(DetailData):
                BaseModifier += int(DetailData.get("ProficiencyBonus", 2)) // 2

            CheckLabel = f"{AbilityTitle} Check"

        else:
            SkillTitle, _, BaseModifier, _ = self.StateService.GetSkillModifier(DetailData, self.SelectedQuery)
            CheckLabel = f"{SkillTitle} Check"

        TotalMod: int              = BaseModifier + self.SituationalBonus
        DicePart: str              = "2d20kh1" if (self.AdvantageState > 0) else ("2d20kl1" if (self.AdvantageState < 0) else "1d20")
        Formula : str              = f"{DicePart}{"+" if (TotalMod >= 0) else ""}{TotalMod}"
        Outcome : Dice.RollOutcome = self.DiceRoller.EvaluateRoll(Formula)

        EmbedColor  : int = COLOR_STANDARD_ROLL
        OutcomeBadge: str = ""
        if Outcome.IsCriticalHit:
            EmbedColor = COLOR_CRITICAL_HIT

        elif Outcome.IsCriticalMiss:
            EmbedColor = COLOR_CRITICAL_MISS

        if (self.TargetDC is not None):
            Margin      : int  = Outcome.Total - self.TargetDC
            IsSuccess   : bool = ((Outcome.Total >= self.TargetDC) or Outcome.IsCriticalHit) and (not Outcome.IsCriticalMiss)
            EmbedColor         = COLOR_CRITICAL_HIT if IsSuccess else COLOR_CRITICAL_MISS
            StatusTag   : str  = "✅ **Success!**" if IsSuccess else "❌ **Failure!**"
            OutcomeBadge       = f"{StatusTag} (vs DC {self.TargetDC}, {"+" if (Margin >= 0) else ""}{Margin})"

        for ChildItem in self.children:
            if hasattr(ChildItem, "disabled"):
                ChildItem.disabled = True

        ResultEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {CheckLabel}", description = f"{Outcome.Breakdown}\n\n# **{Outcome.Total}**", color = EmbedColor)
        if OutcomeBadge:
            ResultEmbed.add_field(name = "DC Comparison", value = OutcomeBadge, inline = False)

        ResultEmbed.set_footer(text = "Tally │ Dungeons & Dragons Interactive Roll")
        await Interaction.response.edit_message(embed = ResultEmbed, view = self)
        if (self.CompletionCallback is not None):
            await self.CompletionCallback(Interaction, Outcome, CheckLabel)
