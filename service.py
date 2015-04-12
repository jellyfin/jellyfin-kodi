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
from ConnectionManager import ConnectionManager
from ClientInformation import ClientInformation
from WebSocketClient import WebSocketThread
from UserClient import UserClient


class Service():
    

    newWebSocketThread = None
    newUserClient = None

    librarySync = LibrarySync()
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
        xbmcplayer = xbmc.Player()
        
        while not self.KodiMonitor.abortRequested():
            
            if self.KodiMonitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break
            
            if xbmcplayer.isPlaying():
                try:
                    playTime = xbmcplayer.getTime()
                    totalTime = xbmcplayer.getTotalTime()
                    currentFile = xbmcplayer.getPlayingFile()
                    
                    if(player.played_information.get(currentFile) != None):
                        player.played_information[currentFile]["currentPosition"] = playTime
                    
                    # send update
                    td = datetime.today() - lastProgressUpdate
                    secDiff = td.seconds
                    if(secDiff > 10):
                        try:
                            player.reportPlayback()
                        except Exception, msg:
                            self.logMsg("Exception reporting progress: %s" % msg, 0)
                            pass
                        lastProgressUpdate = datetime.today()
                    # only try autoplay when there's 20 seconds or less remaining and only once!
                    if (totalTime - playTime <= 20 and (lastFile==None or lastFile!=currentFile)):
                        lastFile = currentFile
                        player.autoPlayPlayback()
                    
                except Exception, e:
                    self.logMsg("Exception in Playback Monitor Service: %s" % e, 0)
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
                        librarySync = self.librarySync

                        self.logMsg("Doing_Db_Sync: syncDatabase (Started)", 1)
                        libSync = librarySync.syncDatabase()
                        self.logMsg("Doing_Db_Sync: syncDatabase (Finished) %s" % libSync, 1)
                        countSync = librarySync.updatePlayCounts()
                        self.logMsg("Doing_Db_Sync: updatePlayCounts (Finished) %s" % countSync, 1)

                        # Force refresh newly set thumbnails
                        xbmc.executebuiltin("UpdateLibrary(video)")
                        if(libSync and countSync):
                            startupComplete = True
                    else:
                        if self.KodiMonitor.waitForAbort(10):
                            # Abort was requested while waiting. We should exit
                            break                    
                    
                else:
                    self.logMsg("Not authenticated yet", 2)
                    
        self.logMsg("Stopping Service", 0)

        # If user reset library database
        WINDOW = xbmcgui.Window(10000)
        addon = xbmcaddon.Addon('plugin.video.emby')

        if WINDOW.getProperty("SyncInstallRunDone") == "false":
            # Reset the initial sync
            addon.setSetting("SyncInstallRunDone", "false")
        
        if (self.newWebSocketThread != None):
            ws.stopClient()

        if (self.newUserClient != None):
            user.stopClient()              
        
       
#start the service
Service().ServiceEntryPoint()