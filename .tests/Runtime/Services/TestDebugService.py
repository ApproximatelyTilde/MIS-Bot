import logging                       as Logging
import unittest.mock                 as MockLibrary
import Runtime.Configuration.Config  as Config
import Runtime.Services.DebugService as Debug

class TestDebugService:
    def TestLogLevelEnumValues(self) -> None:
        assert (Debug.LogLevel.Debug.value == Logging.DEBUG)
        assert (Debug.LogLevel.Info.value == Logging.INFO)
        assert (Debug.LogLevel.Warning.value == Logging.WARNING)
        assert (Debug.LogLevel.Error.value == Logging.ERROR)
        assert (Debug.LogLevel.Critical.value == Logging.CRITICAL)

    def TestEnvironmentLogFilterDevelopment(self) -> None:
        LogFilter  : Debug.EnvironmentLogFilter = Debug.EnvironmentLogFilter()
        DebugRecord: Logging.LogRecord          = Logging.LogRecord("Tally", Logging.DEBUG, "path", 1, "test debug", (), None)
        InfoRecord : Logging.LogRecord          = Logging.LogRecord("Tally", Logging.INFO, "path", 1, "test info", (), None)

        OriginalEnvironment: str                  = Config.GLOBAL_SETTINGS.ENVIRONMENT
        try:
            Config.GLOBAL_SETTINGS.ENVIRONMENT    = "development"
            assert (LogFilter.filter(DebugRecord) is True)
            assert (LogFilter.filter(InfoRecord) is True)

            Config.GLOBAL_SETTINGS.ENVIRONMENT    = "production"
            assert (LogFilter.filter(DebugRecord) is False)
            assert (LogFilter.filter(InfoRecord) is True)

        finally:
            Config.GLOBAL_SETTINGS.ENVIRONMENT    = OriginalEnvironment

    def TestDebugLogFormatterOutputAndTruncation(self) -> None:
        FormatterInstance: Debug.DebugLogFormatter = Debug.DebugLogFormatter()
        Record           : Logging.LogRecord       = Logging.LogRecord("Tally", Logging.INFO, "path", 1, "Short message", (), None)
        Record.created                             = 1700000000.0
        Record.DisplayTag                          = "TagCustom"

        FormattedText: str = FormatterInstance.format(Record)
        assert ("INFO" in FormattedText)
        assert ("@TagCustom" in FormattedText)
        assert ("Short message" in FormattedText)

    def TestDebugLogFormatterLongTagTruncation(self) -> None:
        FormatterInstance: Debug.DebugLogFormatter = Debug.DebugLogFormatter()
        Record           : Logging.LogRecord       = Logging.LogRecord("Tally", Logging.INFO, "path", 1, "Message", (), None)
        Record.created                             = 1700000000.0
        Record.DisplayTag                          = "VeryLongFunctionNameThatExceedsLimit"

        FormattedText: str = FormatterInstance.format(Record)
        assert ("…" in FormattedText)

    def TestLogMessageExecution(self) -> None:
        with MockLibrary.patch.object(Debug.SYSTEM_LOGGER, "log") as MockLog:
            Debug.LogMessage(Level = Debug.LogLevel.Info, Message = "Test Log Event", Tag = "TestUnit")
            assert (MockLog.call_count == 1)
            CallArgs, CallKwargs = MockLog.call_args
            assert (CallArgs[0] == Logging.INFO)
            assert (CallArgs[1] == "Test Log Event")
            assert (CallKwargs["extra"]["DisplayTag"] == "TestUnit")
