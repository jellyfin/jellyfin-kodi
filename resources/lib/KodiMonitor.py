#################################################################################################
# Kodi  Monitor
# Watched events that occur in Kodi, like setting media watched
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import json

import Utils as utils
from WriteKodiVideoDB import WriteKodiVideoDB
from ReadKodiDB import ReadKodiDB
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils
from PlaybackUtils import PlaybackUtils


class Kodi_Monitor( xbmc.Monitor ):
    
    WINDOW = xbmcgui.Window(10000)

    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def logMsg(self, msg, lvl = 1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % ("EMBY", className), msg, int(lvl))

    def onScanStarted(self, library):
        utils.window('kodiScan', value="true")
        self.logMsg("Kodi library scan running.", 2)

    def onScanFinished(self, library):
        utils.window('kodiScan', clear=True)
        self.logMsg("Kodi library scan finished.", 2)
        
    #this library monitor is used to detect a watchedstate change by the user through the library
    #as well as detect when a library item has been deleted to pass the delete to the Emby server
    def onNotification  (self, sender, method, data):

        WINDOW = self.WINDOW
        downloadUtils = DownloadUtils()
        #player started playing an item - 
        if ("Playlist.OnAdd" in method or "Player.OnPlay" in method):

            jsondata = json.loads(data)
            if jsondata:
                if jsondata.has_key("item"):
                    if jsondata.get("item").has_key("id") and jsondata.get("item").has_key("type"):
                        id = jsondata.get("item").get("id")
                        type = jsondata.get("item").get("type")
                        
                        if (utils.settings('useDirectPaths')=='true' and not type == "song") or (type == "song" and utils.settings('enableMusicSync') == "true"):
                            
                            if type == "song":
                                connection = utils.KodiSQL('music')
                                cursor = connection.cursor()
                                embyid = ReadKodiDB().getEmbyIdByKodiId(id, type, connection, cursor)
                                cursor.close()
                            else:    
                                embyid = ReadKodiDB().getEmbyIdByKodiId(id,type)

                            if embyid:

                                url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % embyid
                                result = downloadUtils.downloadUrl(url)
                                self.logMsg("Result: %s" % result, 2)
                                
                                playurl = None
                                count = 0
                                while not playurl and count < 2:
                                    try:
                                        playurl = xbmc.Player().getPlayingFile()
                                    except RuntimeError:
                                        xbmc.sleep(200)
                                    else:
                                        listItem = xbmcgui.ListItem()
                                        PlaybackUtils().setProperties(playurl, result, listItem)

                                        if type == "song" and utils.settings('directstreammusic') == "true":
                                            utils.window('%splaymethod' % playurl, value="DirectStream")
                                        else:
                                            utils.window('%splaymethod' % playurl, value="DirectPlay")

                                    count += 1
        
        if method == "VideoLibrary.OnUpdate":
            # Triggers 4 times, the following is only for manually marking as watched/unwatched
            jsondata = json.loads(data)
            
            try:
                playcount = jsondata.get('playcount')
                item = jsondata['item']['id']
                type = jsondata['item']['type']
                prop = utils.window('Played%s%s' % (type, item))
            except:
                self.logMsg("Could not process VideoLibrary.OnUpdate data.", 1)
            else:
                self.logMsg("VideoLibrary.OnUpdate: %s" % data, 2)
                if prop != "true":
                    # Set property to prevent the multi triggering
                    utils.window('Played%s%s' % (type, item), "true")
                    WriteKodiVideoDB().updatePlayCountFromKodi(item, type, playcount)

                self.clearProperty(type, item)
                    
        if method == "System.OnWake":
            xbmc.sleep(10000) #Allow network to wake up
            WINDOW.setProperty("OnWakeSync", "true")

        if method == "VideoLibrary.OnRemove":
            xbmc.log('Intercepted remove from sender: ' + sender + ' method: ' + method + ' data: ' + data)
            jsondata = json.loads(data)
            id = ReadKodiDB().getEmbyIdByKodiId(jsondata.get("id"), jsondata.get("type"))
            if id == None:
                return            
            xbmc.log("Deleting Emby ID: " + id + " from database")
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            cursor.execute("DELETE FROM emby WHERE emby_id = ?", (id,))
            connection.commit()
            cursor.close
            
            if jsondata:
                if jsondata.get("type") == "episode" or "movie":
                    url='{server}/mediabrowser/Items?Ids=' + id + '&format=json'
                    #This is a check to see if the item exists on the server, if it doesn't it may have already been deleted by another client
                    result = DownloadUtils().downloadUrl(url)
                    item = result.get("Items")[0]
                    if data:
                        return_value = xbmcgui.Dialog().yesno("Confirm Delete", "Delete file on Emby Server?")
                        if return_value:
                            url='{server}/mediabrowser/Items/' + id
                            xbmc.log('Deleting via URL: ' + url)
                            DownloadUtils().downloadUrl(url, type="DELETE")

        elif method == "Playlist.OnClear":
            self.logMsg("Clear playback properties.", 2)
            utils.window('propertiesPlayback', clear=True)
                            
    def clearProperty(self, type, id):
        # The sleep is necessary since VideoLibrary.OnUpdate
        # triggers 4 times in a row.
        xbmc.sleep(100)
        utils.window('Played%s%s' % (type,id), clear=True)
            
        # Clear the widget cache
        utils.window('clearwidgetcache', value="clear")