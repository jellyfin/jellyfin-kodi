# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import logging

from kodi_six import xbmc, xbmcvfs

from helper import loghandler
from jellyfin import Jellyfin

from .default import Events
from .service import Service
from .context import Context

#################################################################################################

Jellyfin.set_loghandler(loghandler.LogHandler, logging.DEBUG)
loghandler.reset()
loghandler.config()
LOG = logging.getLogger('JELLYFIN.entrypoint')

#################################################################################################
