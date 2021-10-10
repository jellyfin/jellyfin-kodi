# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from kodi_six import xbmcgui

from . import LazyLogger

from .utils import should_stop
from .exceptions import LibraryException
from .translate import translate

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


def progress(message=None):

    ''' Will start and close the progress dialog.
    '''
    def decorator(func):
        def wrapper(self, item=None, *args, **kwargs):

            dialog = xbmcgui.DialogProgressBG()

            if item and type(item) == dict:

                dialog.create(translate('addon_name'), "%s %s" % (translate('gathering'), item['Name']))
                LOG.info("Processing %s: %s", item['Name'], item['Id'])
            else:
                dialog.create(translate('addon_name'), message)
                LOG.info("Processing %s", message)

            if item:
                args = (item,) + args

            result = func(self, dialog=dialog, *args, **kwargs)
            dialog.close()

            return result

        return wrapper
    return decorator


def stop(func):

    ''' Wrapper to catch exceptions and return using catch
    '''
    def wrapper(*args, **kwargs):

        try:
            if should_stop():  # ??? TODO: Fixme
                raise Exception

        except Exception as error:
            LOG.exception(error)

            raise LibraryException("StopCalled")

        return func(*args, **kwargs)

    return wrapper


def jellyfin_item(func):

    ''' Wrapper to retrieve the jellyfin_db item.
    '''
    def wrapper(self, item, *args, **kwargs):
        e_item = self.jellyfin_db.get_item_by_id(item['Id'] if type(item) == dict else item)

        return func(self, item, e_item=e_item, *args, **kwargs)

    return wrapper
