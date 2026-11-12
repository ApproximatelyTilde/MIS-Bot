import os  as OperatingSystem
import sys as System

WORKSPACE_ROOT: str = OperatingSystem.path.abspath(OperatingSystem.path.join(OperatingSystem.path.dirname(__file__), ".."))
if (WORKSPACE_ROOT not in System.path):
    System.path.insert(0, WORKSPACE_ROOT)

DEFAULT_TEST_ENVIRONMENT_VARIABLES: dict[str, str] = {
    "ENVIRONMENT"         : "development",
    "SECRET_KEY"          : "TestSecretKeyForTestingPurpose12345",
    "LOG_LEVEL"           : "DEBUG",
    "DISCORD_BOT_TOKEN"   : "TestingDiscordBotTokenValue1234567890",
    "DISCORD_CLIENT_ID"   : "123456789012345678",
    "DISCORD_GUILD_ID"    : "123456789012345678",
    "PLATFORM_API_URL"    : "http://127.0.0.1:8000",
    "PLATFORM_SUPER_USER" : "Macro Master",
    "COMMAND_PREFIX_DND5E": "!",
    "COMMAND_PREFIX_MGT2E": "."
}

for EnvironmentKey, EnvironmentValue in DEFAULT_TEST_ENVIRONMENT_VARIABLES.items():
    if (EnvironmentKey not in OperatingSystem.environ):
        OperatingSystem.environ[EnvironmentKey] = EnvironmentValue


