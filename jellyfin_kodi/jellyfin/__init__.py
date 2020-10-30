# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import logging

from helper import has_attribute, LazyLogger, window, api, dialog, translate, settings

from .client import JellyfinClient
from client import get_device_id
import connect

#################################################################################################

LOG = LazyLogger()

#################################################################################################


def ensure_client():

    def decorator(func):
        def wrapper(self, *args, **kwargs):

            if self.client.get(self.server_id) is None:
                self.construct()

            return func(self, *args, **kwargs)

        return wrapper
    return decorator


class Jellyfin(object):

    ''' This is your Jellyfinclient, you can create more than one. The server_id is only a temporary thing
        to communicate with the JellyfinClient().

        from jellyfin import Jellyfin

        Jellyfin('123456').config.data['app']

        # Permanent client reference
        client = Jellyfin('123456').get_client()
        client.config.data['app']
    '''

    # Borg - multiple instances, shared state
    _shared_state = {}
    client = {}
    server_id = "default"

    def __init__(self, server_id=None):
        self.__dict__ = self._shared_state
        self.server_id = server_id or "default"

    def get_client(self):
        # type: () -> JellyfinClient
        return self.client[self.server_id]

    def close(self):

        if self.server_id not in self.client:
            return

        self.client[self.server_id].stop()
        self.client.pop(self.server_id, None)

        LOG.info("---[ STOPPED JELLYFINCLIENT: %s ]---", self.server_id)

    @classmethod
    def close_all(cls):

        for client in cls.client:
            cls.client[client].stop()

        cls.client = {}
        LOG.info("---[ STOPPED ALL JELLYFINCLIENTS ]---")

    @classmethod
    def get_active_clients(cls):
        return cls.client

    @ensure_client()
    def __setattr__(self, name, value):

        if has_attribute(self, name):
            return super(Jellyfin, self).__setattr__(name, value)

        setattr(self.client[self.server_id], name, value)

    @ensure_client()
    def __getattr__(self, name):
        return getattr(self.client[self.server_id], name)

    def construct(self):
        self.client[self.server_id] = JellyfinClient()

        try:
            connect.Connect().register(self.server_id)
            self.register_client()
        except Exception as error:
            LOG.exception(error)
            dialog("ok", "{jellyfin}", translate(33142))
            return

        LOG.info("---[ START JELLYFINCLIENT: %s ]---", self.server_id)

    def register_client(self):
        client = self.get_client()
        device_id = get_device_id()
        self.post_capabilities(client, device_id)

        if self.server_id is None and settings('additionalUsers'):
            users = settings('additionalUsers').split(',')
            all_users = client.jellyfin.get_users()

            for additional in users:
                for user in all_users:
                    if user['Name'].lower() in additional.lower():
                        client.jellyfin.session_add_user(client.config.data['app.session'], user['Id'], True)

            self.additional_users(client, device_id)
    
    @staticmethod
    def additional_users(server, device_id):
        ''' Setup additional users images.
        '''
        for i in range(10):
            window('JellyfinAdditionalUserImage.%s' % i, clear=True)

        try:
            session = server.jellyfin.get_device(device_id)
        except Exception as error:
            LOG.exception(error)

            return

        for index, user in enumerate(session[0]['AdditionalUsers']):

            info = server.jellyfin.get_user(user['UserId'])
            image = api.API(info, server.config.data['auth.server']).get_user_artwork(user['UserId'])
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
