import asyncio               as AsyncIO
import Configuration.Config  as Config
import Services.DebugService as Debug
import Application.BotClient as BotClient

async def StartApplication() -> None:
    Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Starting MIS-Bot Application Service: Environment={Config.GLOBAL_SETTINGS.ENVIRONMENT}")
    ClientInstance: BotClient.MISBotClient = BotClient.MISBotClient()
    async with ClientInstance:
        await ClientInstance.start(Config.GLOBAL_SETTINGS.DISCORD_BOT_TOKEN)

if (__name__ == "__main__"):
    AsyncIO.run(StartApplication())

