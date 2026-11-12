import pydantic          as Pydantic
import pydantic_settings as PydanticSettings

class Settings(PydanticSettings.BaseSettings):
    ENVIRONMENT             : str = Pydantic.Field(..., min_length = 1)
    SECRET_KEY              : str = Pydantic.Field(..., min_length = 1)
    LOG_LEVEL               : str = Pydantic.Field(..., min_length = 1)
    DISCORD_BOT_TOKEN       : str = Pydantic.Field(..., min_length = 1)
    DISCORD_CLIENT_ID       : str = Pydantic.Field(..., min_length = 1)
    DISCORD_GUILD_ID        : str = Pydantic.Field(..., min_length = 1)
    PLATFORM_API_URL        : str = Pydantic.Field(..., min_length = 1)
    COMMAND_PREFIX_DND      : str = Pydantic.Field(..., min_length = 1)
    COMMAND_PREFIX_TRAVELLER: str = Pydantic.Field(..., min_length = 1)
    model_config                  = PydanticSettings.SettingsConfigDict(env_file = ".env", env_file_encoding = "utf-8", extra = "ignore")

GLOBAL_SETTINGS: Settings = Settings()

