# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc

import database
from . import window, settings

##################################################################################################


def config():

    logger = logging.getLogger('EMBY')
    logger.addHandler(LogHandler())
    logger.setLevel(logging.DEBUG)


class LogHandler(logging.StreamHandler):

    def __init__(self):

        logging.StreamHandler.__init__(self)
        self.setFormatter(MyFormatter())

        self.sensitive = {'Token': [], 'Server': []}

        for server in database.get_credentials()['Servers']:

            if server.get('AccessToken'):
                self.sensitive['Token'].append(server['AccessToken'])

            if server.get('LocalAddress'):
                self.sensitive['Server'].append(server['LocalAddress'].split('://')[1])

            if server.get('RemoteAddress'):
                self.sensitive['Server'].append(server['RemoteAddress'].split('://')[1])

            if server.get('ManualAddress'):
                self.sensitive['Server'].append(server['ManualAddress'].split('://')[1])

        self.mask_info = settings('maskInfo.bool')

    def emit(self, record):

        if self._get_log_level(record.levelno):
            string = self.format(record)

            if self.mask_info:
                for server in self.sensitive['Server']:
                    string = string.replace(server.encode('utf-8') or "{server}", "{emby-server}")

                for token in self.sensitive['Token']:
                    string = string.replace(token.encode('utf-8')  or "{token}", "{emby-token}")

            try:
                xbmc.log(string, level=xbmc.LOGNOTICE)
            except UnicodeEncodeError:
                xbmc.log(string.encode('utf-8'), level=xbmc.LOGNOTICE)

    @classmethod
    def _get_log_level(cls, level):

        levels = {
            logging.ERROR: 0,
            logging.WARNING: 0,
            logging.INFO: 1,
            logging.DEBUG: 2
        }
        try:
            log_level = int(window('emby_logLevel'))
        except ValueError:
            log_level = 0

        return log_level >= levels[level]


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
