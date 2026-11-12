import asyncio                       as AsyncIO
import Runtime.Configuration.Config  as Config
import Runtime.Services.DebugService as Debug
import Runtime.Application.BotClient as BotClient

async def StartApplication() -> None:
    Debug.LogMessage(Level = Debug.LogLevel.Info, Message = f"Starting Tally Application Service: Environment={Config.GLOBAL_SETTINGS.ENVIRONMENT}")
    ClientInstance: BotClient.TallyBotClient = BotClient.TallyBotClient()
    async with ClientInstance:
        await ClientInstance.start(Config.GLOBAL_SETTINGS.DISCORD_BOT_TOKEN)

if (__name__ == "__main__"):
    AsyncIO.run(StartApplication())

