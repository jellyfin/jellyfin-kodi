# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sys

import xbmc
import xbmcvfs

import objects
from helper import loghandler
from emby import Emby

#################################################################################################

Emby.set_loghandler(loghandler.LogHandler, logging.DEBUG)
loghandler.config()
LOG = logging.getLogger('EMBY.entrypoint')

#################################################################################################

try:
    temp = xbmc.translatePath('special://temp/emby').decode('utf-8')

    if not xbmcvfs.exists(temp):
        xbmcvfs.mkdir(temp)

    sys.path.insert(0, temp)
    reload(objects)
except Exception as error:

    LOG.error(error)
    LOG.warn('No objects not found, using default.')

from default import Events
from service import Service
from context import Context
