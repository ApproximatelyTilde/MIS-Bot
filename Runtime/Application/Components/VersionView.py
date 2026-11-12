import typing                                 as Typing
import discord                                as Discord
import Runtime.Services.PlatformClient        as PlatformClient
import Runtime.Services.CompendiumTagRenderer as TagRenderer

COLOR_VERSION_PICKER_EMBED: int            = 0x0030A6
SINGULAR_CATEGORY_MAPPING : dict[str, str] = {
    "Subclasses": "Subclass",
    "Classes"   : "Class",
    "Species"   : "Species"
}

class VersionView(Discord.ui.View):
    def __init__(self, RecordData            : dict[str, Typing.Any], TagRendererInstance   : TagRenderer.CompendiumTagRenderer, FormatterFunction     : Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed], RuleSetEnforcementMode: str = "Standard", AuthorID              : Typing.Optional[int] = None) -> None:
        super().__init__(timeout = 300.0)
        self.RecordData            : dict[str, Typing.Any]                                        = RecordData
        self.VersionsList          : list[dict[str, Typing.Any]]                                  = RecordData.get("Versions", [])
        self.TagRenderer           : TagRenderer.CompendiumTagRenderer                            = TagRendererInstance
        self.FormatterFunction     : Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed] = FormatterFunction
        self.RuleSetEnforcementMode: str                                                          = RuleSetEnforcementMode
        self.AuthorID              : Typing.Optional[int]                                         = AuthorID
        self.CurrentSource         : str                                                          = str(RecordData.get("source", ""))

        self.BuildComponents()

    def BuildComponents(self) -> None:
        self.clear_items()
        if (len(self.VersionsList) <= 4):
            for VersionItem in self.VersionsList:
                SourceCode : str                 = str(VersionItem.get("Source", ""))
                Year       : int                 = int(VersionItem.get("PublicationYear", 0))
                ButtonLabel: str                 = f"{SourceCode} ({Year})" if (Year > 0) else SourceCode
                IsCurrent  : bool                = (SourceCode == self.CurrentSource)
                ButtonStyle: Discord.ButtonStyle = Discord.ButtonStyle.primary if IsCurrent else Discord.ButtonStyle.secondary

                VersionButton: Discord.ui.Button = Discord.ui.Button(label = ButtonLabel, style = ButtonStyle, custom_id = f"compendium_version_{SourceCode}", disabled = IsCurrent)
                VersionButton.callback           = self.CreateButtonCallback(VersionItem)
                self.add_item(VersionButton)

        else:
            SelectOptions: list[Discord.SelectOption] = []
            for VersionItem in self.VersionsList:
                SourceCode : str  = str(VersionItem.get("Source", ""))
                DisplayName: str  = str(VersionItem.get("SourceDisplayName", SourceCode))
                Year       : int  = int(VersionItem.get("PublicationYear", 0))
                IsCurrent  : bool = (SourceCode == self.CurrentSource)
                SelectOptions.append(Discord.SelectOption(label = f"{SourceCode} ({Year})" if (Year > 0) else SourceCode, description = DisplayName[:100], value = SourceCode, default = IsCurrent))

            VersionSelect: Discord.ui.Select = Discord.ui.Select(placeholder = "Select Edition / Sourcebook...", options = SelectOptions, custom_id = "compendium_select_version")
            VersionSelect.callback           = self.SelectCallback
            self.add_item(VersionSelect)

    def CreateButtonCallback(self, TargetVersionItem: dict[str, Typing.Any]) -> Typing.Callable[[Discord.Interaction], Typing.Coroutine[Typing.Any, Typing.Any, None]]:
        async def ButtonCallback(Interaction: Discord.Interaction) -> None:
            if (self.AuthorID is not None) and (Interaction.user.id != self.AuthorID):
                await Interaction.response.send_message("Only the command author can switch versions.", ephemeral = True)
                return

            self.CurrentSource                = str(TargetVersionItem.get("Source", ""))
            TargetData: dict[str, Typing.Any] = TargetVersionItem.get("Data", {})
            NewEmbed  : Discord.Embed         = self.FormatterFunction(TargetData, self.RuleSetEnforcementMode)
            self.BuildComponents()
            await Interaction.response.edit_message(embed = NewEmbed, view = self)

        return ButtonCallback

    async def SelectCallback(self, Interaction: Discord.Interaction) -> None:
        if (self.AuthorID is not None) and (Interaction.user.id != self.AuthorID):
            await Interaction.response.send_message("Only the command author can switch versions.", ephemeral = True)
            return

        ValuesList: list[str] = Interaction.data.get("values", [])
        if not ValuesList:
            return

        SelectedSource: str                                    = ValuesList[0]
        TargetItem    : Typing.Optional[dict[str, Typing.Any]] = next((V for V in self.VersionsList if (str(V.get("Source", "")) == SelectedSource)), None)
        if (TargetItem is not None):
            self.CurrentSource                = SelectedSource
            TargetData: dict[str, Typing.Any] = TargetItem.get("Data", {})
            NewEmbed  : Discord.Embed         = self.FormatterFunction(TargetData, self.RuleSetEnforcementMode)
            self.BuildComponents()
            await Interaction.response.edit_message(embed = NewEmbed, view = self)

