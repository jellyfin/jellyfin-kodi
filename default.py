# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys
import urlparse

import xbmc
import xbmcaddon

#################################################################################################

_ADDON = xbmcaddon.Addon(id='plugin.video.emby')
_CWD = _ADDON.getAddonInfo('path').decode('utf-8')
_BASE_LIB = xbmc.translatePath(os.path.join(_CWD, 'resources', 'lib')).decode('utf-8')
sys.path.append(_BASE_LIB)

#################################################################################################

import entrypoint
import loghandler
from utils import window, dialog, language as lang
from ga_client import GoogleAnalytics
import database

#################################################################################################

loghandler.config()
log = logging.getLogger("EMBY.default")

#################################################################################################


class Main(object):

    # MAIN ENTRY POINT
    #@utils.profiling()

    def __init__(self):

        # Parse parameters
        base_url = sys.argv[0]
        path = sys.argv[2]
        params = urlparse.parse_qs(path[1:])
        log.warn("Parameter string: %s params: %s", path, params)
        try:
            mode = params['mode'][0]
        except (IndexError, KeyError):
            mode = ""

        if "/extrafanart" in base_url:

            emby_path = path[1:]
            emby_id = params.get('id', [""])[0]
            entrypoint.getExtraFanArt(emby_id, emby_path)

        elif "/Extras" in base_url or "/VideoFiles" in base_url:

            emby_path = path[1:]
            emby_id = params.get('id', [""])[0]
            entrypoint.getVideoFiles(emby_id, emby_path)

        elif not self._modes(mode, params):
            # Other functions
            if mode == 'settings':
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

            elif mode in ('manualsync', 'fastsync', 'repair'):
                self._library_sync(mode)

            elif mode == 'texturecache':
                import artwork
                artwork.Artwork().texture_cache_sync()
            else:
                entrypoint.doMainListing()

    @classmethod
    def _modes(cls, mode, params):
        import utils
        modes = {

            'reset': database.db_reset,
            'resetauth': entrypoint.resetAuth,
            'play': entrypoint.doPlayback,
            'passwords': utils.passwordsXML,
            'adduser': entrypoint.addUser,
            'thememedia': entrypoint.getThemeMedia,
            'channels': entrypoint.BrowseChannels,
            'channelsfolder': entrypoint.BrowseChannels,
            'browsecontent': entrypoint.BrowseContent,
            'getsubfolders': entrypoint.GetSubFolders,
            'nextup': entrypoint.getNextUpEpisodes,
            'inprogressepisodes': entrypoint.getInProgressEpisodes,
            'recentepisodes': entrypoint.getRecentEpisodes,
            'refreshplaylist': entrypoint.refreshPlaylist,
            'deviceid': entrypoint.resetDeviceId,
            'delete': entrypoint.deleteItem,
            'connect': entrypoint.emby_connect,
            'backup': entrypoint.emby_backup
        }
        if mode in modes:
            # Simple functions
            action = modes[mode]
            item_id = params.get('id')
            if item_id:
                item_id = item_id[0]

            if mode == 'play':
                database_id = params.get('dbid')
                action(item_id, database_id)

            elif mode == 'recentepisodes':
                limit = int(params['limit'][0])
                action(item_id, limit, params.get('filters', [""])[0])

            elif mode in ('nextup', 'inprogressepisodes'):
                limit = int(params['limit'][0])
                action(item_id, limit)

            elif mode in ('channels', 'getsubfolders'):
                action(item_id)

            elif mode == 'browsecontent':
                action(item_id, params.get('type', [""])[0], params.get('folderid', [""])[0])

            elif mode == 'channelsfolder':
                folderid = params['folderid'][0]
                action(item_id, folderid)
            else:
                action()

            return True

        return False

    @classmethod
    def _library_sync(cls, mode):

        if window('emby_online') != "true":
            # Server is not online, do not run the sync
            dialog(type_="ok",
                   heading="{emby}",
                   line1=lang(33034))
            log.warn("Not connected to the emby server")

        elif window('emby_dbScan') != "true":
            import librarysync
            library_sync = librarysync.LibrarySync()

            if mode == 'manualsync':
                librarysync.ManualSync().sync()
            elif mode == 'fastsync':
                library_sync.startSync()
            else:
                library_sync.fullSync(repair=True)
        else:
            log.warn("Database scan is already running")


if __name__ == "__main__":

    log.info("plugin.video.emby started")

    try:
        Main()
    except Exception as error:
        if not (hasattr(error, 'quiet') and error.quiet):
            ga = GoogleAnalytics()
            errStrings = ga.formatException()
            ga.sendEventData("Exception", errStrings[0], errStrings[1])
        log.exception(error)
        raise

    log.info("plugin.video.emby stopped")
