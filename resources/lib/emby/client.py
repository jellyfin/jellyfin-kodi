# -*- coding: utf-8 -*-

#################################################################################################

import logging

import core.api as api
from core.configuration import Config
from core.http import HTTP
from core.ws_client import WSClient
from core.connection_manager import ConnectionManager, CONNECTION_STATE

#################################################################################################

LOG = logging.getLogger('Emby.'+__name__)

#################################################################################################

def callback(message, data):

    ''' Callback function should received message, data            
        message: string
        data: json dictionary
    '''
    pass


class EmbyClient(object):

    logged_in = False

    def __init__(self):
        LOG.debug("EmbyClient initializing...")

        self.config = Config()
        self.http = HTTP(self)
        self.wsc = WSClient(self)
        self.auth = ConnectionManager(self)
        self.emby = api.API(self.http)
        self.callback_ws = callback
        self.callback = callback

    def set_credentials(self, credentials=None):
        self.auth.credentials.set_credentials(credentials or {})

    def get_credentials(self):
        return self.auth.credentials.get_credentials()

    def authenticate(self, credentials=None, options=None):

        self.set_credentials(credentials or {})
        state = self.auth.connect(options or {})

        if state['State'] == CONNECTION_STATE['SignedIn']:

            LOG.info("User is authenticated.")
            self.logged_in = True
            self.callback("ServerOnline", {'Id': self['auth/server-id']})

        state['Credentials'] = self.get_credentials()

        return state

    def start(self, websocket=False, keep_alive=True):

        if not self.logged_in:
            raise ValueError("User is not authenticated.")

        self.http.start_session()

        if keep_alive:
            self.http.keep_alive = True

        if websocket:
            self.start_wsc()

    def start_wsc(self):
        self.wsc.start()

    def stop(self):

        self.wsc.stop_client()
        self.http.stop_session()

    def __getitem__(self, key):

        if key.startswith('config'):
            return self.config[key.replace('config/', "", 1)] if "/" in key else self.config

        elif key.startswith('http'):
            return self.http.__shortcuts__(key.replace('http/', "", 1))

        elif key.startswith('websocket'):
            return self.wsc.__shortcuts__(key.replace('websocket/', "", 1))

        elif key.startswith('callback'):
            return self.callback_ws if 'ws' in key else self.callback

        elif key.startswith('auth'):
            return self.auth.__shortcuts__(key.replace('auth/', "", 1))

        elif key.startswith('api'):
            return self.emby

        elif key == 'connected':
            return self.logged_in

        return
