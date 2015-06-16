# -- coding: utf-8 --

import os
import sys
import time
from datetime import datetime

import xbmcaddon
import xbmc
import xbmcgui

addon_ = xbmcaddon.Addon()
addon_path = addon_.getAddonInfo('path').decode('utf-8')
base_resource_path = xbmc.translatePath(os.path.join(addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(base_resource_path)

import KodiMonitor
import Utils as utils
from ClientInformation import ClientInformation
from ConnectionManager import ConnectionManager
from UserClient import UserClient
from Player import Player
from WebSocketClient import WebSocketThread
from LibrarySync import LibrarySync


class Service():

    KodiMonitor = KodiMonitor.Kodi_Monitor()
    clientInfo = ClientInformation()
    librarySync = LibrarySync()

    addonName = clientInfo.getAddonName()
    logLevel = UserClient().getLogLevel()
    WINDOW = xbmcgui.Window(10000)

    newWebSocketThread = None
    newUserClient = None
    warn_auth = True
    welcome_msg = True
    server_online = True

    def __init__(self, *args):

        addonName = self.addonName
        WINDOW = self.WINDOW
        WINDOW.setProperty('getLogLevel', str(self.logLevel))

        # Initial logging
        self.logMsg("Starting Monitor", 0)
        self.logMsg("======== START %s ========" % addonName, 0)
        self.logMsg("Platform: %s" % (self.clientInfo.getPlatform()), 0)
        self.logMsg("KODI Version: %s" % xbmc.getInfoLabel('System.BuildVersion'), 0)
        self.logMsg("%s Version: %s" % (addonName, self.clientInfo.getVersion()), 0)
        self.logMsg("Log Level: %s" % self.logLevel, 1)

        # Reset window props for profile switch
        WINDOW.clearProperty('Server_online')
        WINDOW.clearProperty('Server_status')
        WINDOW.clearProperty('startup')

        embyProperty = WINDOW.getProperty('Emby.nodes.total')
        propNames = [
        
            "index","path","title","content",
            "inprogress.content","inprogress.title",
            "inprogress.content","inprogress.path",
            "nextepisodes.title","nextepisodes.content",
            "nextepisodes.path","unwatched.title",
            "unwatched.content","unwatched.path",
            "recent.title","recent.content","recent.path",
            "recentepisodes.title","recentepisodes.content",
            "recentepisodes.path","inprogressepisodes.title",
            "inprogressepisodes.content","inprogressepisodes.path"
        ]

        if embyProperty:
            totalNodes = int(embyProperty)
            for i in range(totalNodes):
                for prop in propNames:
                    WINDOW.clearProperty('Emby.nodes.%s.%s' % (str(i), prop))

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))
       
    def ServiceEntryPoint(self):
        
        WINDOW = self.WINDOW
        addon = xbmcaddon.Addon()
        
        # Server auto-detect
        ConnectionManager().checkServer()

        # Initialize important threads
        user = UserClient()
        player = Player()
        ws = WebSocketThread()

        # Sync and progress report
        startupComplete = False
        lastProgressUpdate = datetime.today()

        while not self.KodiMonitor.abortRequested():

            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server
            
            if WINDOW.getProperty('Server_online') == "true":
                
                # Emby server is online
                # Verify if user is set and has access to the server
                if (user.currUser != None) and user.HasAccess:
                    
                    self.warn_auth = True
                    if addon.getSetting('supressConnectMsg') == "false":
                        if self.welcome_msg:
                            # Reset authentication warnings
                            self.welcome_msg = False
                            xbmcgui.Dialog().notification("Emby server", "Welcome %s!" % user.currUser, time=2000, sound=False)

                    # Start the Websocket Client
                    if (self.newWebSocketThread == None):
                        self.newWebSocketThread = "Started"
                        ws.start()

                    # If an item is playing
                    if xbmc.Player().isPlaying():
                        try:
                            # Update and report progress
                            playTime = xbmc.Player().getTime()
                            totalTime = xbmc.Player().getTotalTime()
                            currentFile = xbmc.Player().getPlayingFile()

                            # Update positionticks
                            if player.played_information.get(currentFile) != None:
                                player.played_information[currentFile]["currentPosition"] = playTime
                            
                            td = datetime.today() - lastProgressUpdate
                            secDiff = td.seconds
                            
                            # Report progress to Emby server
                            if (secDiff > 3):
                                try:
                                    player.reportPlayback()
                                except Exception as msg:
                                    self.logMsg("Exception reporting progress: %s" % msg)
                                    pass
                                lastProgressUpdate = datetime.today()
                            
                            elif WINDOW.getProperty('commandUpdate') == "true":
                                # Received a remote control command that
                                # requires updating immediately
                                try:
                                    WINDOW.clearProperty('commandUpdate')
                                    player.reportPlayback()
                                except: pass
                                lastProgressUpdate = datetime.today()
                            
                        except Exception as e:
                            self.logMsg("Exception in Playback Monitor Service: %s" % e)
                            pass

                    else:
                        # Library sync
                        if not startupComplete:
                            # Run full sync
                            self.logMsg("Doing_Db_Sync: syncDatabase (Started)", 1)
                            libSync = self.librarySync.FullLibrarySync()
                            self.logMsg("Doing_Db_Sync: syncDatabase (Finished) %s" % libSync, 1)

                            if libSync:
                                startupComplete = True

                else:
                    
                    if (user.currUser == None) and self.warn_auth:
                        # Alert user is not authenticated and suppress future warning
                        self.warn_auth = False
                        self.logMsg("Not authenticated yet.", 1)

                    # User access is restricted.
                    # Keep verifying until access is granted
                    # unless server goes offline or Kodi is shut down.
                    while user.HasAccess == False:
                        # Verify access with an API call
                        user.hasAccess()

                        if WINDOW.getProperty('Server_online') != "true":
                            # Server went offline
                            break

                        if self.KodiMonitor.waitForAbort(5):
                            # Abort was requested while waiting. We should exit
                            break

            else:
                # Wait until Emby server is online
                # or Kodi is shut down.
                while not self.KodiMonitor.abortRequested():
                    
                    if user.getServer() == "":
                        # No server info set in add-on settings
                        pass
                    
                    elif user.getPublicUsers() == False:
                        # Server is offline.
                        # Alert the user and suppress future warning
                        if self.server_online:
                            self.logMsg("Server is offline.", 1)
                            WINDOW.setProperty('Server_online', "false")
                            xbmcgui.Dialog().notification("Error connecting", "%s Server is unreachable." % self.addonName, sound=False)
                        self.server_online = False
                    
                    else:
                        # Server is online
                        if not self.server_online:
                            # Server was offline when Kodi started.
                            # Wait for server to be fully established.
                            if self.KodiMonitor.waitForAbort(5):
                                # Abort was requested while waiting.
                                break
                            # Alert the user that server is online.
                            xbmcgui.Dialog().notification("Connection successful", "%s Server is online." % self.addonName, time=2000, sound=False)
                        
                        self.server_online = True
                        self.logMsg("Server is online and ready.", 1)
                        WINDOW.setProperty('Server_online', "true")
                        
                        # Start the User client
                        if self.newUserClient == None:
                            self.newUserClient = "Started"
                            user.start()
                        break

                    if self.KodiMonitor.waitForAbort(1):
                        # Abort was requested while waiting.
                        break

            if self.KodiMonitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        # If user reset library database.
        if WINDOW.getProperty('SyncInstallRunDone') == "false":
            addon = xbmcaddon.Addon()
            addon.setSetting('SyncInstallRunDone', "false")
        
        if (self.newWebSocketThread != None):
            ws.stopClient()

        if (self.newUserClient != None):
            user.stopClient()

        self.logMsg("======== STOP %s ========" % self.addonName, 0)

#start the service
Service().ServiceEntryPoint()