# -*- coding: utf-8 -*-

#################################################################################################

import logging

from client import EmbyClient
from helpers import has_attribute

#################################################################################################

class NullHandler(logging.Handler):
    def emit(self, record):
        print(self.format(record))

loghandler = NullHandler
LOG = logging.getLogger('Emby')

#################################################################################################

def config(level=logging.INFO):

    logger = logging.getLogger('Emby')
    logger.addHandler(Emby.loghandler())
    logger.setLevel(level)

def ensure_client():

    def decorator(func):
        def wrapper(self, *args, **kwargs):

            if self.client.get(self.server_id) is None:
                self.construct()

            return func(self, *args, **kwargs)

        return wrapper
    return decorator


class Emby(object):

    ''' This is your Embyclient, you can create more than one. The server_id is only a temporary thing
        to communicate with the EmbyClient().

        from emby import Emby

        Emby('123456')['config/app']

        # Permanent client reference
        client = Emby('123456').get_client()
        client['config/app']
    '''

    # Borg - multiple instances, shared state
    _shared_state = {}
    client = {}
    server_id = "default"
    loghandler = loghandler

    def __init__(self, server_id=None):
        self.__dict__ = self._shared_state
        self.server_id = server_id or "default"

    def get_client(self):
        return self.client[self.server_id]

    @classmethod
    def set_loghandler(cls, func=loghandler, level=logging.INFO):

        for handler in logging.getLogger('Emby').handlers:
            if isinstance(handler, cls.loghandler):
                logging.getLogger('Emby').removeHandler(handler)

        cls.loghandler = func
        config(level)

    def close(self):

        if self.server_id not in self.client:
            return

        self.client[self.server_id].stop()
        self.client.pop(self.server_id, None)

        LOG.info("---[ STOPPED EMBYCLIENT: %s ]---", self.server_id)

    @classmethod
    def close_all(cls):

        for client in cls.client:
            cls.client[client].stop()

        cls.client = {}
        LOG.info("---[ STOPPED ALL EMBYCLIENTS ]---")

    @classmethod
    def get_active_clients(cls):
        return cls.client

    @ensure_client()
    def __setattr__(self, name, value):

        if has_attribute(self, name):
            return super(Emby, self).__setattr__(name, value)

        setattr(self.client[self.server_id], name, value)

    @ensure_client()
    def __getattr__(self, name):
        return getattr(self.client[self.server_id], name)

    @ensure_client()
    def __getitem__(self, key):
        return self.client[self.server_id][key]

    def construct(self):

        self.client[self.server_id] = EmbyClient()

        if self.server_id == 'default':
            LOG.info("---[ START EMBYCLIENT ]---")
        else:
            LOG.info("---[ START EMBYCLIENT: %s ]---", self.server_id)

config()