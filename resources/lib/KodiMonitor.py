#################################################################################################
# Kodi  Monitor
# Watched events that occur in Kodi, like setting media watched
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import json

import Utils as utils
from WriteKodiDB import WriteKodiDB
from DownloadUtils import DownloadUtils

class Kodi_Monitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def onDatabaseUpdated(self, database):
        pass
    
    #this library monitor is used to detect a watchedstate change by the user through the library
    #as well as detect when a library item has been deleted to pass the delete to the Emby server
    def onNotification  (self,sender,method,data):
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        if method == "VideoLibrary.OnUpdate":
           
            jsondata = json.loads(data)
            if jsondata != None:
                
                playcount = None
                playcount = jsondata.get("playcount")
                item = jsondata.get("item").get("id")
                type = jsondata.get("item").get("type")
                if playcount != None:
                    utils.logMsg("MB# Sync","Kodi_Monitor--> VideoLibrary.OnUpdate : " + str(data),2)
                    WriteKodiDB().updatePlayCountFromKodi(item, type, playcount)
        if method == "VideoLibrary.OnRemove":
            xbmc.log('Intercepted remove from sender: ' + sender + ' method: ' + method + ' data: ' + data)
            WINDOW = xbmcgui.Window( 10000 )
            if WINDOW.getProperty("suspendDeletes") == "True":
                #This is a handshake to not try to delete if the item was removed from the Kodi DB due to sync
                xbmc.log('Item deleted by sync')
                WINDOW.setProperty("suspendDeletes", "False")
                return
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.get("type") == "episode":
                    episodeid = jsondata.get("id")
                    MBlist = WINDOW.getProperty("episodeid" + str(episodeid)).split(";;")
                    #MBlist[0] is the ID, and [1] the title
                    url='http://' + server + '/mediabrowser/Items?Ids=' + MBlist[1] + '&format=json'
                    #This is a check to see if the item exists on the server, if it doesn't it may have already been deleted by another client
                    data = DownloadUtils().downloadUrl(url=url, suppress=True, popup=0)
                    result = json.loads(data)
                    item = result.get("Items")[0]
                    if WINDOW.getProperty("embyid" + item.get("Id")) == "deleted":
                        xbmc.log('Item was already deleted: ' + str(MBlist))
                    elif data != "":
                        return_value = xbmcgui.Dialog().yesno("Confirm Delete", "Delete: "+ MBlist[0] + "\n on Emby Server?")
                        if return_value:
                            url='http://' + server + '/mediabrowser/Items/' + MBlist[1]
                            xbmc.log('Deleting via URL: ' + url)
                            DownloadUtils().downloadUrl(url, type="DELETE")
                
                

