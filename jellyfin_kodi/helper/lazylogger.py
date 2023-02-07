# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals


class LazyLogger(object):
    """`helper.loghandler.getLogger()` is used everywhere.
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
