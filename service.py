# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys

import xbmc
import xbmcvfs
import xbmcaddon

#################################################################################################

cache = xbmc.translatePath('special://temp/emby').decode('utf-8')

if not xbmcvfs.exists(cache):
    xbmcvfs.mkdir(cache)

sys.path.insert(0, cache)
__addon__ = xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('path').decode('utf-8')
__base__ = xbmc.translatePath(os.path.join(__addon__, 'resources', 'lib')).decode('utf-8')
sys.path.append(__base__)

#################################################################################################

from entrypoint import Service
from helper import settings
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY.service")
DELAY = int(settings('startupDelay') or 0)

#################################################################################################


if __name__ == "__main__":

    LOG.warn("-->[ service ]")
    LOG.warn("Delay startup by %s seconds.", DELAY)

    try:
        session = Service()

        try:
            if DELAY and xbmc.Monitor().waitForAbort(DELAY):
                raise Exception("Aborted during startup delay")

            session.service()
        except Exception as error: # TODO, build exceptions
            LOG.exception(error)
            session.shutdown()

    except Exception as error:
        ''' Issue initializing the service.
        '''
        LOG.exception(error)

    LOG.warn("--<[ service ]")
