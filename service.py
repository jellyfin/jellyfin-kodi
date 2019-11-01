# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import threading
import sys

import xbmc
import xbmcaddon

#################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.jellyfin')
__base__ = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'), 'kodi_jellyfin')).decode('utf-8')

sys.path.insert(0, __base__)

#################################################################################################

from entrypoint import Service  # noqa: F402
from helper.utils import settings  # noqa: F402

#################################################################################################

LOG = logging.getLogger("JELLYFIN.service")
DELAY = int(settings('startupDelay') if settings('SyncInstallRunDone.bool') else 4 or 0)

#################################################################################################


class ServiceManager(threading.Thread):

    ''' Service thread.
        To allow to restart and reload modules internally.
    '''
    exception = None

    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        service = None

        try:
            service = Service()

            if DELAY and xbmc.Monitor().waitForAbort(DELAY):
                raise Exception("Aborted during startup delay")

            service.service()
        except Exception as error:
            LOG.exception(error)

            if service is not None:

                if 'ExitService' not in error:
                    service.shutdown()

                if 'RestartService' in error:
                    service.reload_objects()

            self.exception = error


if __name__ == "__main__":
    LOG.info("-->[ service ]")
    LOG.info("Delay startup by %s seconds.", DELAY)

    while True:
        if not settings('enableAddon.bool'):
            LOG.warning("Jellyfin for Kodi is not enabled.")

            break

        try:
            session = ServiceManager()
            session.start()
            session.join()  # Block until the thread exits.

            if 'RestartService' in session.exception:
                continue

        except Exception as error:
            ''' Issue initializing the service.
            '''
            LOG.exception(error)

        break

    LOG.info("--<[ service ]")
