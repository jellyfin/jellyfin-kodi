# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcvfs

from helper import loghandler
from emby import Emby

#################################################################################################

Emby.set_loghandler(loghandler.LogHandler, logging.DEBUG)
loghandler.config()
LOG = logging.getLogger('EMBY.entrypoint')

#################################################################################################

from default import Events
from service import Service
from context import Context
