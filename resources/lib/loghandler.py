# -*- coding: utf-8 -*-

##################################################################################################

import logging
import xbmc

from utils import window

##################################################################################################


def config():
    
    logger = logging.getLogger('EMBY')
    logger.addHandler(LogHandler())
    logger.setLevel(logging.DEBUG)


class LogHandler(logging.StreamHandler):

    def __init__(self):
        
        logging.StreamHandler.__init__(self)
        self.setFormatter(MyFormatter())

    def emit(self, record):

        if self._getLogLevel(record.levelno):
            try:
                xbmc.log(self.format(record))
            except UnicodeEncodeError:
                xbmc.log(self.format(record).encode('utf-8'))

    def _getLogLevel(self, level):

        levels = {
            logging.ERROR: 0,
            logging.WARNING: 0,
            logging.INFO: 1,
            logging.DEBUG: 2,
        }
        try:
            logLevel = int(window('emby_logLevel'))
        except ValueError:
            logLevel = 0

        return logLevel >= levels[level]


class MyFormatter(logging.Formatter):

    def __init__(self, fmt="%(name)s -> %(message)s"):
        
        logging.Formatter.__init__(self, fmt)

    def format(self, record):

        # Save the original format configured by the user
        # when the logger formatter was instantiated
        format_orig = self._fmt

        # Replace the original format with one customized by logging level
        if record.levelno in (logging.DEBUG, logging.ERROR):
            self._fmt = '%(name)s -> %(levelname)s:: %(message)s'

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._fmt = format_orig

        return result