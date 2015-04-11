import xbmcaddon
import xbmc
import xbmcgui
import os
import threading
import json
from datetime import datetime

cwd = xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('path')
BASE_RESOURCE_PATH = xbmc.translatePath( os.path.join( cwd, 'resources', 'lib' ) )
sys.path.append(BASE_RESOURCE_PATH)

import KodiMonitor
import Utils as utils
from LibrarySync import LibrarySync
from Player import Player
from DownloadUtils import DownloadUtils
from ConnectionManager import ConnectionManager
from ClientInformation import ClientInformation
from WebSocketClient import WebSocketThread
from UserClient import UserClient
librarySync = LibrarySync()


class Service():
    

    newWebSocketThread = None
    newUserClient = None

    clientInfo = ClientInformation()
    addonName = clientInfo.getAddonName()
    className = None
    
    def __init__(self, *args ):
        self.KodiMonitor = KodiMonitor.Kodi_Monitor()
        addonName = self.addonName
        self.className = self.__class__.__name__

        self.logMsg("Starting Monitor", 0)
        self.logMsg("======== START %s ========" % addonName, 0)
        self.logMsg("KODI Version: %s" % xbmc.getInfoLabel("System.BuildVersion"), 0)
        self.logMsg("%s Version: %s" % (addonName, self.clientInfo.getVersion()), 0)
        pass

    def logMsg(self, msg, lvl=1):
        
        utils.logMsg("%s %s" % (self.addonName, self.className), str(msg), int(lvl))
            
    def ServiceEntryPoint(self):
        
        ConnectionManager().checkServer()
        
        lastProgressUpdate = datetime.today()
        
        startupComplete = False
        #interval_FullSync = 600
        #interval_IncrementalSync = 300
        
        #cur_seconds_fullsync = interval_FullSync
        #cur_seconds_incrsync = interval_IncrementalSync
        
        user = UserClient()
        player = Player()
        ws = WebSocketThread()
        
        lastFile = None
        
        while not self.KodiMonitor.abortRequested():
            
            xbmc.sleep(1000)
            
            if xbmc.Player().isPlaying():
                try:
                    playTime = xbmc.Player().getTime()
                    totalTime = xbmc.Player().getTotalTime()
                    currentFile = xbmc.Player().getPlayingFile()
                    
                    if(player.played_information.get(currentFile) != None):
                        player.played_information[currentFile]["currentPosition"] = playTime
                    
                    # send update
                    td = datetime.today() - lastProgressUpdate
                    secDiff = td.seconds
                    if(secDiff > 10):
                        try:
                            player.reportPlayback()
                        except Exception, msg:
                            xbmc.log("MB3 Sync Service -> Exception reporting progress : " + msg)
                            pass
                        lastProgressUpdate = datetime.today()
                    # only try autoplay when there's 20 seconds or less remaining and only once!
                    if (totalTime - playTime <= 20 and (lastFile==None or lastFile!=currentFile)):
                        lastFile = currentFile
                        player.autoPlayPlayback()
                    
                except Exception, e:
                    xbmc.log("MB3 Sync Service -> Exception in Playback Monitor Service : " + str(e))
                    pass
            else:
                if (self.newUserClient == None):
                        self.newUserClient = "Started"
                        user.start()
                # background worker for database sync
                if (user.currUser != None):
                    
                    # Correctly launch the websocket, if user manually launches the add-on
                    if (self.newWebSocketThread == None):
                        self.newWebSocketThread = "Started"
                        ws.start()
            
                    #full sync
                    if(startupComplete == False):
                        xbmc.log("Doing_Db_Sync: syncDatabase (Started)")
                        libSync = librarySync.syncDatabase()
                        xbmc.log("Doing_Db_Sync: syncDatabase (Finished) " + str(libSync))
                        countSync = librarySync.updatePlayCounts()
                        xbmc.log("Doing_Db_Sync: updatePlayCounts (Finished) "  + str(countSync))

                        if(libSync and countSync):
                            startupComplete = True
                    else:
                        xbmc.sleep(10000)
                    
                else:
                    xbmc.log("Not authenticated yet")
                    
        utils.logMsg("MB3 Sync Service", "stopping Service",0)
        
        if (self.newWebSocketThread != None):
            ws.stopClient()

        if (self.newUserClient != None):
            user.stopClient()              
        
       
#start the service
Service().ServiceEntryPoint()
