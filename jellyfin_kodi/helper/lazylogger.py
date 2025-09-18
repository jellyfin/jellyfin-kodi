# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

from typing import TYPE_CHECKING


class LazyLogger(object):
    """
    `helper.loghandler.getLogger()` is used everywhere.
    This class helps to avoid import errors.
    """

    __logger = None
    __logger_name = None

    def __init__(self, logger_name=None):
        self.__logger_name = logger_name

    def __getattr__(self, name):
        if self.__logger is None:
            from .loghandler import getLogger

            self.__logger = getLogger(self.__logger_name)
        return getattr(self.__logger, name)

    #####################################################################
    # Following are stubs of methods provided by `logging.Logger`.      #
    # Please ensure any actually functional code is above this comment. #
    #####################################################################

    if TYPE_CHECKING:

        def setLevel(self, level):
            """
            Set the logging level of this logger.  level must be an int or a str.
            """
            ...

        def debug(self, msg, *args, **kwargs):
            """
            Log 'msg % args' with severity 'DEBUG'.

            To pass exception information, use the keyword argument exc_info with
            a true value, e.g.

            logger.debug("Houston, we have a %s", "thorny problem", exc_info=1)
            """
            ...

        def info(self, msg, *args, **kwargs):
            """
            Log 'msg % args' with severity 'INFO'.

            To pass exception information, use the keyword argument exc_info with
            a true value, e.g.

            logger.info("Houston, we have a %s", "interesting problem", exc_info=1)
            """
            ...

        def warning(self, msg, *args, **kwargs):
            """
            Log 'msg % args' with severity 'WARNING'.

            To pass exception information, use the keyword argument exc_info with
            a true value, e.g.

            logger.warning("Houston, we have a %s", "bit of a problem", exc_info=1)
            """
            ...

        def error(self, msg, *args, **kwargs):
            """
            Log 'msg % args' with severity 'ERROR'.

            To pass exception information, use the keyword argument exc_info with
            a true value, e.g.

            logger.error("Houston, we have a %s", "major problem", exc_info=1)
            """
            ...

        def exception(self, msg, *args, exc_info=True, **kwargs):
            """
            Convenience method for logging an ERROR with exception information.
            """
            ...

        def critical(self, msg, *args, **kwargs):
            """
            Log 'msg % args' with severity 'CRITICAL'.

            To pass exception information, use the keyword argument exc_info with
            a true value, e.g.

            logger.critical("Houston, we have a %s", "major disaster", exc_info=1)
            """
            ...

        def log(self, level, msg, *args, **kwargs):
            """
            Log 'msg % args' with the integer severity 'level'.

            To pass exception information, use the keyword argument exc_info with
            a true value, e.g.

            logger.log(level, "We have a %s", "mysterious problem", exc_info=1)
            """
            ...
