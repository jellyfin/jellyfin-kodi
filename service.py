# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import threading
import sys

import xbmc
import xbmcvfs
import xbmcaddon

#################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.emby')
__base__ = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'), 'resources', 'lib')).decode('utf-8')
__pcache__ = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'), 'emby')).decode('utf-8')
__cache__ = xbmc.translatePath('special://temp/emby').decode('utf-8')

if not xbmcvfs.exists(__pcache__ + '/'):
    from resources.lib.helper.utils import copytree

    copytree(os.path.join(__base__, 'objects'), os.path.join(__pcache__, 'objects'))

sys.path.insert(0, __cache__)
sys.path.insert(0, __pcache__)
sys.path.append(__base__)

#################################################################################################

from entrypoint import Service
from helper import settings
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY.service")
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

            if not 'ExitService' in error and service is not None:
                service.shutdown()

            self.exception = error


if __name__ == "__main__":

    LOG.warn("-->[ service ]")
    LOG.warn("Delay startup by %s seconds.", DELAY)

    while True:

        try:
            session = ServiceManager()
            session.start()
            session.join() # Block until the thread exits.

            if 'RestartService' in session.exception:

                ''' Reload objects which depends on the patch module.
                '''
                LOG.warn("--[ RESTART ]")

                import objects
                import library
                import full_sync
                import monitor

                reload_modules = ['objects.movies', 'objects.musicvideos', 'objects.tvshows',
                                  'objects.music', 'objects.obj', 'objects.actions', 'objects.kodi.kodi',
                                  'objects.kodi.movies', 'objects.kodi.musicvideos', 'objects.kodi.tvshows',
                                  'objects.kodi.music', 'objects.kodi.artwork', 'objects.kodi.queries',
                                  'objects.kodi.queries_music', 'objects.kodi.queries_texture']

                for mod in reload_modules:
                    del sys.modules[mod]

                reload(objects.kodi)
                reload(objects)
                reload(library)
                reload(full_sync)
                reload(monitor)

                continue

        except Exception as error:
            ''' Issue initializing the service.
            '''
            LOG.exception(error)

        break

    LOG.warn("--<[ service ]")
