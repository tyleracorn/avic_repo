import logging
from pathlib import Path


class ClassWithLogger:
    def __init__(self, name, log_file=False, logger=None, level=logging.INFO):
        """class for initializing a subclass with a logger

        Parameters
        ----------
        name : str
            name of the class
        log_file : str
            path to the log file
        logger : logger
            external logging object if initializing from another class
        level : int
            logging level
        """
        self._name = name
        self._log_level = level
        if logger is None or logger is False:
            pass
        else:
            self._set_external_logger(logger)
        if log_file is False or log_file is None:
            self.log_file = False
        else:
            if logger is False or logger is None:
                self.log_file = Path(log_file)
                self._set_logger(Path(log_file))
            else:
                self.log_file = False

        if log_file is False and logger is False:
            print(f"No logger set for {self._name}")
            self.logger = False

    def _set_logger(self, log_file):
        """Set the logger"""
        print(f"Setting logger for {self._name}")
        self.logger = logging.getLogger(self._name)
        self.logger.info(f"Logger set for {self._name}")
        self.logger.setLevel(self._log_level)
        self._add_log_handler(log_file)

    def _set_external_logger(self, logger):
        """Set an external logger"""
        self.logger = logger

    def _add_log_handler(self, log_file):
        """Add the log file handler to the logger"""
        # setup a file logger format so that it formats the messages to include log level,
        # class name, function name, and function arguments
        self.logger.info(f"Adding log handler for {log_file}")
        formatter = logging.Formatter('%(levelname)s: %(name)s: %(funcName)s: %(message)s')

        self._remove_log_handler(log_file)
        fh = logging.FileHandler(log_file, encoding='utf-8')
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def _remove_log_handler(self, log_file):
        """Remove the log file handler from the logger"""
        if log_file.is_file():
            self.logger.info(f"Removing log handler for {log_file}")
            handlers = self.logger.handlers[:]
            for handler in handlers:
                if str(log_file) in handler.baseFilename:
                    handler.close()
                    self.logger.removeHandler(handler)

    def close_logger(self):
        """Close all handlers in the logger"""
        self.logger.info("Closing logger")
        handlers = self.logger.handlers[:]
        for handler in handlers:
            handler.close()
            self.logger.removeHandler(handler)

    def log_info(self, message):
        """Log an info message"""
        if self.logger is not False:
            self.logger.info(message)

    def log_warning(self, message):
        """Log a warning message"""
        if self.logger is not False:
            self.logger.warning(message)

    def log_error(self, message):
        """Log an error message"""
        if self.logger is not False:
            self.logger.error(message)
