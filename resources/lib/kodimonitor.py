# -*- coding: utf-8 -*-

#################################################################################################

import json

import xbmc
import xbmcgui

import clientinfo
import downloadutils
import embydb_functions as embydb
import playbackutils as pbutils
from utils import Logging, window, settings, kodiSQL

#################################################################################################


class KodiMonitor(xbmc.Monitor):


    def __init__(self):

        global log
        log = Logging(self.__class__.__name__).log

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils()

        log("Kodi monitor started.", 1)


    def onScanStarted(self, library):
        log("Kodi library scan %s running." % library, 2)
        if library == "video":
            window('emby_kodiScan', value="true")
            
    def onScanFinished(self, library):
        log("Kodi library scan %s finished." % library, 2)
        if library == "video":
            window('emby_kodiScan', clear=True)

    def onSettingsChanged(self):
        # Monitor emby settings
        # Review reset setting at a later time, need to be adjusted to account for initial setup
        # changes.
        '''currentPath = utils.settings('useDirectPaths')
        if utils.window('emby_pluginpath') != currentPath:
            # Plugin path value changed. Offer to reset
            log("Changed to playback mode detected", 1)
            utils.window('emby_pluginpath', value=currentPath)
            resp = xbmcgui.Dialog().yesno(
                                heading="Playback mode change detected",
                                line1=(
                                    "Detected the playback mode has changed. The database "
                                    "needs to be recreated for the change to be applied. "
                                    "Proceed?"))
            if resp:
                utils.reset()'''

        currentLog = settings('logLevel')
        if window('emby_logLevel') != currentLog:
            # The log level changed, set new prop
            log("New log level: %s" % currentLog, 1)
            window('emby_logLevel', value=currentLog)

    def onNotification(self, sender, method, data):

        doUtils = self.doUtils
        if method not in ("Playlist.OnAdd"):
            log("Method: %s Data: %s" % (method, data), 1)
            
        if data:
            data = json.loads(data,'utf-8')


        if method == "Player.OnPlay":
            # Set up report progress for emby playback
            item = data.get('item')
            try:
                kodiid = item['id']
                item_type = item['type']
            except (KeyError, TypeError):
                log("Item is invalid for playstate update.", 1)
            else:
                if ((settings('useDirectPaths') == "1" and not item_type == "song") or
                        (item_type == "song" and settings('enableMusic') == "true")):
                    # Set up properties for player
                    embyconn = kodiSQL('emby')
                    embycursor = embyconn.cursor()
                    emby_db = embydb.Embydb_Functions(embycursor)
                    emby_dbitem = emby_db.getItem_byKodiId(kodiid, item_type)
                    try:
                        itemid = emby_dbitem[0]
                    except TypeError:
                        log("No kodiId returned.", 1)
                    else:
                        url = "{server}/emby/Users/{UserId}/Items/%s?format=json" % itemid
                        result = doUtils.downloadUrl(url)
                        log("Item: %s" % result, 2)

                        playurl = None
                        count = 0
                        while not playurl and count < 2:
                            try:
                                playurl = xbmc.Player().getPlayingFile()
                            except RuntimeError:
                                count += 1
                                xbmc.sleep(200)
                            else:
                                listItem = xbmcgui.ListItem()
                                playback = pbutils.PlaybackUtils(result)

                                if item_type == "song" and settings('streamMusic') == "true":
                                    window('emby_%s.playmethod' % playurl, value="DirectStream")
                                else:
                                    window('emby_%s.playmethod' % playurl, value="DirectPlay")
                                # Set properties for player.py
                                playback.setProperties(playurl, listItem)
                    finally:
                        embycursor.close()
            

        elif method == "VideoLibrary.OnUpdate":
            # Manually marking as watched/unwatched
            playcount = data.get('playcount')
            item = data.get('item')
            try:
                kodiid = item['id']
                item_type = item['type']
            except (KeyError, TypeError):
                log("Item is invalid for playstate update.", 1)
            else:
                # Send notification to the server.
                embyconn = kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, item_type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    log("Could not find itemid in emby database.", 1)
                else:
                    # Stop from manually marking as watched unwatched, with actual playback.
                    if window('emby_skipWatched%s' % itemid) == "true":
                        # property is set in player.py
                        window('emby_skipWatched%s' % itemid, clear=True)
                    else:
                        # notify the server
                        url = "{server}/emby/Users/{UserId}/PlayedItems/%s?format=json" % itemid
                        if playcount != 0:
                            doUtils.downloadUrl(url, action_type="POST")
                            log("Mark as watched for itemid: %s" % itemid, 1)
                        else:
                            doUtils.downloadUrl(url, action_type="DELETE")
                            log("Mark as unwatched for itemid: %s" % itemid, 1)
                finally:
                    embycursor.close()


        elif method == "VideoLibrary.OnRemove":
            # Removed function, because with plugin paths + clean library, it will wipe
            # entire library if user has permissions. Instead, use the emby context menu available
            # in Isengard and higher version
            pass
            '''try:
                kodiid = data['id']
                type = data['type']
            except (KeyError, TypeError):
                log("Item is invalid for emby deletion.", 1)
            else:
                # Send the delete action to the server.
                embyconn = utils.kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    log("Could not find itemid in emby database.", 1)
                else:
                    if utils.settings('skipContextMenu') != "true":
                        resp = xbmcgui.Dialog().yesno(
                                                heading="Confirm delete",
                                                line1="Delete file on Emby Server?")
                        if not resp:
                            log("User skipped deletion.", 1)
                            embycursor.close()
                            return

                    url = "{server}/emby/Items/%s?format=json" % itemid
                    log("Deleting request: %s" % itemid)
                    doUtils.downloadUrl(url, action_type="DELETE")
                finally:
                    embycursor.close()'''


        elif method == "System.OnWake":
            # Allow network to wake up
            xbmc.sleep(10000)
            window('emby_onWake', value="true")


        elif method == "GUI.OnScreensaverDeactivated":
            if settings('dbSyncScreensaver') == "true":
                xbmc.sleep(5000);
                window('emby_onWake', value="true")


        elif method == "Playlist.OnClear":
            pass