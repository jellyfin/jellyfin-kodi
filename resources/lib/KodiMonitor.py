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
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.get("type") == "episode":
                    episodeid = jsondata.get("id")
                    WINDOW = xbmcgui.Window( 10000 )
                    MBlist = WINDOW.getProperty("episodeid" + str(episodeid)).split(";;")
                    url='http://' + server + '/mediabrowser/Items?Ids=' + MBlist[1] + '&format=json'
                    data = DownloadUtils().downloadUrl(url=url, suppress=True, popup=0)
                    if data != "":
                        return_value = xbmcgui.Dialog().yesno("Confirm Delete", "Delete: "+ MBlist[0] + "\n on Emby Server?\nEmbyID: " + MBlist[1])
                        if return_value:
                            url='http://' + server + '/mediabrowser/Items/' + MBlist[1]
                            xbmc.log('Deleting via URL: ' + url)
                            DownloadUtils().downloadUrl(url, type="DELETE")
                
                

