# -*- coding: utf-8 -*-

import json
import threading
import websocket
import logging

#################################################################################################
# WebSocket Client thread
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon

import KodiMonitor
import Utils as utils
from ClientInformation import ClientInformation
from DownloadUtils import DownloadUtils
from PlaybackUtils import PlaybackUtils
from LibrarySync import LibrarySync
from WriteKodiVideoDB import WriteKodiVideoDB
from WriteKodiMusicDB import WriteKodiMusicDB

logging.basicConfig()


class WebSocketThread(threading.Thread):

    _shared_state = {}

    doUtils = DownloadUtils()
    clientInfo = ClientInformation()
    KodiMonitor = KodiMonitor.Kodi_Monitor()

    addonName = clientInfo.getAddonName()

    client = None
    keepRunning = True
    
    def __init__(self, *args):

        self.__dict__ = self._shared_state
        threading.Thread.__init__(self, *args)
    
    def logMsg(self, msg, lvl=1):

        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))
    
    def sendProgressUpdate(self, data):
        self.logMsg("sendProgressUpdate", 1)
        if self.client:
            try:
                # Send progress update
                messageData = {
                    'MessageType': "ReportPlaybackProgress",
                    'Data': data
                }
                messageString = json.dumps(messageData)
                self.client.send(messageString)
                self.logMsg("Message data: %s" % messageString, 2)
            except Exception as e:
                self.logMsg("Exception: %s" % e, 1)  
    
    def stopClient(self):
        # stopping the client is tricky, first set keep_running to false and then trigger one 
        # more message by requesting one SessionsStart message, this causes the 
        # client to receive the message and then exit
        if self.client:
            self.logMsg("Stopping Client")
            self.keepRunning = False
            self.client.keep_running = False            
            self.client.close() 
            self.logMsg("Stopping Client : KeepRunning set to False")
        else:
            self.logMsg("Stopping Client NO Object ERROR")
            
    def on_message(self, ws, message):

        WINDOW = xbmcgui.Window(10000)
        addon = xbmcaddon.Addon()
        self.logMsg("Message: %s" % message, 1)
        
        result = json.loads(message)
        messageType = result['MessageType']
        data = result.get("Data")

        if messageType == "Play":
            # A remote control play command has been sent from the server.
            itemIds = data['ItemIds']
            playCommand = data['PlayCommand']

            if "PlayNow" in playCommand:
                startPositionTicks = data.get('StartPositionTicks', 0)
                xbmc.executebuiltin("Dialog.Close(all,true)")
                xbmc.executebuiltin("XBMC.Notification(Playlist: Added %s items to Playlist,)" % len(itemIds))
                PlaybackUtils().PLAYAllItems(itemIds, startPositionTicks)

            elif "PlayNext" in playCommand:
                xbmc.executebuiltin("XBMC.Notification(Playlist: Added %s items to Playlist,)" % len(itemIds))
                playlist = PlaybackUtils().AddToPlaylist(itemIds)
                if not xbmc.Player().isPlaying():
                    xbmc.Player().play(playlist)
               
        elif messageType == "Playstate":
            # A remote control update playstate command has been sent from the server.
            command = data['Command']

            if "Stop" in command:
                self.logMsg("Playback Stopped.", 1)
                xbmc.Player().stop()
            elif "Unpause" in command:
                self.logMsg("Playback unpaused.", 1)
                xbmc.Player().pause()
            elif "Pause" in command:
                self.logMsg("Playback paused.", 1)
                xbmc.Player().pause()
            elif "NextTrack" in command:
                self.logMsg("Playback next track.", 1)
                xbmc.Player().playnext()
            elif "PreviousTrack" in command:
                self.logMsg("Playback previous track.", 1)
                xbmc.Player().playprevious()
            elif "Seek" in command:
                seekPositionTicks = data['SeekPositionTicks']
                seekTime = seekPositionTicks / 10000000.0
                self.logMsg("Seek to %s" % seekTime, 1)
                xbmc.Player().seekTime(seekTime)
            # Report playback
            WINDOW.setProperty('commandUpdate', "true")

        elif messageType == "UserDataChanged":
            # A user changed their personal rating for an item, or their playstate was updated
            userdataList = data['UserDataList']
            self.logMsg("Message: Doing UserDataChanged: UserDataList: %s" % userdataList, 1)
            LibrarySync().user_data_update(userdataList)

        elif messageType == "LibraryChanged":
            # Library items
            itemsRemoved = data.get("ItemsRemoved")
            itemsAdded = data.get("ItemsAdded")
            itemsUpdated = data.get("ItemsUpdated")
            itemsToUpdate = itemsAdded + itemsUpdated

            self.logMsg("Message: WebSocket LibraryChanged: Items Added: %s" % itemsAdded, 1)
            self.logMsg("Message: WebSocket LibraryChanged: Items Updated: %s" % itemsUpdated, 1)
            self.logMsg("Message: WebSocket LibraryChanged: Items Removed: %s" % itemsRemoved, 1)

            LibrarySync().remove_items(itemsRemoved)
            LibrarySync().update_items(itemsToUpdate)

        elif messageType == "GeneralCommand":
            
            command = data['Name']
            arguments = data.get("Arguments")

            if command in ('Mute', 'Unmute', 'SetVolume', 'SetSubtitleStreamIndex', 'SetAudioStreamIndex'):
                # These commands need to be reported back
                if command == "Mute":
                    xbmc.executebuiltin('Mute')
                elif command == "Unmute":
                    xbmc.executebuiltin('Mute')
                elif command == "SetVolume":
                    volume = arguments['Volume']
                    xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % volume)
                elif command == "SetSubtitleStreamIndex":
                    # Emby merges audio and subtitle index together
                    audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                    index = int(arguments['Index']) - audioTracks
                    xbmc.Player().setSubtitleStream(index - 1)
                elif command == "SetAudioStreamIndex":
                    index = int(arguments['Index'])
                    xbmc.Player().setAudioStream(index - 1)
                # Report playback
                WINDOW.setProperty('commandUpdate', "true")

            else:
                # GUI commands
                if command == "ToggleFullscreen":
                    xbmc.executebuiltin('Action(FullScreen)')
                elif command == "ToggleOsdMenu":
                    xbmc.executebuiltin('Action(OSD)')
                elif command == "MoveUp":
                    xbmc.executebuiltin('Action(Up)')
                elif command == "MoveDown":
                    xbmc.executebuiltin('Action(Down)')
                elif command == "MoveLeft":
                    xbmc.executebuiltin('Action(Left)')
                elif command == "MoveRight":
                    xbmc.executebuiltin('Action(Right)')
                elif command == "Select":
                    xbmc.executebuiltin('Action(Select)')
                elif command == "Back":
                    xbmc.executebuiltin('Action(back)')
                elif command == "ToggleContextMenu":
                    xbmc.executebuiltin('Action(ContextMenu)')
                elif command == "GoHome":
                    xbmc.executebuiltin('ActivateWindow(Home)')
                elif command == "PageUp":
                    xbmc.executebuiltin('Action(PageUp)')
                elif command == "NextLetter":
                    xbmc.executebuiltin('Action(NextLetter)')
                elif command == "GoToSearch":
                    xbmc.executebuiltin('VideoLibrary.Search')
                elif command == "GoToSettings":
                    xbmc.executebuiltin('ActivateWindow(Settings)')
                elif command == "PageDown":
                    xbmc.executebuiltin('Action(PageDown)')
                elif command == "PreviousLetter":
                    xbmc.executebuiltin('Action(PrevLetter)')
                elif command == "TakeScreenshot":
                    xbmc.executebuiltin('TakeScreenshot')
                elif command == "ToggleMute":
                    xbmc.executebuiltin('Mute')
                elif command == "VolumeUp":
                    xbmc.executebuiltin('Action(VolumeUp)')
                elif command == "VolumeDown":
                    xbmc.executebuiltin('Action(VolumeDown)')
                elif command == "DisplayMessage":
                    header = arguments['Header']
                    text = arguments['Text']
                    xbmcgui.Dialog().notification(header, text, icon="special://home/addons/plugin.video.emby/icon.png", time=4000)
                elif command == "SendString":
                    string = arguments['String']
                    text = '{"jsonrpc": "2.0", "method": "Input.SendText",  "params": { "text": "%s", "done": false }, "id": 0}' % string
                    result = xbmc.executeJSONRPC(text)
                else:
                    self.logMsg("Unknown command.", 1)

        elif messageType == "ServerRestarting":
            if addon.getSetting('supressRestartMsg') == "true":
                xbmcgui.Dialog().notification("Emby server", "Server is restarting.", icon="special://home/addons/plugin.video.emby/icon.png")

    def on_error(self, ws, error):
        if "10061" in str(error):
            # Server is offline
            pass
        else:
            self.logMsg("Error: %s" % error, 1)
        #raise

    def on_close(self, ws):
        self.logMsg("Closed", 2)

    def on_open(self, ws):
        deviceId = ClientInformation().getMachineId()
        self.doUtils.postCapabilities(deviceId)

    def run(self):
        
        WINDOW = xbmcgui.Window(10000)
        logLevel = int(WINDOW.getProperty('getLogLevel'))
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)
        token = WINDOW.getProperty('accessToken%s' % username)
        deviceId = ClientInformation().getMachineId()

        '''if (logLevel == 2):
            websocket.enableTrace(True)'''

        # Get the appropriate prefix for websocket
        if "https" in server:
            server = server.replace('https', 'wss')
        else:
            server = server.replace('http', 'ws')
        
        websocketUrl = "%s?api_key=%s&deviceId=%s" % (server, token, deviceId)
        self.logMsg("websocket URL: %s" % websocketUrl)

        self.client = websocket.WebSocketApp(websocketUrl,
                                    on_message = self.on_message,
                                    on_error = self.on_error,
                                    on_close = self.on_close)
                                    
        self.client.on_open = self.on_open
        
        while self.keepRunning:
            
            self.client.run_forever()

            if self.keepRunning:
                self.logMsg("Client Needs To Restart", 2)
                if self.KodiMonitor.waitForAbort(5):
                    break
            
        self.logMsg("Thread Exited", 1)