import typing                         as Typing
import discord                        as Discord
import discord.ext.commands           as Commands
import Configuration.Config           as Config
import Services.DebugService          as Debug
import Services.PlatformClient        as PlatformClient
import Services.CompendiumTagRenderer as TagRenderer

COLOR_LOOKUP_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED : int = 0xA60000

def CheckDNDPrefix(Context: Commands.Context) -> bool:
    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND)

class LookupCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot) -> None:
        self.BotInstance   : Commands.Bot                               = BotInstance
        self.PlatformClient: PlatformClient.MISPlatformClient           = PlatformClient.MISPlatformClient()
        self.TagRenderer   : TagRenderer.CompendiumTagRenderer          = TagRenderer.CompendiumTagRenderer()
        self.CachedDataStore: Typing.Optional[Typing.Dict[str, Typing.Any]] = None

    async def EnsureDataStore(self) -> Typing.Optional[Typing.Dict[str, Typing.Any]]:
        if (self.CachedDataStore is None):
            try:
                self.CachedDataStore = await self.PlatformClient.FetchRulesDataStore()

            except Exception as LoadError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Load Rules DataStore from Platform: {str(LoadError)}")
                return None

        return self.CachedDataStore

    @Commands.command(name = "spell")
    @Commands.check(CheckDNDPrefix)
    async def SpellCommand(self, Context: Commands.Context, *, SpellNameQuery: str) -> None:
        QueryCleaned: str = SpellNameQuery.strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Spell Lookup Initiated: Query=\"{QueryCleaned}\"")
        SpellRecord: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.PlatformClient.FetchSpellDetails(QueryCleaned)
        if (SpellRecord is not None):
            SpellEmbed: Discord.Embed = self.TagRenderer.FormatSpellEmbed(SpellRecord)
            await Context.send(embed = SpellEmbed)
            return

        DataStore: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.EnsureDataStore()
        CloseMatches: list[str] = []
        if (DataStore is not None):
            AvailableSpells: list[str] = DataStore.get("Spells", [])
            CloseMatches = [Name for Name in AvailableSpells if QueryCleaned.lower() in Name.lower()][:5]

        SuggestionText: str = f"\n\nDid you mean: {', '.join(f'`{M}`' for M in CloseMatches)}?" if CloseMatches else ""
        NotFoundEmbed : Discord.Embed = Discord.Embed(title = "Spell Not Found", description = f"No spell found matching `{QueryCleaned}`.{SuggestionText}", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5eTools Lookup ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}spell)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "monster")
    @Commands.check(CheckDNDPrefix)
    async def MonsterCommand(self, Context: Commands.Context, *, MonsterNameQuery: str) -> None:
        QueryCleaned: str = MonsterNameQuery.strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Monster Lookup Initiated: Query=\"{QueryCleaned}\"")
        MonsterRecord: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.PlatformClient.FetchMonsterDetails(QueryCleaned)
        if (MonsterRecord is not None):
            MonsterEmbed: Discord.Embed = self.TagRenderer.FormatMonsterEmbed(MonsterRecord)
            await Context.send(embed = MonsterEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Monster Not Found", description = f"No monster found matching `{QueryCleaned}` in the 5eTools bestiary.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5eTools Lookup ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}monster)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "item")
    @Commands.check(CheckDNDPrefix)
    async def ItemCommand(self, Context: Commands.Context, *, ItemNameQuery: str) -> None:
        QueryCleaned: str = ItemNameQuery.strip()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Item Lookup Initiated: Query=\"{QueryCleaned}\"")
        ItemRecord: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.PlatformClient.FetchItemDetails(QueryCleaned)
        if (ItemRecord is not None):
            ItemEmbed: Discord.Embed = self.TagRenderer.FormatItemEmbed(ItemRecord)
            await Context.send(embed = ItemEmbed)
            return

        DataStore: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.EnsureDataStore()
        CloseMatches: list[str] = []
        if (DataStore is not None):
            AvailableItems: list[str] = DataStore.get("Items", [])
            CloseMatches = [Name for Name in AvailableItems if QueryCleaned.lower() in Name.lower()][:5]

        SuggestionText: str = f"\n\nDid you mean: {', '.join(f'`{M}`' for M in CloseMatches)}?" if CloseMatches else ""
        NotFoundEmbed : Discord.Embed = Discord.Embed(title = "Item Not Found", description = f"No item found matching `{QueryCleaned}`.{SuggestionText}", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5eTools Lookup ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}item)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "lookup")
    @Commands.check(CheckDNDPrefix)
    async def LookupCommand(self, Context: Commands.Context, *, SearchQuery: str) -> None:
        QueryCleaned: str = SearchQuery.strip().lower()
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Unified Lookup Initiated: Query=\"{QueryCleaned}\"")

        SpellResult: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.PlatformClient.FetchSpellDetails(QueryCleaned)
        if (SpellResult is not None):
            await Context.send(embed = self.TagRenderer.FormatSpellEmbed(SpellResult))
            return

        MonsterResult: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.PlatformClient.FetchMonsterDetails(QueryCleaned)
        if (MonsterResult is not None):
            await Context.send(embed = self.TagRenderer.FormatMonsterEmbed(MonsterResult))
            return

        ItemResult: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.PlatformClient.FetchItemDetails(QueryCleaned)
        if (ItemResult is not None):
            await Context.send(embed = self.TagRenderer.FormatItemEmbed(ItemResult))
            return

        DataStore: Typing.Optional[Typing.Dict[str, Typing.Any]] = await self.EnsureDataStore()
        if (DataStore is None):
            ErrorEmbed: Discord.Embed = Discord.Embed(title = "Platform Lookup Unavailable", description = "Could not reach the MIS Platform rules engine to perform search.", color = COLOR_ERROR_EMBED)
            await Context.send(embed = ErrorEmbed)
            return

        ResultsDictionary: dict[str, list[str]] = {}
        for CategoryKey in ("Spells", "Items", "Classes", "Species", "Backgrounds", "Conditions", "Languages"):
            CategoryList: list[str] = DataStore.get(CategoryKey, [])
            MatchingEntries: list[str] = [Item for Item in CategoryList if QueryCleaned in Item.lower()][:4]
            if MatchingEntries:
                ResultsDictionary[CategoryKey] = MatchingEntries

        if ResultsDictionary:
            OverviewEmbed: Discord.Embed = Discord.Embed(title = f"Search Results for \"{SearchQuery.strip()}\"", color = COLOR_LOOKUP_EMBED)
            for CatName, ItemsList in ResultsDictionary.items():
                OverviewEmbed.add_field(name = CatName, value = "\n".join(f"• {Name}" for Name in ItemsList), inline = True)

            OverviewEmbed.set_footer(text = f"MIS-Bot • 5eTools Search ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}lookup)")
            await Context.send(embed = OverviewEmbed)

        else:
            EmptyEmbed: Discord.Embed = Discord.Embed(title = "No Results Found", description = f"No compendium entries matched `{SearchQuery.strip()}`.", color = COLOR_ERROR_EMBED)
            EmptyEmbed.set_footer(text = f"MIS-Bot • 5eTools Search ({Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND}lookup)")
            await Context.send(embed = EmptyEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(LookupCommands(BotInstance))

