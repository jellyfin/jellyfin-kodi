# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sys

from helper import loghandler
from emby import Emby

#################################################################################################

Emby.set_loghandler(loghandler.LogHandler, logging.DEBUG)
loghandler.config()
LOG = logging.getLogger('EMBY.entrypoint')

#################################################################################################

try:
    sys.path.insert(0, xbmc.translatePath('special://temp/emby/').decode('utf-8'))
except Exception as error:
    LOG.debug('No objects not found, using default.')

from default import Events
from service import Service
from context import Context
