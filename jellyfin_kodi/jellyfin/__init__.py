# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from ..helper import has_attribute, LazyLogger

from .client import JellyfinClient

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
    """This is your Jellyfinclient, you can create more than one. The server_id is only a temporary thing
    to communicate with the JellyfinClient().

    from jellyfin_kodi.jellyfin import Jellyfin

    Jellyfin('123456').config.data['app']

    # Permanent client reference
    client = Jellyfin('123456').get_client()
    client.config.data['app']
    """

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

        if self.server_id == "default":
            LOG.info("---[ START JELLYFINCLIENT ]---")
        else:
            LOG.info("---[ START JELLYFINCLIENT: %s ]---", self.server_id)
