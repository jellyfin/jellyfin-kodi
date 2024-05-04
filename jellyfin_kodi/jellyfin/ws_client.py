# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import threading
import time

from kodi_six import xbmc

from ..helper import LazyLogger, settings

# If numpy is installed, the websockets library tries to use it, and then
# kodi hard crashes for reasons I don't even want to pretend to understand
import sys  # noqa: E402,I100
sys.modules['numpy'] = None
import websocket  # noqa: E402,I201

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class WSClient(threading.Thread):

    wsc = None
    stop = False

    def __init__(self, client):

        LOG.debug("WSClient initializing...")

        self.client = client
        threading.Thread.__init__(self)

    def send(self, message, data=""):

        if self.wsc is None:
            raise ValueError("The websocket client is not started.")

        self.wsc.send(json.dumps({'MessageType': message, "Data": data}))

    def run(self):

        monitor = xbmc.Monitor()
        token = self.client.config.data['auth.token']
        device_id = self.client.config.data['app.device_id']
        server = self.client.config.data['auth.server']
        server = server.replace('https://', 'wss://') if server.startswith('https') else server.replace('http://', 'ws://')
        wsc_url = "%s/socket?api_key=%s&device_id=%s" % (server, token, device_id)

        LOG.info("Websocket url: %s", wsc_url)

        self.wsc = websocket.WebSocketApp(wsc_url,
                                          on_open=lambda ws: self.on_open(ws),
                                          on_message=lambda ws, message: self.on_message(ws, message),
                                          on_error=lambda ws, error: self.on_error(ws, error))

        while not self.stop:

            self.wsc.run_forever(ping_interval=10, reconnect=10)

            if not self.stop and monitor.waitForAbort(5):
                break

    def on_error(self, ws, error):
        LOG.error(error)

    def on_open(self, ws):
        LOG.info("--->[ websocket opened ]")
        # Avoid a timing issue where the capabilities are not correctly registered
        time.sleep(5)
        if settings('remoteControl.bool'):
            self.client.jellyfin.post_capabilities({
                'PlayableMediaTypes': "Audio,Video",
                'SupportsMediaControl': True,
                'SupportedCommands': (
                    "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                    "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                    "GoHome,PageUp,NextLetter,GoToSearch,"
                    "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                    "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                    "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                    "SetRepeatMode,Mute,Unmute,SetVolume,"
                    "Play,Playstate,PlayNext,PlayMediaSource"
                ),
            })
        else:
            self.client.jellyfin.post_capabilities({
                "PlayableMediaTypes": "Audio, Video",
                "SupportsMediaControl": False
            })

    def on_message(self, ws, message):

        message = json.loads(message)
        data = message.get('Data', {})

        if message['MessageType'] in ('RefreshProgress',):
            LOG.debug("Ignoring %s", message)

            return

        if not self.client.config.data['app.default']:
            data['ServerId'] = self.client.auth.server_id

        self.client.callback(message['MessageType'], data)

    def stop_client(self):

        self.stop = True

        if self.wsc is not None:
            self.wsc.close()
