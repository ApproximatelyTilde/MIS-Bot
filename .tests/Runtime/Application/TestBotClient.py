import unittest.mock                 as MockLibrary
import discord.ext.commands          as Commands
import Runtime.Application.BotClient as BotClient
import Runtime.Configuration.Config  as Config

async def ExecuteSampleRollCommand(Context: Commands.Context) -> None:
    pass

async def ExecuteSampleCastCommand(Context: Commands.Context) -> None:
    pass

class TestBotClient:
    def TestGetDynamicPrefixesWithServerSettings(self) -> None:
        MockBot         : MockLibrary.MagicMock = MockLibrary.MagicMock(spec = Commands.Bot)
        MockSettings    : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockBot.ServerSettingsService           = MockSettings
        MockSettings.GetCachedDND5EPrefix.return_value = "!dnd"
        MockSettings.GetCachedMGT2EPrefix.return_value = ".mgt"

        MockGuild       : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockGuild.id                            = 999111
        MockMessage     : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockMessage.guild                       = MockGuild

        with MockLibrary.patch.object(Commands, "when_mentioned", return_value = ["<@!123456> "]):
            PrefixesList: list[str] = BotClient.GetDynamicPrefixes(MockBot, MockMessage)
            assert ("!dnd" in PrefixesList)
            assert (".mgt" in PrefixesList)
            assert ("<@!123456> " in PrefixesList)

    def TestGetDynamicPrefixesWithoutServerSettings(self) -> None:
        MockBot     : MockLibrary.MagicMock = MockLibrary.MagicMock(spec = Commands.Bot)
        del MockBot.ServerSettingsService

        MockMessage : MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockMessage.guild                   = None

        with MockLibrary.patch.object(Commands, "when_mentioned", return_value = []):
            PrefixesList: list[str] = BotClient.GetDynamicPrefixes(MockBot, MockMessage)
            assert (Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E in PrefixesList)
            assert (Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E in PrefixesList)

    def TestAddAndRemoveCommandPrefixPartitioning(self) -> None:
        ClientInstance: BotClient.TallyBotClient = BotClient.TallyBotClient()

        MockCogMGT2E: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockCogMGT2E.__module__             = "Runtime.Application.Commands.MGT2E.DiceCommands"

        MockCommandMGT2E: Commands.Command  = Commands.Command(ExecuteSampleRollCommand, name = "roll", aliases = ["r"])
        MockCommandMGT2E.cog                = MockCogMGT2E

        MockCogDND5E: MockLibrary.MagicMock = MockLibrary.MagicMock()
        MockCogDND5E.__module__             = "Runtime.Application.Commands.DND5E.DiceCommands"

        MockCommandDND5E: Commands.Command  = Commands.Command(ExecuteSampleCastCommand, name = "cast", aliases = ["c"])
        MockCommandDND5E.cog                = MockCogDND5E

        ClientInstance.add_command(MockCommandMGT2E)
        ClientInstance.add_command(MockCommandDND5E)

        assert ("roll" in ClientInstance.MGT2ECommands)
        assert ("r" in ClientInstance.MGT2ECommands)
        assert ("roll" not in ClientInstance.DND5ECommands)

        assert ("cast" in ClientInstance.DND5ECommands)
        assert ("c" in ClientInstance.DND5ECommands)
        assert ("cast" not in ClientInstance.MGT2ECommands)

        ClientInstance.remove_command("roll")
        assert ("roll" not in ClientInstance.MGT2ECommands)
        assert ("cast" in ClientInstance.DND5ECommands)
