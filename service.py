import xbmcaddon
import xbmc
import xbmcgui
import os
import threading
import json
from datetime import datetime
import time

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
from PlaybackUtils import PlaybackUtils
librarySync = LibrarySync()


class Service():
    

    newWebSocketThread = None
    newUserClient = None

    clientInfo = ClientInformation()
    addonName = clientInfo.getAddonName()
    WINDOW = xbmcgui.Window(10000)

    warn_auth = True
    server_online = True
    
    def __init__(self, *args ):
        self.KodiMonitor = KodiMonitor.Kodi_Monitor()
        addonName = self.addonName

        self.logMsg("Starting Monitor", 0)
        self.logMsg("======== START %s ========" % addonName, 0)
        self.logMsg("KODI Version: %s" % xbmc.getInfoLabel("System.BuildVersion"), 0)
        self.logMsg("%s Version: %s" % (addonName, self.clientInfo.getVersion()), 0)
        self.logMsg("Platform: %s" % (self.clientInfo.getPlatform()), 0)
        
        #reset all window props on startup for user profile switches
        self.WINDOW.clearProperty("startup")
        embyProperty = self.WINDOW.getProperty("Emby.nodes.total")
        propNames = ["index","path","title","content","inprogress.content","inprogress.title","inprogress.content","inprogress.path","nextepisodes.title","nextepisodes.content","nextepisodes.path","unwatched.title","unwatched.content","unwatched.path","recent.title","recent.content","recent.path","recentepisodes.title","recentepisodes.content","recentepisodes.path","inprogressepisodes.title","inprogressepisodes.content","inprogressepisodes.path"]
        if embyProperty:
            totalNodes = int(embyProperty)
            for i in range(totalNodes):
                for prop in propNames:
                    self.WINDOW.clearProperty("Emby.nodes.%s.%s" %(str(i),prop))


    def logMsg(self, msg, lvl=1):
        
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), str(msg), int(lvl))
            
    def ServiceEntryPoint(self):
        
        WINDOW = self.WINDOW
        WINDOW.setProperty("Server_online", "")
        self.WINDOW.setProperty("Server_status", "")
        WINDOW.setProperty("Emby_Service_Timestamp", str(int(time.time())))
        
        ConnectionManager().checkServer()
        lastProgressUpdate = datetime.today()
        startupComplete = False
        
        user = UserClient()
        player = Player()
        ws = WebSocketThread()
        
        lastFile = None
        
        while not self.KodiMonitor.abortRequested():
            WINDOW.setProperty("Emby_Service_Timestamp", str(int(time.time())))
                     
            if self.KodiMonitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

            if WINDOW.getProperty('Server_online') == "true":
                # Server is online
                if (user.currUser != None) and (user.HasAccess == True):
                    self.warn_auth = True

                    # Correctly launch the websocket, if user manually launches the add-on
                    if (self.newWebSocketThread == None):
                        self.newWebSocketThread = "Started"
                        ws.start()

                    if xbmc.Player().isPlaying():
                        WINDOW.setProperty("Emby_Service_Timestamp", str(int(time.time())))
                        try:
                            playTime = xbmc.Player().getTime()
                            totalTime = xbmc.Player().getTotalTime()
                            currentFile = xbmc.Player().getPlayingFile()

                            if(player.played_information.get(currentFile) != None):
                                player.played_information[currentFile]["currentPosition"] = playTime
                            
                            # send update
                            td = datetime.today() - lastProgressUpdate
                            secDiff = td.seconds
                            if(secDiff > 3):
                                try:
                                    player.reportPlayback()
                                except Exception, msg:
                                    self.logMsg("Exception reporting progress: %s" % msg)
                                    pass
                                lastProgressUpdate = datetime.today()
                            elif WINDOW.getProperty('commandUpdate') == "true":
                                try:
                                    WINDOW.clearProperty('commandUpdate')
                                    player.reportPlayback()
                                except: pass
                                lastProgressUpdate = datetime.today()
                            # only try autoplay when there's 20 seconds or less remaining and only once!
                            addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
                          
                            # if its an episode see if autoplay is enabled
                            if addonSettings.getSetting("autoPlaySeason")=="true":
                                notificationtime = addonSettings.getSetting("autoPlaySeasonTime")
                                if (totalTime - playTime <= int(notificationtime) and (lastFile==None or lastFile!=currentFile)):
                                    lastFile = currentFile
                                    player.autoPlayPlayback()
                            
                        except Exception, e:
                            self.logMsg("Exception in Playback Monitor Service: %s" % e)
                            pass

                    else:
                        WINDOW.setProperty("Emby_Service_Timestamp", str(int(time.time())))
                        #full sync
                        if (startupComplete == False):
                            self.logMsg("Doing_Db_Sync: syncDatabase (Started)")
                            libSync = librarySync.FullLibrarySync()
                            self.logMsg("Doing_Db_Sync: syncDatabase (Finished) " + str(libSync))

                            if (libSync):
                                startupComplete = True
                        else:
                            if self.KodiMonitor.waitForAbort(1):
                                # Abort was requested while waiting. We should exit
                                break    
                else:
                    
                    if self.warn_auth:
                        self.logMsg("Not authenticated yet.", 1)
                        self.warn_auth = False

                    while user.HasAccess == False:

                        WINDOW.setProperty("Emby_Service_Timestamp", str(int(time.time())))
                        user.hasAccess()

                        if WINDOW.getProperty('Server_online') != "true":
                            # Server went offline
                            break

                        if self.KodiMonitor.waitForAbort(5):
                            # Abort was requested while waiting. We should exit
                            break


            else:
                # Wait until server becomes online or shut down is requested
                while not self.KodiMonitor.abortRequested():
                    WINDOW.setProperty("Emby_Service_Timestamp", str(int(time.time())))
                    
                    if user.getServer() == "":
                        pass
                    elif user.getPublicUsers() == False:
                        # Server is not online, suppress future warning
                        if self.server_online:
                            WINDOW.setProperty("Server_online", "false")
                            self.logMsg("Server is offline.", 1)
                            xbmcgui.Dialog().notification("Error connecting", "%s Server is unreachable." % self.addonName)
                        self.server_online = False
                    else:
                        # Server is online
                        if not self.server_online:
                            # Server was not online when Kodi started.
                            # Wait for server to be fully established.
                            if self.KodiMonitor.waitForAbort(5):
                                # Abort was requested while waiting.
                                break
                        self.server_online = True
                        self.logMsg("Server is online and ready.", 1)
                        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
                        if addonSettings.getSetting("supressConnectMsg")=="false":
                            xbmcgui.Dialog().notification("Connection successful", "%s Server is online." % self.addonName, time=2000)
                        WINDOW.setProperty("Server_online", "true")
                        
                        # Server is online, proceed.
                        if (self.newUserClient == None):
                            self.newUserClient = "Started"
                            user.start()
                        break

                    if self.KodiMonitor.waitForAbort(1):
                        # Abort was requested while waiting.
                        break

        # If user reset library database.
        if WINDOW.getProperty("SyncInstallRunDone") == "false":
            addon = xbmcaddon.Addon('plugin.video.emby')
            addon.setSetting("SyncInstallRunDone", "false")
        
        if (self.newWebSocketThread != None):
            ws.stopClient()

        if (self.newUserClient != None):
            user.stopClient()

        self.logMsg("======== STOP %s ========" % self.addonName, 0)
       
#start the service
Service().ServiceEntryPoint()
