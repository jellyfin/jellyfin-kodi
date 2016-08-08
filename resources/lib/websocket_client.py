# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import threading
import websocket

import xbmc
import xbmcgui

import clientinfo
import downloadutils
import librarysync
import playlist
import userclient
from utils import window, settings, language as lang, JSONRPC

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class WebSocket_Client(threading.Thread):

    _shared_state = {}

    client = None
    stopWebsocket = False


    def __init__(self):

        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()
        
        self.doUtils = downloadutils.DownloadUtils()
        self.clientInfo = clientinfo.ClientInfo()
        self.deviceId = self.clientInfo.getDeviceId()
        self.librarySync = librarysync.LibrarySync()
        
        threading.Thread.__init__(self)


    def sendProgressUpdate(self, data):
        
        log.debug("sendProgressUpdate")
        try:
            messageData = {

                'MessageType': "ReportPlaybackProgress",
                'Data': data
            }
            messageString = json.dumps(messageData)
            self.client.send(messageString)
            log.debug("Message data: %s" % messageString)

        except Exception as e:
            log.exception(e)

    def on_message(self, ws, message):

        result = json.loads(message)
        messageType = result['MessageType']
        data = result['Data']
        dialog = xbmcgui.Dialog()

        if messageType not in ('SessionEnded'):
            # Mute certain events
            log.info("Message: %s" % message)

        if messageType == "Play":
            # A remote control play command has been sent from the server.
            itemIds = data['ItemIds']
            command = data['PlayCommand']

            pl = playlist.Playlist()

            if command == "PlayNow":
                dialog.notification(
                        heading=lang(29999),
                        message="%s %s" % (len(itemIds), lang(33004)),
                        icon="special://home/addons/plugin.video.emby/icon.png",
                        sound=False)
                startat = data.get('StartPositionTicks', 0)
                pl.playAll(itemIds, startat)

            elif command == "PlayNext":
                dialog.notification(
                        heading=lang(29999),
                        message="%s %s" % (len(itemIds), lang(33005)),
                        icon="special://home/addons/plugin.video.emby/icon.png",
                        sound=False)
                newplaylist = pl.modifyPlaylist(itemIds)
                player = xbmc.Player()
                if not player.isPlaying():
                    # Only start the playlist if nothing is playing
                    player.play(newplaylist)

        elif messageType == "Playstate":
            # A remote control update playstate command has been sent from the server.
            command = data['Command']
            player = xbmc.Player()

            actions = {

                'Stop': player.stop,
                'Unpause': player.pause,
                'Pause': player.pause,
                'NextTrack': player.playnext,
                'PreviousTrack': player.playprevious,
                'Seek': player.seekTime
            }
            action = actions[command]
            if command == "Seek":
                seekto = data['SeekPositionTicks']
                seektime = seekto / 10000000.0
                action(seektime)
                log.info("Seek to %s." % seektime)
            else:
                action()
                log.info("Command: %s completed." % command)

            window('emby_command', value="true")

        elif messageType == "UserDataChanged":
            # A user changed their personal rating for an item, or their playstate was updated
            userdata_list = data['UserDataList']
            self.librarySync.triage_items("userdata", userdata_list)

        elif messageType == "LibraryChanged":
            
            librarySync = self.librarySync
            processlist = {

                'added': data['ItemsAdded'],
                'update': data['ItemsUpdated'],
                'remove': data['ItemsRemoved']
            }
            for action in processlist:
                librarySync.triage_items(action, processlist[action])

        elif messageType == "GeneralCommand":
            
            command = data['Name']
            arguments = data['Arguments']

            if command in ('Mute', 'Unmute', 'SetVolume',
                            'SetSubtitleStreamIndex', 'SetAudioStreamIndex'):

                player = xbmc.Player()
                # These commands need to be reported back
                if command == "Mute":
                    xbmc.executebuiltin('Mute')
                elif command == "Unmute":
                    xbmc.executebuiltin('Mute')
                elif command == "SetVolume":
                    volume = arguments['Volume']
                    xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % volume)
                elif command == "SetAudioStreamIndex":
                    index = int(arguments['Index'])
                    player.setAudioStream(index - 1)
                elif command == "SetSubtitleStreamIndex":
                    embyindex = int(arguments['Index'])
                    currentFile = player.getPlayingFile()

                    mapping = window('emby_%s.indexMapping' % currentFile)
                    if mapping:
                        externalIndex = json.loads(mapping)
                        # If there's external subtitles added via playbackutils
                        for index in externalIndex:
                            if externalIndex[index] == embyindex:
                                player.setSubtitleStream(int(index))
                                break
                        else:
                            # User selected internal subtitles
                            external = len(externalIndex)
                            audioTracks = len(player.getAvailableAudioStreams())
                            player.setSubtitleStream(external + embyindex - audioTracks - 1)
                    else:
                        # Emby merges audio and subtitle index together
                        audioTracks = len(player.getAvailableAudioStreams())
                        player.setSubtitleStream(index - audioTracks - 1)

                # Let service know
                window('emby_command', value="true")

            elif command == "DisplayMessage":
                
                header = arguments['Header']
                text = arguments['Text']
                dialog.notification(
                            heading=header,
                            message=text,
                            icon="special://home/addons/plugin.video.emby/icon.png",
                            time=4000)

            elif command == "SendString":
                
                params = {
                    'text': arguments['String'],
                    'done': False
                }
                result = JSONRPC("Input.SendText").execute(params)

            elif command in ("MoveUp", "MoveDown", "MoveRight", "MoveLeft"):
                # Commands that should wake up display
                actions = {
                    'MoveUp': "Input.Up",
                    'MoveDown': "Input.Down",
                    'MoveRight': "Input.Right",
                    'MoveLeft': "Input.Left"
                }
                result = JSONRPC(actions[command]).execute()

            elif command == "GoHome":
                result = JSONRPC("GUI.ActivateWindow").execute({"window":"home"})

            else:
                builtin = {

                    'ToggleFullscreen': 'Action(FullScreen)',
                    'ToggleOsdMenu': 'Action(OSD)',
                    'ToggleContextMenu': 'Action(ContextMenu)',
                    'Select': 'Action(Select)',
                    'Back': 'Action(back)',
                    'PageUp': 'Action(PageUp)',
                    'NextLetter': 'Action(NextLetter)',
                    'GoToSearch': 'VideoLibrary.Search',
                    'GoToSettings': 'ActivateWindow(Settings)',
                    'PageDown': 'Action(PageDown)',
                    'PreviousLetter': 'Action(PrevLetter)',
                    'TakeScreenshot': 'TakeScreenshot',
                    'ToggleMute': 'Mute',
                    'VolumeUp': 'Action(VolumeUp)',
                    'VolumeDown': 'Action(VolumeDown)',
                }
                action = builtin.get(command)
                if action:
                    xbmc.executebuiltin(action)

        elif messageType == "ServerRestarting":
            if settings('supressRestartMsg') == "true":
                dialog.notification(
                            heading=lang(29999),
                            message=lang(33006),
                            icon="special://home/addons/plugin.video.emby/icon.png")

        elif messageType == "UserConfigurationUpdated":
            # Update user data set in userclient
            userclient.UserClient().userSettings = data
            self.librarySync.refresh_views = True

    def on_close(self, ws):
        log.debug("Closed.")

    def on_open(self, ws):
        self.doUtils.postCapabilities(self.deviceId)

    def on_error(self, ws, error):
        if "10061" in str(error):
            # Server is offline
            pass
        else:
            log.debug("Error: %s" % error)

    def run(self):

        loglevel = int(window('emby_logLevel'))
        # websocket.enableTrace(True)

        userId = window('emby_currUser')
        server = window('emby_server%s' % userId)
        token = window('emby_accessToken%s' % userId)
        # Get the appropriate prefix for the websocket
        if "https" in server:
            server = server.replace('https', "wss")
        else:
            server = server.replace('http', "ws")

        websocket_url = "%s?api_key=%s&deviceId=%s" % (server, token, self.deviceId)
        log.info("websocket url: %s" % websocket_url)

        self.client = websocket.WebSocketApp(websocket_url,
                                    on_message=self.on_message,
                                    on_error=self.on_error,
                                    on_close=self.on_close)
        
        self.client.on_open = self.on_open
        log.warn("----===## Starting WebSocketClient ##===----")

        while not self.monitor.abortRequested():

            self.client.run_forever(ping_interval=10)
            if self.stopWebsocket:
                break

            if self.monitor.waitForAbort(5):
                # Abort was requested, exit
                break

        log.warn("##===---- WebSocketClient Stopped ----===##")

    def stopClient(self):

        self.stopWebsocket = True
        self.client.close()
        log.info("Stopping thread.")