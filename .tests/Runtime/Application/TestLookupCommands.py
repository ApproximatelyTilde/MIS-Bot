import typing                                          as Typing
import unittest.mock                                   as MockLibrary
import discord                                         as Discord
import pytest                                          as Pytest
import Runtime.Configuration.Config                    as Config
import Runtime.Application.Commands.DND5E.LookupCommands as LookupCommands
import Runtime.Application.Components.VersionView      as VersionView
import Runtime.Services.ServerSettingsService          as ServerSettings

def BuildMockContext(PrefixValue: str = "!", GuildID: Typing.Optional[int] = 123456) -> MockLibrary.MagicMock:
    MockContext: MockLibrary.MagicMock = MockLibrary.MagicMock()
    MockContext.prefix                 = PrefixValue
    MockContext.author                 = MockLibrary.MagicMock()
    MockContext.author.id              = 999888777
    MockContext.send                   = MockLibrary.AsyncMock()
    MockContext.bot                    = MockLibrary.MagicMock()
    MockContext.bot.ServerSettingsService = None
    if (GuildID is not None):
        MockContext.guild    = MockLibrary.MagicMock()
        MockContext.guild.id = GuildID

    else:
        MockContext.guild = None

    return MockContext

class TestLookupCommands:
    def TestExtractQueryAndSource(self) -> None:
        assert (LookupCommands.ExtractQueryAndSource("Fireball") == ("Fireball", None))
        assert (LookupCommands.ExtractQueryAndSource("Fireball -s PHB") == ("Fireball", "PHB"))
        assert (LookupCommands.ExtractQueryAndSource("Magic Missile --source XPHB") == ("Magic Missile", "XPHB"))
        assert (LookupCommands.ExtractQueryAndSource("Shield | TCE") == ("Shield", "TCE"))

    def TestCheckDND5EPrefix(self) -> None:
        DefaultContext: MockLibrary.MagicMock = BuildMockContext(PrefixValue = Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E)
        assert (LookupCommands.CheckDND5EPrefix(DefaultContext) is True)

        MockSettingsService: MockLibrary.MagicMock             = MockLibrary.MagicMock()
        MockSettingsService.GetCachedDND5EPrefix.return_value  = "?"
        CustomContext      : MockLibrary.MagicMock             = BuildMockContext(PrefixValue = "?")
        CustomContext.bot.ServerSettingsService                = MockSettingsService
        assert (LookupCommands.CheckDND5EPrefix(CustomContext) is True)

    @Pytest.mark.asyncio
    async def TestResolveRuleSetEnforcementMode(self) -> None:
        MockBot: MockLibrary.MagicMock                = MockLibrary.MagicMock()
        MockBot.PlatformClient                        = MockLibrary.MagicMock()
        CogInstance: LookupCommands.LookupCommands    = LookupCommands.LookupCommands(MockBot)

        DirectMessageContext: MockLibrary.MagicMock = BuildMockContext(GuildID = None)
        assert ((await CogInstance.ResolveRuleSetEnforcementMode(DirectMessageContext)) == "Standard")

        GuildContext: MockLibrary.MagicMock                   = BuildMockContext(GuildID = 555)
        MockSettingsService: MockLibrary.MagicMock            = MockLibrary.MagicMock()
        MockSettingsService.GetServerSettings                 = MockLibrary.AsyncMock(return_value = ServerSettings.ServerSettingsModel(GuildID = "555", RuleSetEnforcementMode = "Strict2024"))
        GuildContext.bot.ServerSettingsService                = MockSettingsService
        assert ((await CogInstance.ResolveRuleSetEnforcementMode(GuildContext)) == "Strict2024")

    @Pytest.mark.asyncio
    async def TestExecuteEntityLookupFoundAndNotFound(self) -> None:
        MockPlatform: MockLibrary.MagicMock            = MockLibrary.MagicMock()
        MockBot     : MockLibrary.MagicMock            = MockLibrary.MagicMock()
        MockBot.PlatformClient                         = MockPlatform
        CogInstance : LookupCommands.LookupCommands    = LookupCommands.LookupCommands(MockBot, PlatformClientInstance = MockPlatform)

        SingleRecord : dict[str, Typing.Any]   = dict(name = "Fireball", source = "XPHB", Versions = [dict(name = "Fireball", source = "XPHB")])
        FetchFound   : MockLibrary.AsyncMock   = MockLibrary.AsyncMock(return_value = SingleRecord)
        MockEmbed    : Discord.Embed           = Discord.Embed(title = "Fireball")
        FormatMock   : MockLibrary.MagicMock   = MockLibrary.MagicMock(return_value = MockEmbed)
        FoundContext : MockLibrary.MagicMock   = BuildMockContext()
        await CogInstance.ExecuteEntityLookup(FoundContext, "Fireball", "Spells", FetchFound, FormatMock, "spell")
        FoundContext.send.assert_awaited_once_with(embed = MockEmbed)

        MultiRecord  : dict[str, Typing.Any]   = dict(name = "Fireball", source = "XPHB", Versions = [dict(name = "Fireball", source = "XPHB"), dict(name = "Fireball", source = "PHB")])
        FetchMulti   : MockLibrary.AsyncMock   = MockLibrary.AsyncMock(return_value = MultiRecord)
        MultiContext : MockLibrary.MagicMock   = BuildMockContext()
        await CogInstance.ExecuteEntityLookup(MultiContext, "Fireball", "Spells", FetchMulti, FormatMock, "spell")
        MultiKwargs  : dict[str, Typing.Any]   = MultiContext.send.call_args.kwargs
        assert isinstance(MultiKwargs["embed"], Discord.Embed)
        assert isinstance(MultiKwargs["view"], VersionView.VersionView)

        FetchMissing : MockLibrary.AsyncMock   = MockLibrary.AsyncMock(return_value = None)
        MockPlatform.SearchCompendium          = MockLibrary.AsyncMock(return_value = dict(Results = dict(Spells = [dict(name = "Fireball")])))
        MissContext  : MockLibrary.MagicMock   = BuildMockContext()
        await CogInstance.ExecuteEntityLookup(MissContext, "Firebal", "Spells", FetchMissing, FormatMock, "spell")
        SentEmbed    : Discord.Embed           = MissContext.send.call_args.kwargs["embed"]
        assert ("Spell Not Found" in str(SentEmbed.title))
        assert ("Fireball" in str(SentEmbed.description))

    @Pytest.mark.asyncio
    async def TestLookupCommandUnifiedSearch(self) -> None:
        MockPlatform: MockLibrary.MagicMock            = MockLibrary.MagicMock()
        MockBot     : MockLibrary.MagicMock            = MockLibrary.MagicMock()
        MockBot.PlatformClient                         = MockPlatform
        CogInstance : LookupCommands.LookupCommands    = LookupCommands.LookupCommands(MockBot, PlatformClientInstance = MockPlatform)

        MockPlatform.SearchCompendium = MockLibrary.AsyncMock(return_value = dict(Results = dict(Spells = [dict(name = "Shield", source = "XPHB", AvailableSources = ["XPHB", "PHB"])])))
        SearchContext: MockLibrary.MagicMock = BuildMockContext()
        await CogInstance.LookupCommand.callback(CogInstance, SearchContext, SearchQuery = "Shield")
        SearchKwargs : dict[str, Typing.Any] = SearchContext.send.call_args.kwargs
        assert isinstance(SearchKwargs["embed"], Discord.Embed)
        assert isinstance(SearchKwargs["view"], VersionView.CompendiumUnifiedPickerView)

        MockPlatform.SearchCompendium = MockLibrary.AsyncMock(return_value = dict(Results = dict()))
        EmptyContext : MockLibrary.MagicMock = BuildMockContext()
        await CogInstance.LookupCommand.callback(CogInstance, EmptyContext, SearchQuery = "NonexistentSpell")
        EmptyEmbed   : Discord.Embed         = EmptyContext.send.call_args.kwargs["embed"]
        assert ("No Results Found" in str(EmptyEmbed.title))
