# -*- coding: utf-8 -*-

#################################################################################################

import os
import sys
import time
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

#################################################################################################

_addon = xbmcaddon.Addon(id='plugin.video.emby')
addon_path = _addon.getAddonInfo('path').decode('utf-8')
base_resource = xbmc.translatePath(os.path.join(addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(base_resource)

#################################################################################################

import userclient
import clientinfo
import initialsetup
import kodimonitor
import librarysync
import player
import utils
import videonodes
import websocket_client as wsc

#################################################################################################


class Service():

    welcome_msg = True
    server_online = True
    warn_auth = True

    userclient_running = False
    websocket_running = False
    library_running = False
    kodimonitor_running = False


    def __init__(self):

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        logLevel = userclient.UserClient().getLogLevel()
        self.monitor = xbmc.Monitor()

        utils.window('emby_logLevel', value=str(logLevel))
        utils.window('emby_kodiProfile', value=xbmc.translatePath("special://profile"))
        utils.window('emby_pluginpath', value=utils.settings('useDirectPaths'))

        # Initial logging
        self.logMsg("======== START %s ========" % self.addonName, 0)
        self.logMsg("Platform: %s" % (self.clientInfo.getPlatform()), 0)
        self.logMsg("KODI Version: %s" % xbmc.getInfoLabel('System.BuildVersion'), 0)
        self.logMsg("%s Version: %s" % (self.addonName, self.clientInfo.getVersion()), 0)
        self.logMsg("Using plugin paths: %s" % (utils.settings('useDirectPaths') != "true"), 0)
        self.logMsg("Log Level: %s" % logLevel, 0)

        # Reset window props for profile switch
        properties = [

            "emby_online", "emby_serverStatus", "emby_onWake",
            "emby_syncRunning", "emby_dbCheck", "emby_kodiScan",
            "emby_shouldStop", "emby_currUser", "emby_dbScan", "emby_sessionId",
            "emby_initialScan"
        ]
        for prop in properties:
            utils.window(prop, clear=True)

        # Clear playlist properties
        xbmcgui.Window(10008).clearProperties()
        # Clear video nodes properties
        videonodes.VideoNodes().clearProperties()
        
        # Set the minimum database version
        utils.window('emby_minDBVersion', value="1.1.63")

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

       
    def ServiceEntryPoint(self):
        # Important: Threads depending on abortRequest will not trigger
        # if profile switch happens more than once.
        monitor = self.monitor
        kodiProfile = xbmc.translatePath("special://profile")

        # Server auto-detect
        initialsetup.InitialSetup().setup()

        # Initialize important threads
        user = userclient.UserClient()
        ws = wsc.WebSocket_Client()
        library = librarysync.LibrarySync()
        kplayer = player.Player()
        # Sync and progress report
        lastProgressUpdate = datetime.today()

        while not monitor.abortRequested():

            if utils.window('emby_kodiProfile') != kodiProfile:
                # Profile change happened, terminate this thread and others
                self.logMsg(
                    "Kodi profile was: %s and changed to: %s. Terminating old Emby thread."
                    % (kodiProfile, utils.window('emby_kodiProfile')), 1)
                
                break
            
            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server

            if utils.window('emby_online') == "true":
                
                # Emby server is online
                # Verify if user is set and has access to the server
                if (user.currUser is not None) and user.HasAccess:

                     # If an item is playing
                    if xbmc.Player().isPlaying():
                        try:
                            # Update and report progress
                            playtime = xbmc.Player().getTime()
                            totalTime = xbmc.Player().getTotalTime()
                            currentFile = kplayer.currentFile

                            # Update positionticks
                            if kplayer.played_info.get(currentFile) is not None:
                                kplayer.played_info[currentFile]['currentPosition'] = playtime
                            
                            td = datetime.today() - lastProgressUpdate
                            secDiff = td.seconds
                            
                            # Report progress to Emby server
                            if (secDiff > 3):
                                kplayer.reportPlayback()
                                lastProgressUpdate = datetime.today()
                            
                            elif utils.window('emby_command') == "true":
                                # Received a remote control command that
                                # requires updating immediately
                                utils.window('emby_command', clear=True)
                                kplayer.reportPlayback()
                                lastProgressUpdate = datetime.today()
                            
                        except Exception as e:
                            self.logMsg("Exception in Playback Monitor Service: %s" % e, 1)
                            pass
                    else:
                        # Start up events
                        self.warn_auth = True
                        if utils.settings('connectMsg') == "true" and self.welcome_msg:
                            # Reset authentication warnings
                            self.welcome_msg = False
                            # Get additional users
                            additionalUsers = user.AdditionalUser
                            if additionalUsers:
                                add = ", %s" % ", ".join(additionalUsers)
                            else:
                                add = ""
                            xbmcgui.Dialog().notification(
                                        heading="Emby server",
                                        message="Welcome %s%s!" % (user.currUser, add),
                                        icon="special://home/addons/plugin.video.emby/icon.png",
                                        time=2000,
                                        sound=False)

                        # Start monitoring kodi events
                        if not self.kodimonitor_running:
                            self.kodimonitor_running = kodimonitor.KodiMonitor()

                        # Start the Websocket Client
                        if not self.websocket_running:
                            self.websocket_running = True
                            ws.start()
                        # Start the syncing thread
                        if not self.library_running:
                            self.library_running = True
                            library.start()
                else:
                    
                    if (user.currUser is None) and self.warn_auth:
                        # Alert user is not authenticated and suppress future warning
                        self.warn_auth = False
                        self.logMsg("Not authenticated yet.", 1)

                    # User access is restricted.
                    # Keep verifying until access is granted
                    # unless server goes offline or Kodi is shut down.
                    while user.HasAccess == False:
                        # Verify access with an API call
                        user.hasAccess()

                        if utils.window('emby_online') != "true":
                            # Server went offline
                            break

                        if monitor.waitForAbort(5):
                            # Abort was requested while waiting. We should exit
                            break
            else:
                # Wait until Emby server is online
                # or Kodi is shut down.
                while not monitor.abortRequested():
                    
                    if user.getServer() == False:
                        # No server info set in add-on settings
                        pass
                    
                    elif user.getPublicUsers() == False:
                        # Server is offline.
                        # Alert the user and suppress future warning
                        if self.server_online:
                            self.logMsg("Server is offline.", 1)
                            utils.window('emby_online', value="false")

                            xbmcgui.Dialog().notification(
                                        heading="Error connecting",
                                        message="%s Server is unreachable." % self.addonName,
                                        icon="special://home/addons/plugin.video.emby/icon.png",
                                        sound=False)
                        
                        self.server_online = False
                    
                    else:
                        # Server is online
                        if not self.server_online:
                            # Server was offline when Kodi started.
                            # Wait for server to be fully established.
                            if monitor.waitForAbort(5):
                                # Abort was requested while waiting.
                                break
                            # Alert the user that server is online.
                            xbmcgui.Dialog().notification(
                                        heading="Emby server",
                                        message="Server is online.",
                                        icon="special://home/addons/plugin.video.emby/icon.png",
                                        time=2000,
                                        sound=False)
                        
                        self.server_online = True
                        self.logMsg("Server is online and ready.", 1)
                        utils.window('emby_online', value="true")
                        
                        # Start the userclient thread
                        if not self.userclient_running:
                            self.userclient_running = True
                            user.start()
                        
                        break

                    if monitor.waitForAbort(1):
                        # Abort was requested while waiting.
                        break

            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        ##### Emby thread is terminating. #####

        if self.library_running:
            library.stopThread()

        if self.websocket_running:
            ws.stopClient()
        
        if self.userclient_running:
            user.stopClient()

        self.logMsg("======== STOP %s ========" % self.addonName, 0)

# Delay option
delay = int(utils.settings('startupDelay'))

xbmc.log("Delaying emby startup by: %s sec..." % delay)
if delay and xbmc.Monitor().waitForAbort(delay):
    # Start the service
    xbmc.log("Abort requested while waiting. Emby for kodi not started.")
else:
    Service().ServiceEntryPoint()