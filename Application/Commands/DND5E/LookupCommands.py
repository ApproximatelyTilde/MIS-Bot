import inspect                                 as Inspect
import typing                                  as Typing
import discord                                 as Discord
import discord.ext.commands                    as Commands
import Configuration.Config                    as Config
import Services.DebugService                   as Debug
import Services.PlatformClient                 as PlatformClient
import Services.ServerSettingsService          as ServerSettings
import Services.CompendiumTagRenderer          as TagRenderer
import Services.Compendium.SourceFilterService as SourceFilter
import Services.Compendium.CompendiumService   as Compendium

COLOR_LOOKUP_EMBED: int = 0x0030A6
COLOR_ERROR_EMBED : int = 0xA60000

def CheckDND5EPrefix(Context: Commands.Context) -> bool:
    ServerSettingsInstance = getattr(Context.bot, "ServerSettingsService", None)
    if (ServerSettingsInstance is not None):
        GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
        return (Context.prefix == ServerSettingsInstance.GetCachedDND5EPrefix(GuildID))

    return (Context.prefix == Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)

class LookupCommands(Commands.Cog):
    def __init__(self, BotInstance: Commands.Bot, CompendiumServiceInstance: Typing.Optional[Compendium.CompendiumService] = None) -> None:
        self.BotInstance       : Commands.Bot                              = BotInstance
        self.PlatformClient    : PlatformClient.MISPlatformClient          = PlatformClient.MISPlatformClient()
        self.CompendiumService : Compendium.CompendiumService       = CompendiumServiceInstance if (CompendiumServiceInstance is not None) else Compendium.CompendiumService()
        self.TagRenderer       : TagRenderer.CompendiumTagRenderer         = TagRenderer.CompendiumTagRenderer()
        self.SourceFilter      : SourceFilter.SourceFilterService   = SourceFilter.SourceFilterService()
        self.CachedDataStore   : Typing.Optional[dict[str, Typing.Any]] = None

    async def ResolveRuleSetEnforcementMode(self, Context: Commands.Context) -> str:
        ServerSettingsInstance = getattr(self.BotInstance, "ServerSettingsService", None)
        if isinstance(ServerSettingsInstance, ServerSettings.ServerSettingsService):
            GuildID: Typing.Optional[int] = Context.guild.id if (Context.guild is not None) else None
            SettingsModel: ServerSettings.ServerSettingsModel = await ServerSettingsInstance.GetServerSettings(GuildID)
            return SettingsModel.RuleSetEnforcementMode

        elif hasattr(ServerSettingsInstance, "GetServerSettings") and callable(ServerSettingsInstance.GetServerSettings):
            try:
                GuildID = Context.guild.id if (Context.guild is not None) else None
                SettingsResult = ServerSettingsInstance.GetServerSettings(GuildID)
                if Inspect.isawaitable(SettingsResult):
                    SettingsModel = await SettingsResult
                    return str(getattr(SettingsModel, "RuleSetEnforcementMode", "Standard"))

            except Exception as SettingsFetchError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to get server settings: {str(SettingsFetchError)}")

        return "Standard"

    async def EnsureDataStore(self) -> Typing.Optional[dict[str, Typing.Any]]:
        if (self.CachedDataStore is None):
            try:
                self.CachedDataStore = await self.PlatformClient.FetchRulesDataStore()

            except Exception as LoadError:
                Debug.LogMessage(Level = Debug.LogLevel.Warning, Message = f"Failed to Load Rules DataStore from Platform: {str(LoadError)}")
                return None

        return self.CachedDataStore

    @Commands.command(name = "spell")
    @Commands.check(CheckDND5EPrefix)
    async def SpellCommand(self, Context: Commands.Context, *, SpellNameQuery: str) -> None:
        QueryCleaned   : str = SpellNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Spell Lookup Initiated: Query=\"{QueryCleaned}\"")
        SpellRecord: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchSpellDetails(QueryCleaned)
        if (SpellRecord is not None):
            SpellEmbed: Discord.Embed = self.TagRenderer.FormatSpellEmbed(SpellRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = SpellEmbed)
            return

        DataStore: Typing.Optional[dict[str, Typing.Any]] = await self.EnsureDataStore()
        CloseMatches: list[str] = []
        if (DataStore is not None):
            AvailableSpells: list[str] = DataStore.get("Spells", [])
            FilteredMatches: list[str] = [Name for Name in AvailableSpells if QueryCleaned.lower() in Name.lower()]
            CloseMatches = self.SourceFilter.PrioritizeCandidateNames(FilteredMatches)[:5]

        SuggestionText: str           = f"\n\nDid you mean: {", ".join(f'`{M}`' for M in CloseMatches)}?" if (CloseMatches) else ""
        NotFoundEmbed : Discord.Embed = Discord.Embed(title = "Spell Not Found", description = f"No spell found matching `{QueryCleaned}`.{SuggestionText}", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}spell)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "monster")
    @Commands.check(CheckDND5EPrefix)
    async def MonsterCommand(self, Context: Commands.Context, *, MonsterNameQuery: str) -> None:
        QueryCleaned   : str = MonsterNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Monster Lookup Initiated: Query=\"{QueryCleaned}\"")
        MonsterRecord: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchMonsterDetails(QueryCleaned)
        if (MonsterRecord is not None):
            MonsterEmbed: Discord.Embed = self.TagRenderer.FormatMonsterEmbed(MonsterRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = MonsterEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Monster Not Found", description = f"No monster found matching `{QueryCleaned}` in the 5e.tools bestiary.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}monster)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "item")
    @Commands.check(CheckDND5EPrefix)
    async def ItemCommand(self, Context: Commands.Context, *, ItemNameQuery: str) -> None:
        QueryCleaned   : str = ItemNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Item Lookup Initiated: Query=\"{QueryCleaned}\"")
        ItemRecord: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchItemDetails(QueryCleaned)
        if (ItemRecord is not None):
            ItemEmbed: Discord.Embed = self.TagRenderer.FormatItemEmbed(ItemRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = ItemEmbed)
            return

        DataStore: Typing.Optional[dict[str, Typing.Any]] = await self.EnsureDataStore()
        CloseMatches: list[str] = []
        if (DataStore is not None):
            AvailableItems : list[str] = DataStore.get("Items", [])
            FilteredMatches: list[str] = [Name for Name in AvailableItems if QueryCleaned.lower() in Name.lower()]
            CloseMatches = self.SourceFilter.PrioritizeCandidateNames(FilteredMatches)[:5]

        SuggestionText: str           = f"\n\nDid you mean: {", ".join(f'`{M}`' for M in CloseMatches)}?" if (CloseMatches) else ""
        NotFoundEmbed : Discord.Embed = Discord.Embed(title = "Item Not Found", description = f"No item found matching `{QueryCleaned}`.{SuggestionText}", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}item)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "feat")
    @Commands.check(CheckDND5EPrefix)
    async def FeatureCommand(self, Context: Commands.Context, *, FeatureNameQuery: str) -> None:
        QueryCleaned   : str = FeatureNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Feat Lookup Initiated: Query=\"{QueryCleaned}\"")
        FeatureRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetFeature(QueryCleaned)
        if (FeatureRecord is not None):
            FeatureEmbed: Discord.Embed = self.TagRenderer.FormatFeatureEmbed(FeatureRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = FeatureEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Feat Not Found", description = f"No feat found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}feat)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "option", aliases = ["opt"])
    @Commands.check(CheckDND5EPrefix)
    async def OptionCommand(self, Context: Commands.Context, *, OptionNameQuery: str) -> None:
        QueryCleaned   : str = OptionNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Option Lookup Initiated: Query=\"{QueryCleaned}\"")
        OptionRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetOption(QueryCleaned)
        if (OptionRecord is not None):
            OptionEmbed: Discord.Embed = self.TagRenderer.FormatOptionEmbed(OptionRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = OptionEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Option Not Found", description = f"No option or feature found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}option)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "rule")
    @Commands.check(CheckDND5EPrefix)
    async def RuleCommand(self, Context: Commands.Context, *, RuleNameQuery: str) -> None:
        QueryCleaned   : str = RuleNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Rule Lookup Initiated: Query=\"{QueryCleaned}\"")
        RuleRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetRule(QueryCleaned)
        if (RuleRecord is not None):
            RuleEmbed: Discord.Embed = self.TagRenderer.FormatRuleEmbed(RuleRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = RuleEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Rule Not Found", description = f"No rule or table found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}rule)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "class")
    @Commands.check(CheckDND5EPrefix)
    async def ClassCommand(self, Context: Commands.Context, *, ClassNameQuery: str) -> None:
        QueryCleaned   : str = ClassNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Class Lookup Initiated: Query=\"{QueryCleaned}\"")
        ClassRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetClass(QueryCleaned)
        if (ClassRecord is not None):
            ClassEmbed: Discord.Embed = self.TagRenderer.FormatClassEmbed(ClassRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = ClassEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Class Not Found", description = f"No class found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}class)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "background", aliases = ["bg"])
    @Commands.check(CheckDND5EPrefix)
    async def BackgroundCommand(self, Context: Commands.Context, *, BackgroundNameQuery: str) -> None:
        QueryCleaned   : str = BackgroundNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Background Lookup Initiated: Query=\"{QueryCleaned}\"")
        BgRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetBackground(QueryCleaned)
        if (BgRecord is not None):
            BgEmbed: Discord.Embed = self.TagRenderer.FormatBackgroundEmbed(BgRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = BgEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Background Not Found", description = f"No background found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}background)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "species", aliases = ["race"])
    @Commands.check(CheckDND5EPrefix)
    async def SpeciesCommand(self, Context: Commands.Context, *, SpeciesNameQuery: str) -> None:
        QueryCleaned   : str = SpeciesNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Species Lookup Initiated: Query=\"{QueryCleaned}\"")
        SpeciesRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetSpecies(QueryCleaned)
        if (SpeciesRecord is not None):
            SpeciesEmbed: Discord.Embed = self.TagRenderer.FormatSpeciesEmbed(SpeciesRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = SpeciesEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Species Not Found", description = f"No species or race found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}species)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "condition", aliases = ["cond"])
    @Commands.check(CheckDND5EPrefix)
    async def ConditionCommand(self, Context: Commands.Context, *, ConditionNameQuery: str) -> None:
        QueryCleaned   : str = ConditionNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Condition Lookup Initiated: Query=\"{QueryCleaned}\"")
        ConditionRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetCondition(QueryCleaned)
        if (ConditionRecord is not None):
            CondEmbed: Discord.Embed = self.TagRenderer.FormatConditionEmbed(ConditionRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = CondEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Condition Not Found", description = f"No condition found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}condition)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "deity", aliases = ["god"])
    @Commands.check(CheckDND5EPrefix)
    async def DeityCommand(self, Context: Commands.Context, *, DeityNameQuery: str) -> None:
        QueryCleaned   : str = DeityNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Deity Lookup Initiated: Query=\"{QueryCleaned}\"")
        DeityRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetDeity(QueryCleaned)
        if (DeityRecord is not None):
            DeityEmbed: Discord.Embed = self.TagRenderer.FormatDeityEmbed(DeityRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = DeityEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Deity Not Found", description = f"No deity found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}deity)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "vehicle", aliases = ["veh"])
    @Commands.check(CheckDND5EPrefix)
    async def VehicleCommand(self, Context: Commands.Context, *, VehicleNameQuery: str) -> None:
        QueryCleaned   : str = VehicleNameQuery.strip()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Vehicle Lookup Initiated: Query=\"{QueryCleaned}\"")
        VehicleRecord: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetVehicle(QueryCleaned)
        if (VehicleRecord is not None):
            VehicleEmbed: Discord.Embed = self.TagRenderer.FormatVehicleEmbed(VehicleRecord, RuleSetEnforcementMode = EnforcementMode)
            await Context.send(embed = VehicleEmbed)
            return

        NotFoundEmbed: Discord.Embed = Discord.Embed(title = "Vehicle Not Found", description = f"No vehicle found matching `{QueryCleaned}` in 5e.tools.", color = COLOR_ERROR_EMBED)
        NotFoundEmbed.set_footer(text = f"MIS-Bot • 5e.tools Lookup ({Context.prefix}vehicle)")
        await Context.send(embed = NotFoundEmbed)

    @Commands.command(name = "lookup")
    @Commands.check(CheckDND5EPrefix)
    async def LookupCommand(self, Context: Commands.Context, *, SearchQuery: str) -> None:
        QueryCleaned   : str = SearchQuery.strip().lower()
        EnforcementMode: str = await self.ResolveRuleSetEnforcementMode(Context)
        PrefixStr      : str = str(Context.prefix)
        Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Unified Lookup Initiated: Query=\"{QueryCleaned}\"")

        ExactFeature: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetFeature(QueryCleaned)
        if (ExactFeature is not None) and (str(ExactFeature.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatFeatureEmbed(ExactFeature, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactOption: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetOption(QueryCleaned)
        if (ExactOption is not None) and (str(ExactOption.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatOptionEmbed(ExactOption, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactRule: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetRule(QueryCleaned)
        if (ExactRule is not None) and (str(ExactRule.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatRuleEmbed(ExactRule, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactClass: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetClass(QueryCleaned)
        if (ExactClass is not None) and (str(ExactClass.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatClassEmbed(ExactClass, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactBackground: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetBackground(QueryCleaned)
        if (ExactBackground is not None) and (str(ExactBackground.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatBackgroundEmbed(ExactBackground, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactSpecies: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetSpecies(QueryCleaned)
        if (ExactSpecies is not None) and (str(ExactSpecies.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatSpeciesEmbed(ExactSpecies, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactCondition: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetCondition(QueryCleaned)
        if (ExactCondition is not None) and (str(ExactCondition.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatConditionEmbed(ExactCondition, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactDeity: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetDeity(QueryCleaned)
        if (ExactDeity is not None) and (str(ExactDeity.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatDeityEmbed(ExactDeity, RuleSetEnforcementMode = EnforcementMode))
            return

        ExactVehicle: Typing.Optional[dict[str, Typing.Any]] = self.CompendiumService.GetVehicle(QueryCleaned)
        if (ExactVehicle is not None) and (str(ExactVehicle.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatVehicleEmbed(ExactVehicle, RuleSetEnforcementMode = EnforcementMode))
            return

        SpellResult: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchSpellDetails(QueryCleaned)
        if (SpellResult is not None) and (str(SpellResult.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatSpellEmbed(SpellResult, RuleSetEnforcementMode = EnforcementMode))
            return

        MonsterResult: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchMonsterDetails(QueryCleaned)
        if (MonsterResult is not None) and (str(MonsterResult.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatMonsterEmbed(MonsterResult, RuleSetEnforcementMode = EnforcementMode))
            return

        ItemResult: Typing.Optional[dict[str, Typing.Any]] = await self.PlatformClient.FetchItemDetails(QueryCleaned)
        if (ItemResult is not None) and (str(ItemResult.get("name", "")).strip().lower() == QueryCleaned):
            await Context.send(embed = self.TagRenderer.FormatItemEmbed(ItemResult, RuleSetEnforcementMode = EnforcementMode))
            return

        CompendiumResults: dict[str, list[dict[str, Typing.Any]]] = self.CompendiumService.SearchAll(QueryCleaned)
        JumpCommandMapping: dict[str, str] = {
            "Features"   : "feat",
            "Options"    : "option",
            "Rules"      : "rule",
            "Classes"    : "class",
            "Backgrounds": "background",
            "Species"    : "species",
            "Conditions" : "condition",
            "Deities"    : "deity",
            "Vehicles"   : "vehicle"
        }

        DataStore: Typing.Optional[dict[str, Typing.Any]] = await self.EnsureDataStore()
        PlatformMatches: dict[str, list[str]] = dict()
        if (DataStore is not None):
            for CategoryKey in ("Spells", "Items"):
                CategoryList      : list[str] = DataStore.get(CategoryKey, [])
                MatchingEntries   : list[str] = [Item for Item in CategoryList if QueryCleaned in Item.lower()]
                PrioritizedEntries: list[str] = self.SourceFilter.PrioritizeCandidateNames(MatchingEntries)[:4]
                if PrioritizedEntries:
                    PlatformMatches[CategoryKey] = PrioritizedEntries

        HasCompendiumMatches: bool = any((len(Items) > 0) for Items in CompendiumResults.values())
        HasPlatformMatches  : bool = any((len(Items) > 0) for Items in PlatformMatches.values())

        if HasCompendiumMatches or HasPlatformMatches:
            OverviewEmbed: Discord.Embed = Discord.Embed(title = f"Search Results for \"{SearchQuery.strip()}\"", color = COLOR_LOOKUP_EMBED)

            for CatName, ItemsList in CompendiumResults.items():
                if ItemsList:
                    CmdName  : str       = JumpCommandMapping.get(CatName, "lookup")
                    JumpLines: list[str] = [f"• `{PrefixStr}{CmdName} {Item.get("name")}`" for Item in ItemsList[:4]]
                    OverviewEmbed.add_field(name = CatName, value = "\n".join(JumpLines), inline = True)

            for CatName, NamesList in PlatformMatches.items():
                if NamesList:
                    CmdName  : str       = "spell" if (CatName == "Spells") else "item"
                    JumpLines: list[str] = [f"• `{PrefixStr}{CmdName} {Name}`" for Name in NamesList]
                    OverviewEmbed.add_field(name = CatName, value = "\n".join(JumpLines), inline = True)

            OverviewEmbed.set_footer(text = f"MIS-Bot • 5e.tools Unified Search ({PrefixStr}lookup)")
            await Context.send(embed = OverviewEmbed)

        else:
            EmptyEmbed: Discord.Embed = Discord.Embed(title = "No Results Found", description = f"No compendium entries matched `{SearchQuery.strip()}` across any category.", color = COLOR_ERROR_EMBED)
            EmptyEmbed.set_footer(text = f"MIS-Bot • 5e.tools Unified Search ({PrefixStr}lookup)")
            await Context.send(embed = EmptyEmbed)

async def setup(BotInstance: Commands.Bot) -> None:
    await BotInstance.add_cog(LookupCommands(BotInstance))
