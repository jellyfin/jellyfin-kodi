# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcvfs

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
