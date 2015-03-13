#################################################################################################
# Kodi  Monitor
# Watched events that occur in Kodi, like setting media watched
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import json

import Utils as utils
from LibrarySync import LibrarySync

librarySync = LibrarySync()

WINDOW = xbmcgui.Window( 10000 )

class Kodi_Monitor(xbmc.Monitor):
    def __init__(self, *args, **kwargs):
        xbmc.Monitor.__init__(self)

    def onDatabaseUpdated(self, database):
        pass
    
    #this library monitor is used to detect a watchedstate change by the user through the library
    def onNotification  (self,sender,method,data):
        if method == "VideoLibrary.OnUpdate":
            
            #check windowprop if the sync is busy to prevent any false updates
            if WINDOW.getProperty("librarysync") != "busy":
            
                jsondata = json.loads(data)
                if jsondata != None:
                    playcount = None
                    playcount = jsondata.get("playcount")
                    item = jsondata.get("item").get("id")
                    
                    if playcount != None:
                        librarySync.updatePlayCountFromKodi(item, playcount)

