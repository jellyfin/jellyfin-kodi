# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmcgui

from .utils import should_stop
from .exceptions import LibraryException
from .translate import _

#################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

#################################################################################################


def progress(message=None):

    ''' Will start and close the progress dialog.
    '''
    def decorator(func):
        def wrapper(self, item=None, *args, **kwargs):

            dialog = xbmcgui.DialogProgressBG()

            if item and type(item) == dict:

                dialog.create(_('addon_name'), "%s %s" % (_('gathering'), item['Name']))
                LOG.info("Processing %s: %s", item['Name'], item['Id'])
            else:
                dialog.create(_('addon_name'), message)
                LOG.info("Processing %s", message)

            if item:
                args = (item,) + args

            result = func(self, dialog=dialog, *args, **kwargs)
            dialog.close()

            return result

        return wrapper
    return decorator


def catch(errors=(Exception,)):

    ''' Wrapper to catch exceptions and return using catch
    '''
    def decorator(func):
        def wrapper(*args, **kwargs):

            try:
                return func(*args, **kwargs)
            except errors as error:
                LOG.exception(error)

                raise Exception("Caught exception")

        return wrapper
    return decorator


def silent_catch(errors=(Exception,)):

    ''' Wrapper to catch exceptions and ignore them
    '''
    def decorator(func):
        def wrapper(*args, **kwargs):

            try:
                return func(*args, **kwargs)
            except errors as error:
                LOG.error(error)

        return wrapper
    return decorator


def stop(default=None):

    ''' Wrapper to catch exceptions and return using catch
    '''
    def decorator(func):
        def wrapper(*args, **kwargs):

            try:
                if should_stop():  # ??? TODO: Fixme
                    raise Exception

            except Exception as error:
                LOG.exception(error)

                if default is not None:
                    return default

                raise LibraryException("StopCalled")

            return func(*args, **kwargs)

        return wrapper
    return decorator


def jellyfin_item():

    ''' Wrapper to retrieve the jellyfin_db item.
    '''
    def decorator(func):
        def wrapper(self, item, *args, **kwargs):
            e_item = self.jellyfin_db.get_item_by_id(item['Id'] if type(item) == dict else item)

            return func(self, item, e_item=e_item, *args, **kwargs)

        return wrapper
    return decorator


def library_check():

    ''' Wrapper to retrieve the library
    '''
    def decorator(func):
        def wrapper(self, item, *args, **kwargs):

            ''' TODO: Rethink this one... songs and albums cannot be found by library. expensive.
            '''
            from database import get_sync

            if kwargs.get('library') is None:
                sync = get_sync()

                if 'e_item' in kwargs:
                    try:
                        view_id = kwargs['e_item'][6]
                        view_name = self.jellyfin_db.get_view_name(view_id)
                        view = {'Name': view_name, 'Id': view_id}
                    except Exception:
                        view = None

                if view is None:
                    ancestors = self.server.jellyfin.get_ancestors(item['Id'])

                    if not ancestors:
                        if item['Type'] == 'MusicArtist':

                            try:
                                views = self.jellyfin_db.get_views_by_media('music')[0]
                            except Exception as error:
                                LOG.exception(error)
                                return

                            view = {'Id': views[0], 'Name': views[1]}
                        else:  # Grab the first music library
                            return
                    else:
                        for ancestor in ancestors:
                            if ancestor['Type'] == 'CollectionFolder':

                                view = self.jellyfin_db.get_view_name(ancestor['Id'])
                                view = {'Id': None, 'Name': None} if view is None else {'Name': ancestor['Name'], 'Id': ancestor['Id']}

                                break

                    if view['Id'] not in [x.replace('Mixed:', "") for x in sync['Whitelist'] + sync['Libraries']]:
                        LOG.info("Library %s is not synced. Skip update.", view['Id'])

                        return

                kwargs['library'] = view

            return func(self, item, *args, **kwargs)

        return wrapper
    return decorator
