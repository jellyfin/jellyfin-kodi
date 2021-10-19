# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import threading

from kodi_six import xbmc

from jellyfin_kodi.entrypoint.service import Service
from jellyfin_kodi.helper.utils import settings
from jellyfin_kodi.helper import LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)
DELAY = int(settings('startupDelay') if settings('SyncInstallRunDone.bool') else 4)

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
                # TODO: fix this properly as to not match on str()
                if 'ExitService' not in str(error):
                    service.shutdown()

                if 'RestartService' in str(error):
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

            if 'RestartService' in str(session.exception):
                continue

        except Exception as error:
            ''' Issue initializing the service.
            '''
            LOG.exception(error)

        break

    LOG.info("--<[ service ]")
