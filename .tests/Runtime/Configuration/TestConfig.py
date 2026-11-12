import pydantic                     as Pydantic
import pytest                       as Pytest
import Runtime.Configuration.Config as Config

class TestConfiguration:
    def TestGlobalSettingsLoaded(self) -> None:
        assert (Config.GLOBAL_SETTINGS is not None)
        assert (len(Config.GLOBAL_SETTINGS.ENVIRONMENT) > 0)
        assert (len(Config.GLOBAL_SETTINGS.SECRET_KEY) > 0)
        assert (len(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E) > 0)
        assert (len(Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E) > 0)

    def TestCommandPrefixProperties(self) -> None:
        assert (Config.GLOBAL_SETTINGS.COMMAND_PREFIX_DND5E == "!")
        assert (Config.GLOBAL_SETTINGS.COMMAND_PREFIX_MGT2E == ".")

    def TestSettingsValidationSuccess(self) -> None:
        CustomSettings: Config.Settings = Config.Settings(ENVIRONMENT = "test", SECRET_KEY = "SuperSecretKeyForTesting12345", LOG_LEVEL = "INFO", DISCORD_BOT_TOKEN = "TestDiscordBotTokenString98765", DISCORD_CLIENT_ID = "987654321098765432", DISCORD_GUILD_ID = "123456789012345678", PLATFORM_API_URL = "http://127.0.0.1:9000", COMMAND_PREFIX_DND5E = "!", COMMAND_PREFIX_MGT2E = ".")
        assert (CustomSettings.ENVIRONMENT == "test")
        assert (CustomSettings.PLATFORM_SUPER_USER == "Macro Master")

    def TestSettingsMissingRequiredFieldRaisesValidationError(self) -> None:
        with Pytest.raises(Pydantic.ValidationError):
            Config.Settings(ENVIRONMENT = "", SECRET_KEY = "", LOG_LEVEL = "", DISCORD_BOT_TOKEN = "", DISCORD_CLIENT_ID = "", DISCORD_GUILD_ID = "")
