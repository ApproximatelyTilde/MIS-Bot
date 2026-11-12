import datetime             as DateTime
import enum                 as Enumeration
import inspect              as Inspect
import logging              as Logging
import sys                  as System
import typing               as Typing
import Configuration.Config as Config

MAXIMUM_LINE_WIDTH: int = 120

ANSI_COLOR_RESET: str = "\033[0m"
ANSI_STYLE_BOLD : str = "\033[1m"

LOG_LEVEL_ANSI_COLORS: dict[int, str] = {
    Logging.DEBUG   : "\033[36m",
    Logging.INFO    : "\033[32m",
    Logging.WARNING : "\033[33m",
    Logging.ERROR   : "\033[31m",
    Logging.CRITICAL: "\033[1;31m"
}

class LogLevel(int, Enumeration.Enum):
    Debug    = Logging.DEBUG
    Info     = Logging.INFO
    Warning  = Logging.WARNING
    Error    = Logging.ERROR
    Critical = Logging.CRITICAL

class EnvironmentLogFilter(Logging.Filter):
    def filter(self, Record: Logging.LogRecord) -> bool:
        if (Record.levelno == Logging.DEBUG) and (Config.GLOBAL_SETTINGS.ENVIRONMENT.lower() != "development"):
            return False

        return True

class DebugLogFormatter(Logging.Formatter):
    def format(self, Record: Logging.LogRecord) -> str:
        CurrentTime  : str = DateTime.datetime.fromtimestamp(Record.created).strftime("%Y%m%d - %H%M")
        DisplayTag   : str = getattr(Record, "DisplayTag", Record.funcName)
        if (len(DisplayTag) > 20):
            DisplayTag = DisplayTag[:19] + "…"

        ColonPadding : str = ":".ljust(10 - len(Record.levelname))
        LevelColor   : str = LOG_LEVEL_ANSI_COLORS.get(Record.levelno, "")
        MessageText  : str = Record.getMessage()
        VisiblePrefix: str = Record.levelname + ColonPadding + CurrentTime + " - @" + DisplayTag + ": "
        if ((len(VisiblePrefix) + len(MessageText)) > MAXIMUM_LINE_WIDTH):
            AllowedLength: int = MAXIMUM_LINE_WIDTH - len(VisiblePrefix)
            MessageText        = MessageText[:AllowedLength - 1] + "…"

        OutputLine: str = LevelColor + Record.levelname + ANSI_COLOR_RESET + ColonPadding + CurrentTime + " - " + ANSI_STYLE_BOLD + "@" + DisplayTag + ANSI_COLOR_RESET + ": " + MessageText
        return OutputLine

SYSTEM_LOGGER: Logging.Logger = Logging.getLogger("MISBot")
if not SYSTEM_LOGGER.handlers:
    STREAM_HANDLER: Logging.StreamHandler = Logging.StreamHandler(stream = System.stdout)
    STREAM_HANDLER.setFormatter(DebugLogFormatter())
    STREAM_HANDLER.addFilter(EnvironmentLogFilter())
    SYSTEM_LOGGER.setLevel(Logging.DEBUG)
    SYSTEM_LOGGER.addHandler(STREAM_HANDLER)
    SYSTEM_LOGGER.propagate = False

def LogMessage(Level: LogLevel, Message: str, Tag: Typing.Optional[str] = None) -> None:
    if (Tag is not None):
        DisplayTag: str = Tag

    else:
        CallerFrame = Inspect.currentframe()
        if (CallerFrame is None):
            DisplayTag: str = "Anonymous"

        else:
            TargetFrame = CallerFrame.f_back
            while (TargetFrame is not None) and (TargetFrame.f_code.co_name == "LogMessage"):
                TargetFrame = TargetFrame.f_back

            if (TargetFrame is None):
                DisplayTag = "Anonymous"

            else:
                DisplayTag = TargetFrame.f_code.co_name
                del TargetFrame

            del CallerFrame

    SYSTEM_LOGGER.log(Level.value, Message, extra = {"DisplayTag": DisplayTag})

