# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import threading

from kodi_six import xbmc

from helper import LazyLogger

from . import websocket

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
        server = server.replace('https', "wss") if server.startswith('https') else server.replace('http', "ws")
        wsc_url = "%s/socket?api_key=%s&device_id=%s" % (server, token, device_id)

        #import web_pdb; web_pdb.set_trace()
        LOG.info("Websocket url: %s", wsc_url)

        self.wsc = websocket.WebSocketApp(wsc_url,
                                          on_message=lambda ws, message: self.on_message(ws, message),
                                          on_error=lambda ws, error: self.on_error(ws, error))
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

        import web_pdb; web_pdb.set_trace()
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
