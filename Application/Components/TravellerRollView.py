import typing                         as Typing
import discord                        as Discord
import discord.ui                     as UserInterface
import Services.DebugService          as Debug
import Services.TravellerStateService as TravellerStateService

COLOR_SUCCESS_EMBED: int = 0x005E00
COLOR_FAILURE_EMBED: int = 0xA60000

class TravellerRollView(UserInterface.View):
    def __init__(self, StateService: TravellerStateService.TravellerStateService, CharacterRecord: dict[str, Typing.Any], SelectedSkill: Typing.Optional[str] = None, SelectedAttribute: Typing.Optional[str] = None, TargetDifficulty: int = TravellerStateService.DEFAULT_DIFFICULTY_AVERAGE) -> None:
        super().__init__(timeout = 180.0)
        self.StateService      : TravellerStateService.TravellerStateService = StateService
        self.CharacterRecord   : dict[str, Typing.Any]                       = CharacterRecord
        self.SelectedSkill     : Typing.Optional[str]                        = SelectedSkill
        self.SelectedAttribute : str                                         = SelectedAttribute if (SelectedAttribute is not None) else "Dexterity"
        self.TargetDifficulty  : int                                         = TargetDifficulty
        self.NetBoons          : int                                         = 0

        self.BoonButton     : UserInterface.Button = UserInterface.Button(label = "Boon / Bane", style = Discord.ButtonStyle.secondary, row = 0)
        self.BoonButton.callback                   = self.OnBoonBaneClicked
        self.add_item(self.BoonButton)

        self.FinalizeButton : UserInterface.Button = UserInterface.Button(label = "Roll 2d6", style = Discord.ButtonStyle.primary, emoji = "🎲", row = 0)
        self.FinalizeButton.callback               = self.OnFinalizeClicked
        self.add_item(self.FinalizeButton)

        self.BuildAttributeSelect()

    def BuildAttributeSelect(self) -> None:
        DetailData     : dict           = self.CharacterRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.get("Characteristics", {})

        SelectOptions: list[Discord.SelectOption] = []
        for ShortName, FullName in [("STR", "Strength"), ("DEX", "Dexterity"), ("END", "Endurance"), ("INT", "Intelligence"), ("EDU", "Education"), ("SOC", "SocialStanding")]:
            ScoreVal: int = Characteristics.get(FullName, 7)
            DMVal   : int = self.StateService.CalculateCharacteristicModifier(ScoreVal)
            IsDefault: bool = (FullName == self.SelectedAttribute)
            SelectOptions.append(Discord.SelectOption(label = f"{ShortName}: {ScoreVal} (DM: {'+' if DMVal >= 0 else ''}{DMVal})", value = FullName, default = IsDefault))

        AttrMenu: UserInterface.Select = UserInterface.Select(placeholder = "Select Characteristic", options = SelectOptions, row = 1)
        AttrMenu.callback              = self.OnAttributeSelected
        self.add_item(AttrMenu)

    async def OnBoonBaneClicked(self, Interaction: Discord.Interaction) -> None:
        if (self.NetBoons == 0):
            self.NetBoons           = 1
            self.BoonButton.label   = "✨ Boon (+1)"
            self.BoonButton.style   = Discord.ButtonStyle.success

        elif (self.NetBoons > 0):
            self.NetBoons           = -1
            self.BoonButton.label   = "⚡ Bane (-1)"
            self.BoonButton.style   = Discord.ButtonStyle.danger

        else:
            self.NetBoons           = 0
            self.BoonButton.label   = "Boon / Bane"
            self.BoonButton.style   = Discord.ButtonStyle.secondary

        await Interaction.response.edit_message(view = self)

    async def OnAttributeSelected(self, Interaction: Discord.Interaction) -> None:
        SelectComponent: UserInterface.Select = Typing.cast(UserInterface.Select, Interaction.data.get("values", ["Dexterity"]))
        SelectedVal    : str                  = SelectComponent[0] if isinstance(SelectComponent, list) else "Dexterity"
        self.SelectedAttribute                = SelectedVal
        await Interaction.response.edit_message(view = self)

    async def OnFinalizeClicked(self, Interaction: Discord.Interaction) -> None:
        DetailData     : dict           = self.CharacterRecord.get("DetailData", {})
        Characteristics: dict[str, int] = DetailData.get("Characteristics", {})
        Skills         : dict[str, int] = DetailData.get("Skills", {})
        CharName       : str            = str(self.CharacterRecord.get("Name", "Hero"))

        StatScore: int = Characteristics.get(self.SelectedAttribute, 7)
        StatDM   : int = self.StateService.CalculateCharacteristicModifier(StatScore)

        SkillMod: int = 0
        if self.SelectedSkill:
            SkillMod = self.StateService.GetSkillModifier(Skills, self.SelectedSkill)

        TotalModifier: int = StatDM + SkillMod
        RollOutcome  : TravellerStateService.TravellerRollOutcome = self.StateService.EvaluateRoll(
            Modifier         = TotalModifier,
            NetBoons         = self.NetBoons,
            TargetDifficulty = self.TargetDifficulty
        )

        for ChildItem in self.children:
            ChildItem.disabled = True

        EmbedColor: int = COLOR_SUCCESS_EMBED if RollOutcome.IsSuccess else COLOR_FAILURE_EMBED
        TitleText : str = f"{CharName}: {self.SelectedSkill or self.SelectedAttribute} Check"
        ResultEmbed: Discord.Embed = Discord.Embed(title = TitleText, color = EmbedColor)
        ResultEmbed.add_field(name = "Result", value = RollOutcome.BreakdownString, inline = False)
        ResultEmbed.add_field(name = "Outcome", value = f"**{RollOutcome.OutcomeDescription}**", inline = False)
        ResultEmbed.set_footer(text = "MIS-Bot • MGT2E Interactive Roll")

        await Interaction.response.edit_message(embed = ResultEmbed, view = self)

