import typing                                 as Typing
import discord                                as Discord
import discord.ui                             as UserInterface
import Runtime.Services.MGT2EStateService     as MGT2EState
import Runtime.Services.TargetResolverService as TargetResolver

COLOR_SUCCESS_EMBED: int = 0x005E00
COLOR_FAILURE_EMBED: int = 0xA60000

CORE_MGT2E_SKILLS: list[str] = ["Admin", "Advocate", "Animals", "Art", "Astrogation", "Athletics", "Broker", "Carouse", "Deception", "Diplomat", "Drive", "Electronics", "Engineer", "Explosives", "Flyer", "Gambler", "Gun Combat", "Gunner", "Heavy Weapons", "Investigate", "Leadership", "Mechanic", "Medic", "Melee", "Navigation", "Persuade", "Pilot", "Recon", "Science", "Stealth", "Streetwise", "Survival", "Tactics", "Vacc Suit"]

class MGT2ERollView(UserInterface.View):
    def __init__(self, StateService: MGT2EState.MGT2EStateService, CharacterRecord: dict[str, Typing.Any], SelectedSkill: Typing.Optional[str] = None, SelectedAttribute: Typing.Optional[str] = None, TargetDifficulty: int = MGT2EState.DEFAULT_DIFFICULTY_AVERAGE, InvokerDiscordID: Typing.Optional[int] = None, TargetResolverInstance: Typing.Optional[TargetResolver.TargetResolverService] = None, SituationalModifier: int = 0, CompletionCallback: Typing.Optional[Typing.Callable[[Discord.Interaction, MGT2EState.MGT2ERollOutcome, str], Typing.Awaitable[None]]] = None) -> None:
        super().__init__(timeout = 180.0)
        self.StateService       : MGT2EState.MGT2EStateService                   = StateService
        self.CharacterRecord    : dict[str, Typing.Any]                          = CharacterRecord
        self.SelectedSkill      : Typing.Optional[str]                           = SelectedSkill
        self.TargetDifficulty   : int                                            = TargetDifficulty
        self.InvokerDiscordID   : Typing.Optional[int]                           = InvokerDiscordID
        self.TargetResolver     : Typing.Optional[TargetResolver.TargetResolverService] = TargetResolverInstance
        self.SituationalModifier: int                                            = SituationalModifier
        self.CompletionCallback : Typing.Optional[Typing.Any]                    = CompletionCallback
        self.NetBoons           : int                                            = 0

        if (SelectedAttribute is not None):
            self.SelectedAttribute: str = self.StateService.NormalizeCharacteristicName(SelectedAttribute)

        elif (SelectedSkill is not None):
            self.SelectedAttribute = self.StateService.GetDefaultCharacteristicForSkill(SelectedSkill)

        else:
            self.SelectedAttribute = "Dexterity"

        self.BoonButton     : UserInterface.Button = UserInterface.Button(label = "Boon / Bane", style = Discord.ButtonStyle.secondary, row = 0)
        self.BoonButton.callback                   = self.OnBoonBaneClicked
        self.add_item(self.BoonButton)

        self.FinalizeButton : UserInterface.Button = UserInterface.Button(label = "Roll 2d6", style = Discord.ButtonStyle.primary, emoji = "🎲", row = 0)
        self.FinalizeButton.callback               = self.OnFinalizeClicked
        self.add_item(self.FinalizeButton)

        self.BuildAttributeSelect()
        if (SelectedSkill is None):
            self.BuildSkillSelect()

    def BuildAttributeSelect(self) -> None:
        DetailData     : dict           = self.CharacterRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.get("Characteristics", {})

        SelectOptions: list[Discord.SelectOption] = []
        for ShortName, FullName in [("STR", "Strength"), ("DEX", "Dexterity"), ("END", "Endurance"), ("INT", "Intelligence"), ("EDU", "Education"), ("SOC", "SocialStanding")]:
            ScoreValue   : int  = int(Characteristics.get(FullName, 7))
            ModifierValue: int  = self.StateService.CalculateCharacteristicModifier(ScoreValue)
            IsDefault    : bool = (FullName == self.SelectedAttribute)
            SelectOptions.append(Discord.SelectOption(label = f"{ShortName}: {ScoreValue} (DM: {"+" if (ModifierValue >= 0) else ""}{ModifierValue})", value = FullName, default = IsDefault))

        self.AttrMenu: UserInterface.Select = UserInterface.Select(placeholder = "Select Characteristic", options = SelectOptions, row = 1)
        self.AttrMenu.callback              = self.OnAttributeSelected
        self.add_item(self.AttrMenu)

    def BuildSkillSelect(self) -> None:
        DetailData      : dict           = self.CharacterRecord.get("DetailData", {})
        SkillsDictionary: dict[str, int] = DetailData.get("Skills", {})

        SkillCandidates: list[str] = []
        SeenLower      : set[str]  = set()
        for SkillKey in sorted(SkillsDictionary.keys()):
            if (SkillsDictionary.get(SkillKey, -3) >= 0) and (SkillKey.strip().lower() not in SeenLower):
                SkillCandidates.append(SkillKey)
                SeenLower.add(SkillKey.strip().lower())

        for BaseSkill in CORE_MGT2E_SKILLS:
            if (len(SkillCandidates) >= 24):
                break

            if BaseSkill.lower() not in SeenLower:
                SkillCandidates.append(BaseSkill)
                SeenLower.add(BaseSkill.lower())

        SkillOptions: list[Discord.SelectOption] = [Discord.SelectOption(label = "Pure Characteristic (No Skill)", value = "__NONE__", default = (self.SelectedSkill is None))]
        for SkillName in SkillCandidates[:24]:
            ModifierValue: int  = self.StateService.GetSkillModifier(SkillsDictionary, SkillName)
            ModStr       : str  = f"{"+" if (ModifierValue >= 0) else ""}{ModifierValue}"
            IsDef        : bool = (self.SelectedSkill is not None) and (self.SelectedSkill.strip().lower() == SkillName.strip().lower())
            SkillOptions.append(Discord.SelectOption(label = f"{SkillName.title()} ({ModStr})"[:100], value = SkillName, default = IsDef))

        self.SkillMenu: UserInterface.Select = UserInterface.Select(placeholder = "Select Skill (Optional)", options = SkillOptions, row = 2)
        self.SkillMenu.callback              = self.OnSkillSelected
        self.add_item(self.SkillMenu)

    async def CheckAuthorization(self, Interaction: Discord.Interaction) -> bool:
        if (self.InvokerDiscordID is not None) and (Interaction.user.id != self.InvokerDiscordID):
            await Interaction.response.send_message("Only the player who opened this interactive roll may modify or execute it.", ephemeral = True)
            return False

        if (self.TargetResolver is not None) and (Interaction.channel is not None):
            IsValid, _, GuardMessage = await self.TargetResolver.ValidateSystemGuard(Interaction.user.id, Interaction.channel.id, "MGT2E")
            if not IsValid:
                await Interaction.response.send_message(GuardMessage or "Switch to a Mongoose Traveller character before using this control.", ephemeral = True)
                return False

        return True

    async def OnBoonBaneClicked(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        if (self.NetBoons == 0):
            self.NetBoons         = 1
            self.BoonButton.label = "✨ Boon (+1)"
            self.BoonButton.style = Discord.ButtonStyle.success

        elif (self.NetBoons == 1):
            self.NetBoons         = -1
            self.BoonButton.label = "⚡ Bane (-1)"
            self.BoonButton.style = Discord.ButtonStyle.danger

        else:
            self.NetBoons         = 0
            self.BoonButton.label = "Boon / Bane"
            self.BoonButton.style = Discord.ButtonStyle.secondary

        await Interaction.response.edit_message(view = self)

    async def OnAttributeSelected(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        SelectedValue: str = "Dexterity"
        if (self.AttrMenu.values):
            SelectedValue = str(self.AttrMenu.values[0])

        self.SelectedAttribute = SelectedValue
        for Option in self.AttrMenu.options:
            Option.default = (Option.value == SelectedValue)

        await Interaction.response.edit_message(view = self)

    async def OnSkillSelected(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        SelectedValue: str = "__NONE__"
        if (self.SkillMenu.values):
            SelectedValue = str(self.SkillMenu.values[0])

        if (SelectedValue == "__NONE__"):
            self.SelectedSkill = None

        else:
            self.SelectedSkill     = SelectedValue
            self.SelectedAttribute = self.StateService.GetDefaultCharacteristicForSkill(SelectedValue)
            for AttrOption in self.AttrMenu.options:
                AttrOption.default = (AttrOption.value == self.SelectedAttribute)

        for Option in self.SkillMenu.options:
            Option.default = (Option.value == SelectedValue)

        await Interaction.response.edit_message(view = self)

    async def OnFinalizeClicked(self, Interaction: Discord.Interaction) -> None:
        if not await self.CheckAuthorization(Interaction):
            return

        DetailData     : dict           = self.CharacterRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.get("Characteristics", {})
        Skills         : dict[str, int] = DetailData.get("Skills", {})
        CharacterName  : str            = str(self.CharacterRecord.get("Name", "Traveller"))

        StatScore: int = int(Characteristics.get(self.SelectedAttribute, 7))
        StatDM   : int = self.StateService.CalculateCharacteristicModifier(StatScore)

        SkillModifier: int = 0
        if self.SelectedSkill:
            SkillModifier = self.StateService.GetSkillModifier(Skills, self.SelectedSkill)

        TotalModifier: int                         = StatDM + SkillModifier + self.SituationalModifier
        RollOutcome  : MGT2EState.MGT2ERollOutcome = self.StateService.EvaluateRoll(Modifier = TotalModifier, NetBoons = self.NetBoons, TargetDifficulty = self.TargetDifficulty)

        for ChildItem in self.children:
            if hasattr(ChildItem, "disabled"):
                ChildItem.disabled = True

        CheckTitle : str           = f"{self.SelectedSkill.title()} ({self.SelectedAttribute[:3].upper()})" if self.SelectedSkill else f"{self.SelectedAttribute} Check"
        EmbedColor : int           = COLOR_SUCCESS_EMBED if (RollOutcome.IsSuccess) else COLOR_FAILURE_EMBED
        ResultEmbed: Discord.Embed = Discord.Embed(title = f"{CharacterName}: {CheckTitle}", color = EmbedColor)
        ResultEmbed.add_field(name = "Result", value = RollOutcome.BreakdownString, inline = False)
        ResultEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
        ResultEmbed.set_footer(text = "Tally │ Mongoose Traveller Interactive Roll")

        await Interaction.response.edit_message(embed = ResultEmbed, view = self)
        if (self.CompletionCallback is not None):
            await self.CompletionCallback(Interaction, RollOutcome, CheckTitle)
