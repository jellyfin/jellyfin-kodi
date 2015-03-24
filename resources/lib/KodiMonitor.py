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

class Kodi_Monitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def onDatabaseUpdated(self, database):
        pass
    
    #this library monitor is used to detect a watchedstate change by the user through the library
    def onNotification  (self,sender,method,data):

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
           
            jsondata = json.loads(data)
            if jsondata != None:
                if jsondata.get("type") == "episode":
                    episodeid = jsondata.get("id")
                    WINDOW = xbmcgui.Window( 10000 )
                    MBlist = WINDOW.getProperty("episodeid" + str(episodeid)).split(";;")
                    return_value = xbmcgui.Dialog().yesno("Confirm Delete", "Not really going to, but if I were I would delete: Title - "+ MBlist[0] + " MBID: " + MBlist[1])
                
                

