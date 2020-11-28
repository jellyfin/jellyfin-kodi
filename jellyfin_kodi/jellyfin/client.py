# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from helper import LazyLogger
from kodi_six.xbmc import translatePath
import json

from . import api
from .configuration import Config
from .http import HTTP
from .ws_client import WSClient
from .connection_manager import ConnectionManager, CONNECTION_STATE

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


def callback(message, data):

    ''' Callback function should received message, data
        message: string
        data: json dictionary
    '''
    pass


class JellyfinClient(object):

    logged_in = False

    def __init__(self):
        LOG.debug("JellyfinClient initializing...")

        self.config = Config()
        self.http = HTTP(self)
        self.wsc = WSClient(self)
        self.auth = ConnectionManager(self)
        self.jellyfin = api.API(self.http)
        self.callback_ws = callback
        self.callback = callback

        addon_data = translatePath("special://profile/addon_data/plugin.video.jellyfin/data.json")
        with open(addon_data, 'rb') as infile:
            data = json.load(infile)

        try:
            server_data = data['Servers'][0]
            self.jellyfin.config.data['auth.server'] = server_data.get('address')
            self.jellyfin.config.data['auth.server-name'] = server_data.get('Name')
            self.jellyfin.config.data['auth.user_id'] = server_data.get('UserId')
            self.jellyfin.config.data['auth.token'] = server_data.get('AccessToken')
        except Exception as e:
            LOG.warning('Addon appears to not be configured yet: {}'.format(e))

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
            self.callback("ServerOnline", {'Id': self.auth.server_id})

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
