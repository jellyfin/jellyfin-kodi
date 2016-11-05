# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging

import xbmc
import xbmcgui

import downloadutils
import embydb_functions as embydb
import playbackutils as pbutils
from utils import window, settings
from ga_client import log_error
from database import DatabaseConn
from contextlib import closing

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class KodiMonitor(xbmc.Monitor):


    def __init__(self):

        xbmc.Monitor.__init__(self)

        self.download = downloadutils.DownloadUtils().downloadUrl
        log.info("Kodi monitor started")


    def onScanStarted(self, library):

        log.debug("Kodi library scan %s running", library)
        if library == "video":
            window('emby_kodiScan', value="true")

    def onScanFinished(self, library):

        log.debug("Kodi library scan %s finished", library)
        if library == "video":
            window('emby_kodiScan', clear=True)

    def onSettingsChanged(self):
        # Monitor emby settings
        current_log_level = settings('logLevel')
        if window('emby_logLevel') != current_log_level:
            # The log level changed, set new prop
            log.info("New log level: %s", current_log_level)
            window('emby_logLevel', value=current_log_level)

        current_context = "true" if settings('enableContext') == "true" else ""
        if window('emby_context') != current_context:
            log.info("New context setting: %s", current_context)
            window('emby_context', value=current_context)

    @log_error()
    def onNotification(self, sender, method, data):

        if method not in ('Playlist.OnAdd', 'Player.OnStop', 'Player.OnClear'):
            log.info("Method: %s Data: %s", method, data)

        if data:
            data = json.loads(data, 'utf-8')

        if method == 'Player.OnPlay':
            self._on_play_(data)

        elif method == 'VideoLibrary.OnUpdate':
            self._video_update(data)

        elif method == 'System.OnSleep':
            # Connection is going to sleep
            log.info("Marking the server as offline. System.OnSleep activated.")
            window('emby_online', value="sleep")

        elif method == 'System.OnWake':
            self._system_wake()

        elif method == 'GUI.OnScreensaverDeactivated':
            self._screensaver_deactivated()

    def _on_play_(self, data):
        # Set up report progress for emby playback
        try:
            item = data['item']
            kodi_id = item['id']
            item_type = item['type']
        except (KeyError, TypeError):
            log.info("Item is invalid for playstate update")
        else:
            if ((settings('useDirectPaths') == "1" and not item_type == "song") or
                    (item_type == "song" and settings('enableMusic') == "true")):
                # Set up properties for player
                item_id = self._get_item_id(kodi_id, item_type)
                if item_id:
                    url = "{server}/emby/Users/{UserId}/Items/%s?format=json" % item_id
                    result = self.download(url)
                    log.debug("Item: %s", result)

                    playurl = None
                    count = 0
                    while not playurl and count < 2:
                        try:
                            playurl = xbmc.Player().getPlayingFile()
                        except RuntimeError:
                            count += 1
                            xbmc.sleep(200)
                        else:
                            listitem = xbmcgui.ListItem()
                            playback = pbutils.PlaybackUtils(result)

                            if item_type == "song" and settings('streamMusic') == "true":
                                window('emby_%s.playmethod' % playurl, value="DirectStream")
                            else:
                                window('emby_%s.playmethod' % playurl, value="DirectPlay")
                            # Set properties for player.py
                            playback.setProperties(playurl, listitem)

    def _video_update(self, data):
        # Manually marking as watched/unwatched
        try:
            item = data['item']
            kodi_id = item['id']
            item_type = item['type']
        except (KeyError, TypeError):
            log.info("Item is invalid for playstate update")
        else:
            # Send notification to the server.
            item_id = self._get_item_id(kodi_id, item_type)
            if item_id:
                # Stop from manually marking as watched unwatched, with actual playback.
                if window('emby_skipWatched%s' % item_id) == "true":
                    # property is set in player.py
                    window('emby_skipWatched%s' % item_id, clear=True)
                else:
                    # notify the server
                    url = "{server}/emby/Users/{UserId}/PlayedItems/%s?format=json" % item_id
                    if data.get('playcount') != 0:
                        self.download(url, action_type="POST")
                        log.info("Mark as watched for itemid: %s", item_id)
                    else:
                        self.download(url, action_type="DELETE")
                        log.info("Mark as unwatched for itemid: %s", item_id)

    @classmethod
    def _system_wake(cls):
        # Allow network to wake up
        xbmc.sleep(10000)
        window('emby_online', value="false")
        window('emby_onWake', value="true")

    @classmethod
    def _screensaver_deactivated(cls):

        if settings('dbSyncScreensaver') == "true":
            xbmc.sleep(5000)
            window('emby_onWake', value="true")

    @classmethod
    def _get_item_id(cls, kodi_id, item_type):

        item_id = None

        with DatabaseConn('emby') as conn:
            with closing(conn.cursor()) as cursor:
                emby_db = embydb.Embydb_Functions(cursor)
                db_item = emby_db.getItem_byKodiId(kodi_id, item_type)

        try:
            item_id = db_item[0]
        except TypeError:
            log.info("Could not retrieve item Id")

        return item_id
