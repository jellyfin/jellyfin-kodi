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
    addonName = None
    className = None
    
    def __init__(self, *args ):
        self.KodiMonitor = KodiMonitor.Kodi_Monitor()
        self.addonName = self.clientInfo.getAddonName()
        self.className = self.__class__.__name__

        self.logMsg("Starting Monitor", 0)
        self.logMsg("======== START %s ========" % self.addonName, 0)
        self.logMsg("KODI Version: %s" % xbmc.getInfoLabel("System.BuildVersion"), 0)
        self.logMsg("%s Version: %s" % (self.addonName, self.clientInfo.getVersion()), 0)
        pass

    def logMsg(self, msg, lvl=1):
        addonName = self.addonName
        className = self.className

        utils.logMsg("%s %s" % (addonName, className), str(msg), int(lvl))
               
    def ServiceEntryPoint(self):
        
        ConnectionManager().checkServer()
        
        lastProgressUpdate = datetime.today()
        
        interval_FullSync = 600
        interval_IncrementalSync = 300
        
        cur_seconds_fullsync = interval_FullSync
        cur_seconds_incrsync = interval_IncrementalSync
        
        user = UserClient()
        player = Player()
        ws = WebSocketThread()
        
        while not self.KodiMonitor.abortRequested():
            
            xbmc.sleep(1000)
            
            if xbmc.Player().isPlaying():
                try:
                    playTime = xbmc.Player().getTime()
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
                            self.logMsg("Exception reporting progress: %s" % msg)
                            pass
                        lastProgressUpdate = datetime.today()
                    
                except Exception, e:
                    self.logMsg("Exception in Playback Monitor Service: %s" % e)
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
                    if(cur_seconds_fullsync >= interval_FullSync):
                        self.logMsg("Doing_Db_Sync: syncDatabase (Started)")
                        worked = librarySync.syncDatabase()
                        self.logMsg("Doing_Db_Sync: syncDatabase (Finished) %s" % worked)
                        if(worked):
                            cur_seconds_fullsync = 0
                        else:
                            cur_seconds_fullsync = interval_FullSync - 10
                    else:
                        cur_seconds_fullsync += 1
                    
                    #incremental sync
                    if(cur_seconds_incrsync >= interval_IncrementalSync):
                        self.logMsg("Doing_Db_Sync: updatePlayCounts (Started)")
                        worked = librarySync.updatePlayCounts()
                        self.logMsg("Doing_Db_Sync: updatePlayCounts (Finished) %s" % worked)
                        if(worked):
                            cur_seconds_incrsync = 0
                        else:
                            cur_seconds_incrsync = interval_IncrementalSync - 10
                    else:
                        cur_seconds_incrsync += 1
              
                    
                else:
                    self.logMsg("Not authenticated yet")
                    
        self.logMsg("Stopping Service", 0)
        
        if (self.newWebSocketThread != None):
            ws.stopClient()

        if (self.newUserClient != None):
            user.stopClient()              
        
       
#start the service
Service().ServiceEntryPoint()