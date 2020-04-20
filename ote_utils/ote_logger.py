from builtins import object
import logging


class OteLogger(object):
    """Logging class for the ote classes

    INITIALIZATION
    --------------
    Create a new logging instance by passing a unique name during initialization.
    The name can be any string, however it is recommened you pass __name__ so each logging
    message will contain the classname the log came from, making it easier to debug.

    LOGGING HANDLERS
    ----------------
    By defaul all logging will go to the console (screen).
    Optionally you can enable logging to a file, as well as disable the console logging.

    LOG LEVELS
    ----------
    Each instance can log at its own level. The level is set to the global level upon
    initialization, (default: INFO), but can be overridden.
    Setting the global level will make all current logger instances log at the new level.
    All new instances will also log at this level unless overridden.
    Valid log levles are DEBUG, INFO, WARNING, ERROR and CRITICAL and are directly used
    from the logging class.
    """

    LOGGERS = []
    GLOBAL_LEVEL = logging.INFO

    @staticmethod
    def set_global_loglevel(level):
        """Set the log level for all current instances of the logging class.
        This level will also be the new default level for new instances as well.

        Args:
            level: (string) 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
        """
        if hasattr(logging, level.upper()):
            OteLogger.GLOBAL_LEVEL = level

            for logger in OteLogger.LOGGERS:
                logger.info("Global loglevel set to {}".format(level))
                logger.set_loglevel(level)

    def __init__(self, name, level=None, console=True, filename=None, file_mode="overwrite"):
        """Initialize a new logger instance
        Args:
            name: name of the logger to initialize. Generally pass it __name__
            level: (optional) log level to set for this instance
                   (default) the global level
            console: (default: True) print message to the console (screen)
            filename: (default: None) if a filename is given all messages will
                      be logged to the filename given.
            file_mode: (default: overwrite)  ['append','overwrite']
                       If no file exists, one is created.
                       If 'append', the existing file is appended to.
                       If 'overwrite', a new file is created each time.
        """

        self.logger = logging.getLogger(name)

        if level is not None and hasattr(logging, level.upper()):
            self.loglevel = getattr(logging, level.upper())
        else:
            self.loglevel = OteLogger.GLOBAL_LEVEL

        self.logger.setLevel(self.loglevel)
        self.formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        if console is True:
            self.enable_logging_to_console()
        if filename is not None:
            self.enable_logging_to_file(filename, file_mode)
        OteLogger.LOGGERS.append(self)

    def enable_logging_to_console(self):
        """Enable logging to the conole (screen)
        """
        handler = logging.StreamHandler()
        handler.setFormatter(self.formatter)
        self.logger.addHandler(handler)
        self.debug("Logging to console enabled")

    def enable_logging_to_file(self, filename=None, file_mode="overwrite"):
        """Enable logging to a file
        Args:
            filename: (default: None) if a filename is given all messages will
                      be logged to the filename given.
            file_mode: (default: overwrite)  ['append','overwrite']
                       If no file exists, one is created.
                       If 'append', the existing file is appended to.
                       If 'overwrite', a new file is created each time.
        """
        if filename is not None:
            mode = "w"
            if file_mode.lower() == "append":
                mode = "a"
            handler = logging.FileHandler(filename, mode=mode)
            handler.setFormatter(self.formatter)
            self.logger.addHandler(handler)
            self.debug("Logging to file '{}' enabled".format(filename))

    def set_loglevel(self, level):
        """Set the log level for for this instance
        Args:
            level: The logging level to set.
                   Possible values are DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        if level is not None and hasattr(logging, level.upper()):
            logging_level = getattr(logging, level.upper())
            self.loglevel = logging_level
            self.logger.setLevel(self.loglevel)
            self.debug("Logging level set to {}".format(level))
        else:
            self.logger.info("set_loglevel: Invalid loglevel: {}".format(level))

    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
