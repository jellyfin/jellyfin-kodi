# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function

##################################################################################################

import os
import logging
import traceback

import xbmc
import xbmcaddon
import database

from . import window, settings

##################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.jellyfin')
__pluginpath__ = xbmc.translatePath(__addon__.getAddonInfo('path').decode('utf-8'))

##################################################################################################


def config():

    logger = logging.getLogger('JELLYFIN')
    logger.addHandler(LogHandler())
    logger.setLevel(logging.DEBUG)


def reset():

    for handler in logging.getLogger('JELLYFIN').handlers:
        logging.getLogger('JELLYFIN').removeHandler(handler)


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

            if server.get('ManualAddress'):
                self.sensitive['Server'].append(server['ManualAddress'].split('://')[1])

        self.mask_info = settings('maskInfo.bool')

    def emit(self, record):

        if self._get_log_level(record.levelno):
            string = self.format(record)

            if self.mask_info:
                for server in self.sensitive['Server']:
                    string = string.replace(server.encode('utf-8') or "{server}", "{jellyfin-server}")

                for token in self.sensitive['Token']:
                    string = string.replace(token.encode('utf-8') or "{token}", "{jellyfin-token}")

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
            log_level = int(window('jellyfin_logLevel'))
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

        self._gen_rel_path(record)

        # Replace the original format with one customized by logging level
        self._fmt = '%(name)s -> %(levelname)s::%(relpath)s:%(lineno)s %(message)s'

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        # Restore the original format configured by the user
        self._fmt = format_orig

        return result

    def formatException(self, exc_info):
        _pluginpath_real = os.path.realpath(__pluginpath__)
        res = []

        for o in traceback.format_exception(*exc_info):
            if o.startswith('  File "'):
                # If this split can't handle your file names, you should seriously consider renaming your files.
                fn = o.split('  File "', 2)[1].split('", line ', 1)[0]
                rfn = os.path.realpath(fn)
                if rfn.startswith(_pluginpath_real):
                    o = o.replace(fn, os.path.relpath(rfn, _pluginpath_real))

            res.append(o)

        return ''.join(res)

    def _gen_rel_path(self, record):
        if record.pathname:
            record.relpath = os.path.relpath(record.pathname, __pluginpath__)
