# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sys
import _strptime # Workaround for threads using datetime: _striptime is locked
from datetime import datetime

import xbmc

import userclient
import clientinfo
import initialsetup
import kodimonitor
import librarysync
import player
import videonodes
import websocket_client as wsc
from utils import window, settings, dialog, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Service(object):

    welcome_msg = True
    server_online = True
    warn_auth = True

    userclient_running = False
    userclient_thread = None

    websocket_running = False
    websocket_thread = None

    library_running = False
    library_thread = None

    monitor = False


    def __init__(self):

        self.client_info = clientinfo.ClientInfo()
        self.addon_name = self.client_info.get_addon_name()
        log_level = settings('logLevel')

        window('emby_logLevel', value=str(log_level))
        window('emby_kodiProfile', value=xbmc.translatePath('special://profile'))
        context_menu = "true" if settings('enableContext') == "true" else ""
        window('emby_context', value=context_menu)

        # Initial logging
        log.warn("======== START %s ========", self.addon_name)
        log.warn("Python Version: %s", sys.version)
        log.warn("Platform: %s", self.client_info.get_platform())
        log.warn("KODI Version: %s", xbmc.getInfoLabel('System.BuildVersion'))
        log.warn("%s Version: %s", self.addon_name, self.client_info.get_version())
        log.warn("Using plugin paths: %s", settings('useDirectPaths') == "0")
        log.warn("Log Level: %s", log_level)

        # Reset window props for profile switch
        properties = [

            "emby_online", "emby_serverStatus", "emby_onWake",
            "emby_syncRunning", "emby_dbCheck", "emby_kodiScan",
            "emby_shouldStop", "emby_currUser", "emby_dbScan", "emby_sessionId",
            "emby_initialScan", "emby_customplaylist", "emby_playbackProps"
        ]
        for prop in properties:
            window(prop, clear=True)

        # Clear video nodes properties
        videonodes.VideoNodes().clearProperties()

        # Set the minimum database version
        window('emby_minDBVersion', value="1.1.63")


    def service_entry_point(self):

        # Important: Threads depending on abortRequest will not trigger
        # if profile switch happens more than once.
        self.monitor = kodimonitor.KodiMonitor()
        kodiProfile = xbmc.translatePath('special://profile')

        # Server auto-detect
        initialsetup.InitialSetup().setup()

        # Initialize important threads
        self.userclient_thread = userclient.UserClient()
        self.websocket_thread = wsc.WebSocketClient()
        self.library_thread = librarysync.LibrarySync()
        kplayer = player.Player()
        # Sync and progress report
        lastProgressUpdate = datetime.today()

        while not self.monitor.abortRequested():

            if window('emby_kodiProfile') != kodiProfile:
                # Profile change happened, terminate this thread and others
                log.info("Kodi profile was: %s and changed to: %s. Terminating old Emby thread.",
                         kodiProfile, window('emby_kodiProfile'))
                break

            # Before proceeding, need to make sure:
            # 1. Server is online
            # 2. User is set
            # 3. User has access to the server

            if window('emby_online') == "true":

                # Emby server is online
                # Verify if user is set and has access to the server
                if self.userclient_thread.get_user() is not None and self.userclient_thread.get_access():

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
                            
                            elif window('emby_command') == "true":
                                # Received a remote control command that
                                # requires updating immediately
                                window('emby_command', clear=True)
                                kplayer.reportPlayback()
                                lastProgressUpdate = datetime.today()
                            
                        except Exception:
                            log.exception("Exception in Playback Monitor Service")
                    else:
                        # Start up events
                        self.warn_auth = True
                        if settings('connectMsg') == "true" and self.welcome_msg:
                            # Reset authentication warnings
                            self.welcome_msg = False
                            # Get additional users
                            additionalUsers = settings('additionalUsers')
                            if additionalUsers:
                                add = ", %s" % ", ".join(additionalUsers.split(','))
                            else:
                                add = ""
                            dialog(type_="notification",
                                   heading="{emby}",
                                   message=("%s %s%s!"
                                            % (lang(33000), self.userclient_thread.get_username().decode('utf-8'),
                                               add.decode('utf-8'))),
                                   icon="{emby}",
                                   time=2000,
                                   sound=False)

                        # Start the Websocket Client
                        if not self.websocket_running:
                            self.websocket_running = True
                            self.websocket_thread.start()
                        # Start the syncing thread
                        if not self.library_running:
                            self.library_running = True
                            self.library_thread.start()
                else:
                    
                    if (self.userclient_thread.get_user() is None) and self.warn_auth:
                        # Alert user is not authenticated and suppress future warning
                        self.warn_auth = False
                        log.info("Not authenticated yet.")

                    # User access is restricted.
                    # Keep verifying until access is granted
                    # unless server goes offline or Kodi is shut down.
                    while not self.userclient_thread.get_access():
                        # Verify access with an API call

                        if window('emby_online') != "true":
                            # Server went offline
                            break

                        if self.monitor.waitForAbort(5):
                            # Abort was requested while waiting. We should exit
                            break
            else:
                # Wait until Emby server is online
                # or Kodi is shut down.
                self._server_online_check()


            if self.monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        ##### Emby thread is terminating. #####
        self._shutdown()

    def _server_online_check(self):
        # Set emby_online true/false property
        user = self.userclient_thread
        while not self.monitor.abortRequested():
            
            if user.get_server() is None:
                # No server info set in add-on settings
                pass
            
            elif not user.verify_server():
                # Server is offline.
                # Alert the user and suppress future warning
                if self.server_online:
                    log.info("Server is offline")
                    window('emby_online', value="false")

                    if settings('offlineMsg') == "true":
                        dialog(type_="notification",
                               heading=lang(33001),
                               message="%s %s" % (self.addon_name, lang(33002)),
                               icon="{emby}",
                               sound=False)

                self.server_online = False

            elif window('emby_online') == "sleep":
                # device going to sleep
                if self.websocket_running:
                    self.websocket_thread.stop_client()
                    self.websocket_thread = wsc.WebSocketClient()
                    self.websocket_running = False

                if self.library_running:
                    self.library_thread.stopThread()
                    self.library_thread = librarysync.LibrarySync()
                    self.library_running = False

            else:
                # Server is online
                if not self.server_online:
                    # Server was offline when Kodi started.
                    # Wait for server to be fully established.
                    if self.monitor.waitForAbort(5):
                        # Abort was requested while waiting.
                        break
                    # Alert the user that server is online.
                    dialog(type_="notification",
                           heading="{emby}",
                           message=lang(33003),
                           icon="{emby}",
                           time=2000,
                           sound=False)

                self.server_online = True
                window('emby_online', value="true")
                log.info("Server is online and ready")

                # Start the userclient thread
                if not self.userclient_running:
                    self.userclient_running = True
                    user.start()

                break

            if self.monitor.waitForAbort(1):
                # Abort was requested while waiting.
                break

    def _shutdown(self):

        if self.userclient_running:
            self.userclient_thread.stop_client()

        if self.library_running:
            self.library_thread.stopThread()

        if self.websocket_running:
            self.websocket_thread.stop_client()

        log.warn("======== STOP %s ========", self.addon_name)