def CreateVersionPromptEmbed(CanonicalName: str, CategoryName: str, VersionsList: list[dict[str, Typing.Any]]) -> Discord.Embed:
    PromptEmbed: Discord.Embed = Discord.Embed(title = f"{CanonicalName} — Select Version", description = f"Multiple versions of **{CanonicalName}** were found in the compendium.\nPlease select which version you would like to view:", color = COLOR_VERSION_PICKER_EMBED)

    VersionLines: list[str]    = []
    for Index, VersionItem in enumerate(VersionsList, 1):
        SourceCode : str = str(VersionItem.get("Source", ""))
        DisplayName: str = str(VersionItem.get("SourceDisplayName", SourceCode))
        Year       : int = int(VersionItem.get("PublicationYear", 0))
        YearTag    : str = f" ({Year})" if (Year > 0) else ""
        PrimaryTag : str = " **[Primary]**" if VersionItem.get("IsPrimary") else ""
        VersionLines.append(f"{Index}. **{SourceCode}**{YearTag} — *{DisplayName}*{PrimaryTag}")

    PromptEmbed.add_field(name = f"Available Versions ({CategoryName})", value = "\n".join(VersionLines), inline = False)
    PromptEmbed.set_footer(text = "Tally │ Compendium Version Selector")
    return PromptEmbed

class CompendiumUnifiedPickerView(Discord.ui.View):
    def __init__(self, SearchResults         : dict[str, list[dict[str, Typing.Any]]], PlatformClientInstance: PlatformClient.TallyPlatformClient, TagRendererInstance   : TagRenderer.CompendiumTagRenderer, FormatterMapping      : dict[str, Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed]], RuleSetEnforcementMode: str = "Standard", AuthorID              : Typing.Optional[int] = None) -> None:
        super().__init__(timeout = 300.0)
        self.SearchResults         : dict[str, list[dict[str, Typing.Any]]]                                  = SearchResults
        self.PlatformClient        : PlatformClient.TallyPlatformClient                                      = PlatformClientInstance
        self.TagRenderer           : TagRenderer.CompendiumTagRenderer                                       = TagRendererInstance
        self.FormatterMapping      : dict[str, Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed]] = FormatterMapping
        self.RuleSetEnforcementMode: str                                                                     = RuleSetEnforcementMode
        self.AuthorID              : Typing.Optional[int]                                                    = AuthorID

        self.BuildSelectMenu()

    def BuildSelectMenu(self) -> None:
        SelectOptions: list[Discord.SelectOption] = []

        for CategoryName, EntriesList in self.SearchResults.items():
            for Entry in EntriesList:
                if (len(SelectOptions) >= 25):
                    break

                CanonicalName       : str       = str(Entry.get("name", ""))
                PrimarySource       : str       = str(Entry.get("source", ""))
                AvailableSourcesList: list[str] = list(Entry.get("AvailableSources", []))
                SourcesString       : str       = f"Sources: {", ".join(AvailableSourcesList)}" if AvailableSourcesList else f"Source: {PrimarySource}"
                CategoryShort       : str       = SINGULAR_CATEGORY_MAPPING.get(CategoryName, CategoryName[:-1] if CategoryName.endswith("s") else CategoryName)

                SelectOptions.append(Discord.SelectOption(label = f"[{CategoryShort}] {CanonicalName}"[:100], description = SourcesString[:100], value = f"{CategoryName}::{CanonicalName}::{PrimarySource}"))

            if (len(SelectOptions) >= 25):
                break

        if SelectOptions:
            PickerSelect: Discord.ui.Select = Discord.ui.Select(placeholder = "Choose an entity to view details...", options = SelectOptions, custom_id = "compendium_unified_select")
            PickerSelect.callback           = self.UnifiedSelectCallback
            self.add_item(PickerSelect)

    async def UnifiedSelectCallback(self, Interaction: Discord.Interaction) -> None:
        if (self.AuthorID is not None) and (Interaction.user.id != self.AuthorID):
            await Interaction.response.send_message("Only the command author can select an item.", ephemeral = True)
            return

        ValuesList: list[str] = Interaction.data.get("values", [])
        if not ValuesList:
            return

        SelectedValue: str                       = ValuesList[0]
        CategoryName, CanonicalName, TargetSource = SelectedValue.split("::", 2)

        RecordData: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchEntityRulesData(CategoryName, CanonicalName, Source = TargetSource)
        if (RecordData is None):
            await Interaction.response.send_message(f"Could not load details for **{CanonicalName}**.", ephemeral = True)
            return

        FormatterFunction: Typing.Optional[Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed]] = self.FormatterMapping.get(CategoryName)
        if (FormatterFunction is None):
            await Interaction.response.send_message(f"No renderer available for {CategoryName}.", ephemeral = True)
            return

        ResultEmbed : Discord.Embed               = FormatterFunction(RecordData, self.RuleSetEnforcementMode)
        VersionsList: list[dict[str, Typing.Any]] = RecordData.get("Versions", [])

        if (len(VersionsList) > 1):
            ActiveVersionView: VersionView = VersionView(RecordData = RecordData, TagRendererInstance = self.TagRenderer, FormatterFunction = FormatterFunction, RuleSetEnforcementMode = self.RuleSetEnforcementMode, AuthorID = self.AuthorID)
            await Interaction.response.edit_message(embed = ResultEmbed, view = ActiveVersionView)

        else:
            await Interaction.response.edit_message(embed = ResultEmbed, view = None)
