# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from client import get_device_id
from helper import LazyLogger, window, settings
from helper import api as helper_api

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

    def __init__(self, server_id):
        LOG.debug("JellyfinClient initializing...")

        self.config = Config()
        self.http = HTTP(self)
        self.wsc = WSClient(self)
        self.auth = ConnectionManager(self)
        self.jellyfin = api.API(self.http)
        self.callback_ws = callback
        self.callback = callback
        self.server_id = server_id
        self.logged_in = False

    def register_client(self):
        device_id = get_device_id()
        self.post_capabilities(self, device_id)

        if self.server_id == 'default' and settings('additionalUsers'):
            users = settings('additionalUsers').split(',')
            all_users = self.jellyfin.get_users()

            for additional in users:
                for user in all_users:
                    if user['Name'].lower() in additional.lower():
                        self.jellyfin.session_add_user(self.config.data['app.session'], user['Id'], True)

            self.additional_users(self, device_id)
    
    @staticmethod
    def additional_users(client, device_id):
        ''' Setup additional users images.
        '''
        for i in range(10):
            window('JellyfinAdditionalUserImage.%s' % i, clear=True)

        try:
            session = client.jellyfin.get_device(device_id)
        except Exception as error:
            LOG.exception(error)

            return

        for index, user in enumerate(session[0]['AdditionalUsers']):

            info = client.jellyfin.get_user(user['UserId'])
            image = helper_api.API(info, client.config.data['auth.server']).get_user_artwork(user['UserId'])
            window('JellyfinAdditionalUserImage.%s' % index, image)
            window('JellyfinAdditionalUserPosition.%s' % user['UserId'], str(index))

    @staticmethod
    def post_capabilities(client, device_id):
        LOG.info("--[ post capabilities/%s ]", client.auth.server_id)

        client.jellyfin.post_capabilities({
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                "SetRepeatMode,"
                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
        })
        session = client.jellyfin.get_device(device_id)
        client.config.data['app.session'] = session[0]['Id']

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
        
        self.register_client()
        LOG.info("---[ START JELLYFINCLIENT: %s ]---", self.server_id)

    def start_wsc(self):
        self.wsc.start()

    def stop(self):

        self.wsc.stop_client()
        self.http.stop_session()
