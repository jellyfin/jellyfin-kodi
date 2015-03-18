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
            
            #check windowprop if the sync is busy to prevent any false updates
            WINDOW = xbmcgui.Window( 10000 )
            if WINDOW.getProperty("librarysync") != "busy":
                xbmc.log("Kodi_Monitor -> onNotification -> VideoLibrary.OnUpdate : " + str(data))
                jsondata = json.loads(data)
                if jsondata != None:
                    playcount = None
                    playcount = jsondata.get("playcount")
                    item = jsondata.get("item").get("id")
                    type = jsondata.get("item").get("type")
                    
                    if playcount != None:
                        WriteKodiDB().updatePlayCountFromKodi(item, type, playcount)

