import re                                              as RegularExpressions
import typing                                          as Typing
import discord                                         as Discord
import discord.ext.commands                            as Commands
import Runtime.Configuration.Config                    as Config
import Runtime.Services.DebugService                   as Debug
import Runtime.Services.PlatformClient                 as PlatformClient
import Runtime.Services.ServerSettingsService          as ServerSettings
import Runtime.Services.CompendiumTagRenderer          as TagRenderer
import Runtime.Services.Compendium.SourceFilterService as SourceFilter
import Runtime.Application.Components.VersionView      as VersionView

COLOR_LOOKUP_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED : int = 0xA60000
SINGULAR_CATEGORY_MAPPING: dict[str, str] = {
    "Subclasses": "Subclass",
    "Classes"   : "Class",
    "Species"   : "Species"
}

SOURCE_FLAG_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"(?:-s|--source)\s+([a-zA-Z0-9]+)$", RegularExpressions.IGNORECASE)
SOURCE_PIPE_PATTERN: RegularExpressions.Pattern = RegularExpressions.compile(r"\|\s*([a-zA-Z0-9]+)$")

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance: Typing.Optional[ServerSettings.ServerSettingsService] = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

def ExtractQueryAndSource(RawQuery: str) -> tuple[str, Typing.Optional[str]]:
    CleanText: str                                       = RawQuery.strip()
    FlagMatch: Typing.Optional[RegularExpressions.Match] = SOURCE_FLAG_PATTERN.search(CleanText)
    if (FlagMatch is not None):
        SourceBook: str = FlagMatch.group(1).strip()
        QueryName : str = CleanText[:FlagMatch.start()].strip()
        return (QueryName, SourceBook)

    PipeMatch: Typing.Optional[RegularExpressions.Match] = SOURCE_PIPE_PATTERN.search(CleanText)
    if (PipeMatch is not None):
        SourceBook: str = PipeMatch.group(1).strip()
        QueryName : str = CleanText[:PipeMatch.start()].strip()
        return (QueryName, SourceBook)

    return (CleanText, None)

class LookupCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, PlatformClientInstance: Typing.Optional[PlatformClient.TallyPlatformClient] = None) -> None:
        self.BotInstance   : Commands.Bot                       = BotInstance
        self.PlatformClient: PlatformClient.TallyPlatformClient = PlatformClientInstance if (PlatformClientInstance is not None) else (getattr(BotInstance, "PlatformClient", None) or PlatformClient.TallyPlatformClient())
        self.TagRenderer   : TagRenderer.CompendiumTagRenderer  = TagRenderer.CompendiumTagRenderer()
        self.SourceFilter  : SourceFilter.SourceFilterService   = SourceFilter.SourceFilterService()

    async def ResolveRuleSetEnforcementMode(self, Context: Commands.Context) -> str:
        if (Context.guild is None):
            return "Standard"

        ServerSettingsInstance: Typing.Optional[ServerSettings.ServerSettingsService] = getattr(Context.bot, "ServerSettingsService", None)
        if (ServerSettingsInstance is None):
            return "Standard"

        SettingsRecord: ServerSettings.ServerSettingsModel = await ServerSettingsInstance.GetServerSettings(Context.guild.id)
        return SettingsRecord.RuleSetEnforcementMode

    async def ExecuteEntityLookup(self, Context: Commands.Context, RawQuery: str, CategoryName: str, FetchFunction: Typing.Callable[[str, Typing.Optional[str]], Typing.Coroutine[Typing.Any, Typing.Any, Typing.Optional[dict[str, Typing.Any]]]], FormatterFunction: Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed], CommandKeyword: str) -> None:
        QueryName      : str = ""
        SourceBook     : Typing.Optional[str] = None
        QueryName, SourceBook = ExtractQueryAndSource(RawQuery)
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"{CategoryName} Lookup Initiated: Query=\"{QueryName}\", Source=\"{SourceBook}\"")

        Record: Typing.Optional[dict[str, Typing.Any]] = await FetchFunction(QueryName, SourceBook)
        if (Record is not None):
            VersionsList: list[dict[str, Typing.Any]] = list(Record.get("Versions", []))

            if (SourceBook is not None) or (len(VersionsList) <= 1):
                ResultEmbed: Discord.Embed = FormatterFunction(Record, EnforcementMode)
                if (len(VersionsList) > 1):
                    ActiveVersionView: VersionView.VersionView = VersionView.VersionView(RecordData = Record, TagRendererInstance = self.TagRenderer, FormatterFunction = FormatterFunction, RuleSetEnforcementMode = EnforcementMode, AuthorID = Context.author.id)
                    await Context.send(embed = ResultEmbed, view = ActiveVersionView)

                else:
                    await Context.send(embed = ResultEmbed)

                return

            PromptEmbed      : Discord.Embed           = VersionView.CreateVersionPromptEmbed(str(Record.get("name", QueryName)), CategoryName, VersionsList)
            ActiveVersionView: VersionView.VersionView = VersionView.VersionView(RecordData = Record, TagRendererInstance = self.TagRenderer, FormatterFunction = FormatterFunction, RuleSetEnforcementMode = EnforcementMode, AuthorID = Context.author.id)
            await Context.send(embed = PromptEmbed, view = ActiveVersionView)
            return

        SearchResponse  : dict[str, Typing.Any]       = await self.PlatformClient.SearchCompendium(QueryName, Category = CategoryName, Limit = 5)
        CategoryResults : list[dict[str, Typing.Any]] = SearchResponse.get("Results", {}).get(CategoryName, [])
        CloseMatches    : list[str]                   = [str(Entry.get("name", "")) for Entry in CategoryResults if Entry.get("name")]
        SuggestionText  : str                         = (f"\n\nDid you mean: {", ".join(f"`{MatchItem}`" for MatchItem in CloseMatches)}?") if CloseMatches else ""
        CategorySingular: str                         = SINGULAR_CATEGORY_MAPPING.get(CategoryName, CategoryName[:-1] if CategoryName.endswith("s") else CategoryName)
        NotFoundEmbed   : Discord.Embed               = Discord.Embed(title = f"{CategorySingular} Not Found", description = f"No {CategoryName.lower()} found matching `{QueryName}` in the compendium.{SuggestionText}", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"Tally │ Compendium Lookup ({Context.prefix}{CommandKeyword})")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "spell")
    @Commands.check(CheckDND5EPrefix)
    async def SpellCommand(self, Context: Commands.Context, *, SpellNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, SpellNameQuery, "Spells", self.PlatformClient.FetchSpellDetails, self.TagRenderer.FormatSpellEmbed, "spell")

    @Commands.command(name = "monster")
    @Commands.check(CheckDND5EPrefix)
    async def MonsterCommand(self, Context: Commands.Context, *, MonsterNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, MonsterNameQuery, "Monsters", self.PlatformClient.FetchMonsterDetails, self.TagRenderer.FormatMonsterEmbed, "monster")

    @Commands.command(name = "item")
    @Commands.check(CheckDND5EPrefix)
    async def ItemCommand(self, Context: Commands.Context, *, ItemNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, ItemNameQuery, "Items", self.PlatformClient.FetchItemDetails, self.TagRenderer.FormatItemEmbed, "item")

    @Commands.command(name = "feat")
    @Commands.check(CheckDND5EPrefix)
    async def FeatureCommand(self, Context: Commands.Context, *, FeatureNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, FeatureNameQuery, "Features", self.PlatformClient.FetchFeatDetails, self.TagRenderer.FormatFeatureEmbed, "feat")

    @Commands.command(name = "option", aliases = ["opt"])
    @Commands.check(CheckDND5EPrefix)
    async def OptionCommand(self, Context: Commands.Context, *, OptionNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, OptionNameQuery, "Options", self.PlatformClient.FetchOptionDetails, self.TagRenderer.FormatOptionEmbed, "option")

    @Commands.command(name = "rule")
    @Commands.check(CheckDND5EPrefix)
    async def RuleCommand(self, Context: Commands.Context, *, RuleNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, RuleNameQuery, "Rules", self.PlatformClient.FetchRuleDetails, self.TagRenderer.FormatRuleEmbed, "rule")

    @Commands.command(name = "class")
    @Commands.check(CheckDND5EPrefix)
    async def ClassCommand(self, Context: Commands.Context, *, ClassNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, ClassNameQuery, "Classes", self.PlatformClient.FetchClassDetails, self.TagRenderer.FormatClassEmbed, "class")

    @Commands.command(name = "subclass", aliases = ["sub"])
    @Commands.check(CheckDND5EPrefix)
    async def SubclassCommand(self, Context: Commands.Context, *, SubclassNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, SubclassNameQuery, "Subclasses", self.PlatformClient.FetchSubclassDetails, self.TagRenderer.FormatSubclassEmbed, "subclass")

    @Commands.command(name = "background")
    @Commands.check(CheckDND5EPrefix)
    async def BackgroundCommand(self, Context: Commands.Context, *, BackgroundNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, BackgroundNameQuery, "Backgrounds", self.PlatformClient.FetchBackgroundDetails, self.TagRenderer.FormatBackgroundEmbed, "background")

    @Commands.command(name = "species", aliases = ["race"])
    @Commands.check(CheckDND5EPrefix)
    async def SpeciesCommand(self, Context: Commands.Context, *, SpeciesNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, SpeciesNameQuery, "Species", self.PlatformClient.FetchSpeciesDetails, self.TagRenderer.FormatSpeciesEmbed, "species")

    @Commands.command(name = "condition")
    @Commands.check(CheckDND5EPrefix)
    async def ConditionCommand(self, Context: Commands.Context, *, ConditionNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, ConditionNameQuery, "Conditions", self.PlatformClient.FetchConditionDetails, self.TagRenderer.FormatConditionEmbed, "condition")

    @Commands.command(name = "deity")
    @Commands.check(CheckDND5EPrefix)
    async def DeityCommand(self, Context: Commands.Context, *, DeityNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, DeityNameQuery, "Deities", self.PlatformClient.FetchDeityDetails, self.TagRenderer.FormatDeityEmbed, "deity")

    @Commands.command(name = "vehicle")
    @Commands.check(CheckDND5EPrefix)
    async def VehicleCommand(self, Context: Commands.Context, *, VehicleNameQuery: str) -> None:
        await self.ExecuteEntityLookup(Context, VehicleNameQuery, "Vehicles", self.PlatformClient.FetchVehicleDetails, self.TagRenderer.FormatVehicleEmbed, "vehicle")

    @Commands.command(name = "lookup", aliases = ["search"])
    @Commands.check(CheckDND5EPrefix)
    async def LookupCommand(self, Context: Commands.Context, *, SearchQuery: str) -> None:
        QueryCleaned   : str = SearchQuery.strip().lower()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        PrefixStr      : str = str(Context.prefix)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Unified Lookup Initiated: Query=\"{QueryCleaned}\"")

        FormatterMapping: dict[str, Typing.Callable[[dict[str, Typing.Any], str], Discord.Embed]] = {
            "Spells"     : self.TagRenderer.FormatSpellEmbed,
            "Monsters"   : self.TagRenderer.FormatMonsterEmbed,
            "Items"      : self.TagRenderer.FormatItemEmbed,
            "Features"   : self.TagRenderer.FormatFeatureEmbed,
            "Options"    : self.TagRenderer.FormatOptionEmbed,
            "Rules"      : self.TagRenderer.FormatRuleEmbed,
            "Classes"    : self.TagRenderer.FormatClassEmbed,
            "Subclasses" : self.TagRenderer.FormatSubclassEmbed,
            "Backgrounds": self.TagRenderer.FormatBackgroundEmbed,
            "Species"    : self.TagRenderer.FormatSpeciesEmbed,
            "Conditions" : self.TagRenderer.FormatConditionEmbed,
            "Deities"    : self.TagRenderer.FormatDeityEmbed,
            "Vehicles"   : self.TagRenderer.FormatVehicleEmbed
        }

        SearchResponse: dict[str, Typing.Any]                  = await self.PlatformClient.SearchCompendium(QueryCleaned, Limit = 5)
        ResultsMap    : dict[str, list[dict[str, Typing.Any]]] = SearchResponse.get("Results", {})
        ActiveResults : dict[str, list[dict[str, Typing.Any]]] = {Category: Items for Category, Items in ResultsMap.items() if Items}

        TotalMatchesCount: int = sum(len(Items) for Items in ActiveResults.values())
        if (TotalMatchesCount == 0):
            EmptyEmbed: Discord.Embed = Discord.Embed(title = "No Results Found", description = f"No compendium entries matched `{SearchQuery.strip()}` across any category.", color = COLOR_ERROR_EMBED)
            EmptyEmbed.set_footer(text = f"Tally │ Compendium Unified Search ({PrefixStr}lookup)")
            await Context.send(embed = EmptyEmbed)
            return

        OverviewEmbed: Discord.Embed = Discord.Embed(title = f"Compendium Search: \"{SearchQuery.strip()}\"", description = "Select an entry below from the dropdown menu to inspect its details:", color = COLOR_LOOKUP_EMBED)

        for CategoryName, ItemsList in ActiveResults.items():
            LinesList: list[str] = []
            for Item in ItemsList[:4]:
                NameStr   : str       = str(Item.get("name", ""))
                SourceStr : str       = str(Item.get("source", ""))
                Sources   : list[str] = list(Item.get("AvailableSources", []))
                SourcesTag: str       = f" *({", ".join(Sources)})*" if (len(Sources) > 1) else f" *({SourceStr})*"
                LinesList.append(f"• **{NameStr}**{SourcesTag}")

            OverviewEmbed.add_field(name = CategoryName, value = "\n".join(LinesList), inline = True)

        OverviewEmbed.set_footer(text = f"Tally │ Compendium Unified Search ({PrefixStr}lookup)")
        PickerView: VersionView.CompendiumUnifiedPickerView = VersionView.CompendiumUnifiedPickerView(SearchResults = ActiveResults, PlatformClientInstance = self.PlatformClient, TagRendererInstance = self.TagRenderer, FormatterMapping = FormatterMapping, RuleSetEnforcementMode = EnforcementMode, AuthorID = Context.author.id)
        await Context.send(embed = OverviewEmbed, view = PickerView)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(LookupCommands(BotInstance))
