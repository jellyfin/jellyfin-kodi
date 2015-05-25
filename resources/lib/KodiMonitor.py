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
from LibrarySync import LibrarySync
from PlayUtils import PlayUtils
from DownloadUtils import DownloadUtils
from PlaybackUtils import PlaybackUtils

class Kodi_Monitor(xbmc.Monitor):
    
    WINDOW = xbmcgui.Window(10000)

    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def onDatabaseUpdated(self, database):
        pass
    
    #this library monitor is used to detect a watchedstate change by the user through the library
    #as well as detect when a library item has been deleted to pass the delete to the Emby server
    def onNotification  (self,sender,method,data):

        WINDOW = self.WINDOW
        downloadUtils = DownloadUtils()

        if method == "VideoLibrary.OnUpdate":
            jsondata = json.loads(data)
            if jsondata != None:
                
                playcount = None
                playcount = jsondata.get("playcount")
                item = jsondata.get("item").get("id")
                type = jsondata.get("item").get("type")
                prop = WINDOW.getProperty('Played%s%s' % (type,item))
                processWatched = WINDOW.getProperty('played_skipWatched')
                
                if (playcount != None) and (prop != "true") and (processWatched != "true"):
                    WINDOW.setProperty("Played%s%s" % (type,item), "true")
                    utils.logMsg("MB# Sync","Kodi_Monitor--> VideoLibrary.OnUpdate : " + str(data),2)
                    WriteKodiVideoDB().updatePlayCountFromKodi(item, type, playcount)
                
                self.clearProperty(type,item)
                    
        if method == "System.OnWake":
            xbmc.sleep(10000) #Allow network to wake up
            if WINDOW.getProperty("SyncDatabaseRunning") != "true":
                utils.logMsg("Doing_Db_Sync Post Resume: syncDatabase (Started)",0)
                libSync = LibrarySync().FullLibrarySync()
                utils.logMsg("Doing_Db_Sync Post Resume: syncDatabase (Finished) " + str(libSync),0)


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
                if jsondata.get("type") == "episode":
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
                            
    def clearProperty(self,type,id):
        # The sleep is necessary since VideoLibrary.OnUpdate
        # triggers 3 times in a row.
        xbmc.sleep(100)
        self.WINDOW.clearProperty("Played%s%s" % (type,id))
        self.WINDOW.clearProperty('played_skipWatched')
            
        
                

