import unittest.mock                         as MockLibrary
import pytest                                as Pytest
import discord                               as Discord
import discord.ext.commands                  as Commands
import Runtime.Decorators.RateLimitDecorator as RateLimitDecorator
import Runtime.Services.RateLimitService     as RateLimit

class TestRateLimitDecorator:
    def TestRateLimitExceededExceptionProperties(self) -> None:
        ExceptionInstance: RateLimitDecorator.RateLimitExceeded = RateLimitDecorator.RateLimitExceeded(WaitSeconds = 4.25, Category = "Scripting")
        assert (ExceptionInstance.WaitSeconds == 4.25)
        assert (ExceptionInstance.Category == "Scripting")
        assert ("4.2s" in str(ExceptionInstance))

    def TestBuildRateLimitCooldownEmbed(self) -> None:
        CooldownEmbed: Discord.Embed = RateLimitDecorator.BuildRateLimitCooldownEmbed(WaitSeconds = 3.5, Category = "Standard")
        assert (CooldownEmbed.title == "Rate Limit Reached")
        assert ("3.5s" in str(CooldownEmbed.description))
        assert ("standard" in str(CooldownEmbed.description).lower())
        assert ((CooldownEmbed.color is not None) and (CooldownEmbed.color.value == RateLimitDecorator.COLOR_RATE_LIMIT_EMBED))

    @Pytest.mark.asyncio
    async def TestRateLimitPredicateAllowsAdmin(self) -> None:
        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = None

        CheckDecoratorInstance: object = RateLimitDecorator.RateLimit(Category = "Standard")
        PredicateFunction     : object = CheckDecoratorInstance.predicate

        ResultValue: bool = await PredicateFunction(MockContext)
        assert (ResultValue is True)

    @Pytest.mark.asyncio
    async def TestRateLimitPredicateAllowsWhenServiceAbsent(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 111111111
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = []

        MockBot             : MockLibrary.MagicMock = MockLibrary.MagicMock(spec = Commands.Bot)
        del MockBot.RateLimitService

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor
        MockContext.bot                             = MockBot

        CheckDecoratorInstance: object = RateLimitDecorator.RateLimit(Category = "Standard")
        PredicateFunction     : object = CheckDecoratorInstance.predicate

        ResultValue: bool = await PredicateFunction(MockContext)
        assert (ResultValue is True)

    @Pytest.mark.asyncio
    async def TestRateLimitPredicateConsumesAndRaisesOnExceeded(self) -> None:
        MockGuild           : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.owner_id                          = 999999999

        MockPermissions     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockPermissions.administrator               = False
        MockPermissions.manage_guild                = False

        MockAuthor          : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockAuthor.id                               = 222333444
        MockAuthor.guild_permissions                = MockPermissions
        MockAuthor.roles                            = []

        MockService         : RateLimit.RateLimitService = RateLimit.RateLimitService()
        MockBot             : MockLibrary.MagicMock      = MockLibrary.MagicMock()
        MockBot.RateLimitService                         = MockService

        MockContext         : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockContext.guild                           = MockGuild
        MockContext.author                          = MockAuthor
        MockContext.bot                             = MockBot

        CheckDecoratorInstance: object = RateLimitDecorator.RateLimit(Category = "Standard")
        PredicateFunction     : object = CheckDecoratorInstance.predicate

        for _ in range(5):
            ResultValue: bool = await PredicateFunction(MockContext)
            assert (ResultValue is True)

        with Pytest.raises(RateLimitDecorator.RateLimitExceeded) as ExceededError:
            await PredicateFunction(MockContext)

        assert (ExceededError.value.WaitSeconds > 0)
