# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import threading

import xbmc

from .. import websocket

##################################################################################################

LOG = logging.getLogger('JELLYFIN.' + __name__)

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
        server = server.replace('https', "wss") if server.startswith('https') else server.replace('http', "ws")
        wsc_url = "%s/embywebsocket?api_key=%s&device_id=%s" % (server, token, device_id)

        LOG.info("Websocket url: %s", wsc_url)

        self.wsc = websocket.WebSocketApp(wsc_url,
                                          on_message=self.on_message,
                                          on_error=self.on_error)
        self.wsc.on_open = self.on_open

        while not self.stop:

            self.wsc.run_forever(ping_interval=10)

            if not self.stop and monitor.waitForAbort(5):
                break

        LOG.info("---<[ websocket ]")

    def on_error(self, ws, error):
        LOG.error(error)

    def on_open(self, ws):
        LOG.info("--->[ websocket ]")

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
