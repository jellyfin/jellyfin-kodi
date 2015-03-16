import xbmcaddon
import xbmc
import xbmcgui
import os
import threading
import json
from datetime import datetime


addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
cwd = addonSettings.getAddonInfo('path')
BASE_RESOURCE_PATH = xbmc.translatePath( os.path.join( cwd, 'resources', 'lib' ) )
sys.path.append(BASE_RESOURCE_PATH)

WINDOW = xbmcgui.Window( 10000 )

import KodiMonitor
import Utils as utils
from LibrarySync import LibrarySync
from Player import Player
from DownloadUtils import DownloadUtils
from ConnectionManager import ConnectionManager
librarySync = LibrarySync()

class Service():

    
    def __init__(self, *args ):
        self.KodiMonitor = KodiMonitor.Kodi_Monitor()

        utils.logMsg("MB3 Sync Service" "starting Monitor",0)
        
        pass  
    
            
    def ServiceEntryPoint(self):
        
        ConnectionManager().checkServer()
        
        player = Player()
        lastProgressUpdate = datetime.today()
        
        #perform kodi cleanup (needed while testing, can be removed later if needed)
        utils.doKodiCleanup()
        
        # check kodi library sources
        utils.checkKodiSources()
        
        interval_FullSync = 120
        interval_IncrementalSync = 30
        
        cur_seconds_fullsync = interval_FullSync
        cur_seconds_incrsync = interval_IncrementalSync
        
        while not xbmc.abortRequested:
            
            xbmc.sleep(1000)
            
            if xbmc.Player().isPlaying():
                try:
                    playTime = xbmc.Player().getTime()
                    currentFile = xbmc.Player().getPlayingFile()
                    
                    if(player.played_information.get(currentFile) != None):
                        player.played_information[currentFile]["currentPossition"] = playTime
                    
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
                    
                except Exception, e:
                    xbmc.log("MB3 Sync Service -> Exception in Playback Monitor Service : " + str(e))
                    pass
            else:
                # background worker for database sync
                if DownloadUtils().authenticate(retreive=False) != "":
            
                    #full sync
                    if(cur_seconds_fullsync >= interval_FullSync):
                        xbmc.log("Doing_Db_Sync: syncDatabase (Started)")
                        worked = librarySync.syncDatabase()
                        xbmc.log("Doing_Db_Sync: syncDatabase (Finished) " + str(worked))
                        if(worked):
                            cur_seconds_fullsync = 0
                        else:
                            cur_seconds_fullsync = interval_FullSync - 10
                    else:
                        cur_seconds_fullsync += 1
                    
                    #incremental sync
                    if(cur_seconds_incrsync >= interval_IncrementalSync):
                        xbmc.log("Doing_Db_Sync: updatePlayCounts (Started)")
                        worked = librarySync.updatePlayCounts()
                        xbmc.log("Doing_Db_Sync: updatePlayCounts (Finished) "  + str(worked))
                        if(worked):
                            cur_seconds_incrsync = 0
                        else:
                            cur_seconds_incrsync = interval_IncrementalSync - 10
                    else:
                        cur_seconds_incrsync += 1
                else:
                    xbmc.log("Not authenticated yet")
                    
        utils.logMsg("MB3 Sync Service" "stopping Service",0)
        
       
#start the service
Service().ServiceEntryPoint()
