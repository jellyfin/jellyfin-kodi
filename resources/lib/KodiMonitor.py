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
            #WINDOW = xbmcgui.Window( 10000 )
            #if WINDOW.getProperty("librarysync") != "busy":
            # I don't thing we need this, the playcount is not present in updates that don't touch that
            # and when the playcount is updated byt he sync it just sends the same data back to the server
            # if you add this back in you will never be able to trigger a play status update while the sync is running
            
            jsondata = json.loads(data)
            if jsondata != None:
                
                playcount = None
                playcount = jsondata.get("playcount")
                item = jsondata.get("item").get("id")
                type = jsondata.get("item").get("type")
                if playcount != None:
                    xbmc.log("Kodi_Monitor -> onNotification -> VideoLibrary.OnUpdate : " + str(data))
                    WriteKodiDB().updatePlayCountFromKodi(item, type, playcount)

