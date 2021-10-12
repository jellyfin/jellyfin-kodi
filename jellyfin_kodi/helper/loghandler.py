# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

import os
import logging
import traceback

from six import ensure_text
from kodi_six import xbmc, xbmcaddon

from .. import database
from . import get_filesystem_encoding, settings, kodi_version
from .utils import translate_path

##################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.jellyfin')
__pluginpath__ = translate_path(__addon__.getAddonInfo('path'))

##################################################################################################


def getLogger(name=None):
    if name is None:
        return __LOGGER

    return __LOGGER.getChild(name)


class LogHandler(logging.StreamHandler):

    def __init__(self):

        logging.StreamHandler.__init__(self)
        self.setFormatter(MyFormatter())

        self.sensitive = {'Token': [], 'Server': []}

        for server in database.get_credentials()['Servers']:

            if server.get('AccessToken'):
                self.sensitive['Token'].append(server['AccessToken'])

            if server.get('address'):
                self.sensitive['Server'].append(server['address'].split('://')[1])

        self.mask_info = settings('maskInfo.bool')

        if kodi_version() > 18:
            self.level = xbmc.LOGINFO
        else:
            self.level = xbmc.LOGNOTICE

    def emit(self, record):

        if self._get_log_level(record.levelno):
            string = self.format(record)

            if self.mask_info:
                for server in self.sensitive['Server']:
                    string = string.replace(server or "{server}", "{jellyfin-server}")

                for token in self.sensitive['Token']:
                    string = string.replace(token or "{token}", "{jellyfin-token}")

            xbmc.log(string, level=self.level)

    @classmethod
    def _get_log_level(cls, level):

        levels = {
            logging.ERROR: 0,
            logging.WARNING: 0,
            logging.INFO: 1,
            logging.DEBUG: 2
        }
        try:
            log_level = int(settings('logLevel'))
        except ValueError:
            log_level = 2  # If getting settings fail, we probably want debug logging.

        return log_level >= levels[level]


class MyFormatter(logging.Formatter):

    def __init__(self, fmt='%(name)s -> %(levelname)s::%(relpath)s:%(lineno)s %(message)s'):
        logging.Formatter.__init__(self, fmt)

    def format(self, record):
        if record.pathname:
            record.pathname = ensure_text(record.pathname, get_filesystem_encoding())

        self._gen_rel_path(record)

        # Call the original formatter class to do the grunt work
        result = logging.Formatter.format(self, record)

        return result

    def formatException(self, exc_info):
        _pluginpath_real = os.path.realpath(__pluginpath__)
        res = []

        for o in traceback.format_exception(*exc_info):
            o = ensure_text(o, get_filesystem_encoding())

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


__LOGGER = logging.getLogger('JELLYFIN')
for handler in __LOGGER.handlers:
    __LOGGER.removeHandler(handler)

__LOGGER.addHandler(LogHandler())
__LOGGER.setLevel(logging.DEBUG)
