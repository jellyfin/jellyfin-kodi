# -*- coding: utf-8 -*-

#################################################################################################

import json

import xbmc
import xbmcgui

import clientinfo
import downloadutils
import embydb_functions as embydb
import playbackutils as pbutils
import utils

#################################################################################################


class KodiMonitor(xbmc.Monitor):


    def __init__(self):

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils()

        self.logMsg("Kodi monitor started.", 1)

    def logMsg(self, msg, lvl=1):

        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, lvl)


    def onScanStarted(self, library):
        self.logMsg("Kodi library scan %s running." % library, 2)
        if library == "video":
            utils.window('emby_kodiScan', value="true")
            
    def onScanFinished(self, library):
        self.logMsg("Kodi library scan %s finished." % library, 2)
        if library == "video":
            utils.window('emby_kodiScan', clear=True)

    def onSettingsChanged(self):
        # Monitor emby settings
        currentPath = utils.settings('useDirectPaths')
        if utils.window('emby_pluginpath') != currentPath:
            # Plugin path value changed. Offer to reset
            self.logMsg("Changed to playback mode detected", 1)
            utils.window('emby_pluginpath', value=currentPath)
            resp = xbmcgui.Dialog().yesno(
                                heading="Playback mode change detected",
                                line1=(
                                    "Detected the playback mode has changed. The database "
                                    "needs to be recreated for the change to be applied. "
                                    "Proceed?"))
            if resp:
                utils.reset()

        currentLog = utils.settings('logLevel')
        if utils.window('emby_logLevel') != currentLog:
            # The log level changed, set new prop
            self.logMsg("New log level: %s" % currentLog, 1)
            utils.window('emby_logLevel', value=currentLog)

    def onNotification(self, sender, method, data):

        doUtils = self.doUtils
        if method not in ("Playlist.OnAdd"):
            self.logMsg("Method: %s Data: %s" % (method, data), 1)
            
        if data:
            data = json.loads(data)


        if method == "Player.OnPlay":
            # Set up report progress for emby playback
            item = data.get('item')
            try:
                kodiid = item['id']
                type = item['type']
            except (KeyError, TypeError):
                self.logMsg("Properties already set for item.", 1)
            else:
                if ((utils.settings('useDirectPaths') == "1" and not type == "song") or
                        (type == "song" and utils.settings('enableMusic') == "true")):
                    # Set up properties for player
                    embyconn = utils.kodiSQL('emby')
                    embycursor = embyconn.cursor()
                    emby_db = embydb.Embydb_Functions(embycursor)
                    emby_dbitem = emby_db.getItem_byKodiId(kodiid, type)
                    try:
                        itemid = emby_dbitem[0]
                    except TypeError:
                        self.logMsg("No kodiid returned.", 1)
                    else:
                        url = "{server}/emby/Users/{UserId}/Items/%s?format=json" % itemid
                        result = doUtils.downloadUrl(url)
                        self.logMsg("Item: %s" % result, 2)

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

                                if type == "song" and utils.settings('streamMusic') == "true":
                                    utils.window('emby_%s.playmethod' % playurl,
                                        value="DirectStream")
                                else:
                                    utils.window('emby_%s.playmethod' % playurl,
                                        value="DirectPlay")
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
                type = item['type']
            except (KeyError, TypeError):
                self.logMsg("Item is invalid for playstate update.", 1)
            else:
                # Send notification to the server.
                embyconn = utils.kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    self.logMsg("Could not find itemid in emby database.", 1)
                else:
                    # Stop from manually marking as watched unwatched, with actual playback.
                    if utils.window('emby_skipWatched%s' % itemid) == "true":
                        # property is set in player.py
                        utils.window('emby_skipWatched%s' % itemid, clear=True)
                    else:
                        # notify the server
                        url = "{server}/emby/Users/{UserId}/PlayedItems/%s?format=json" % itemid
                        if playcount != 0:
                            doUtils.downloadUrl(url, type="POST")
                            self.logMsg("Mark as watched for itemid: %s" % itemid, 1)
                        else:
                            doUtils.downloadUrl(url, type="DELETE")
                            self.logMsg("Mark as unwatched for itemid: %s" % itemid, 1)
                finally:
                    embycursor.close()


        elif method == "VideoLibrary.OnRemove":

            try:
                kodiid = data['id']
                type = data['type']
            except (KeyError, TypeError):
                self.logMsg("Item is invalid for emby deletion.", 1)
            else:
                # Send the delete action to the server.
                embyconn = utils.kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                emby_dbitem = emby_db.getItem_byKodiId(kodiid, type)
                try:
                    itemid = emby_dbitem[0]
                except TypeError:
                    self.logMsg("Could not find itemid in emby database.", 1)
                else:
                    if utils.settings('skipConfirmDelete') != "true":
                        resp = xbmcgui.Dialog().yesno(
                                                heading="Confirm delete",
                                                line1="Delete file on Emby Server?")
                        if not resp:
                            self.logMsg("User skipped deletion.", 1)
                            embycursor.close()
                            return
                    url = "{server}/emby/Items/%s?format=json" % itemid
                    self.logMsg("Deleting request: %s" % itemid)
                    doUtils.downloadUrl(url, type="DELETE")
                finally:
                    embycursor.close()


        elif method == "System.OnWake":
            # Allow network to wake up
            xbmc.sleep(10000)
            utils.window('emby_onWake', value="true")

        elif method == "Playlist.OnClear":
            utils.window('emby_customPlaylist', clear=True, windowid=10101)
            #xbmcgui.Window(10101).clearProperties()
            self.logMsg("Clear playlist properties.")