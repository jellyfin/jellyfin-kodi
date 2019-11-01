# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import sys

import xbmc
import xbmcaddon

import database
from dialogs import context
from helper import _, settings, dialog
from downloader import TheVoid

#################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)
XML_PATH = (xbmcaddon.Addon('plugin.video.jellyfin').getAddonInfo('path'), "default", "1080i")
OPTIONS = {
    'Refresh': _(30410),
    'Delete': _(30409),
    'Addon': _(30408),
    'AddFav': _(30405),
    'RemoveFav': _(30406),
    'Transcode': _(30412)
}

#################################################################################################


class Context(object):

    _selected_option = None

    def __init__(self, transcode=False, delete=False):

        try:
            self.kodi_id = sys.listitem.getVideoInfoTag().getDbId() or None
            self.media = self.get_media_type()
            self.server = sys.listitem.getProperty('jellyfinserver') or None
            item_id = sys.listitem.getProperty('jellyfinid')
        except AttributeError:
            self.server = None

            if xbmc.getInfoLabel('ListItem.Property(jellyfinid)'):
                item_id = xbmc.getInfoLabel('ListItem.Property(jellyfinid)')
            else:
                self.kodi_id = xbmc.getInfoLabel('ListItem.DBID')
                self.media = xbmc.getInfoLabel('ListItem.DBTYPE')
                item_id = None

        if self.server or item_id:
            self.item = TheVoid('GetItem', {'ServerId': self.server, 'Id': item_id}).get()
        else:
            self.item = self.get_item_id()

        if self.item:

            if transcode:
                self.transcode()

            elif delete:
                self.delete_item()

            elif self.select_menu():
                self.action_menu()

                if self._selected_option.decode('utf-8') in (OPTIONS['Delete'], OPTIONS['AddFav'], OPTIONS['RemoveFav']):

                    xbmc.sleep(500)
                    xbmc.executebuiltin('Container.Refresh')

    def get_media_type(self):

        ''' Get media type based on sys.listitem. If unfilled, base on visible window.
        '''
        media = sys.listitem.getVideoInfoTag().getMediaType()

        if not media:

            if xbmc.getCondVisibility('Container.Content(albums)'):
                media = "album"
            elif xbmc.getCondVisibility('Container.Content(artists)'):
                media = "artist"
            elif xbmc.getCondVisibility('Container.Content(songs)'):
                media = "song"
            elif xbmc.getCondVisibility('Container.Content(pictures)'):
                media = "picture"
            else:
                LOG.info("media is unknown")

        return media.decode('utf-8')

    def get_item_id(self):

        ''' Get synced item from jellyfindb.
        '''
        item = database.get_item(self.kodi_id, self.media)

        if not item:
            return

        return {
            'Id': item[0],
            'UserData': json.loads(item[4]) if item[4] else {},
            'Type': item[3]
        }

    def select_menu(self):

        ''' Display the select dialog.
            Favorites, Refresh, Delete (opt), Settings.
        '''
        options = []

        if self.item['Type'] not in ('Season'):

            if self.item['UserData'].get('IsFavorite'):
                options.append(OPTIONS['RemoveFav'])
            else:
                options.append(OPTIONS['AddFav'])

        options.append(OPTIONS['Refresh'])

        if settings('enableContextDelete.bool'):
            options.append(OPTIONS['Delete'])

        options.append(OPTIONS['Addon'])

        context_menu = context.ContextMenu("script-jellyfin-context.xml", *XML_PATH)
        context_menu.set_options(options)
        context_menu.doModal()

        if context_menu.is_selected():
            self._selected_option = context_menu.get_selected()

        return self._selected_option

    def action_menu(self):

        selected = self._selected_option.decode('utf-8')

        if selected == OPTIONS['Refresh']:
            TheVoid('RefreshItem', {'ServerId': self.server, 'Id': self.item['Id']})

        elif selected == OPTIONS['AddFav']:
            TheVoid('FavoriteItem', {'ServerId': self.server, 'Id': self.item['Id'], 'Favorite': True})

        elif selected == OPTIONS['RemoveFav']:
            TheVoid('FavoriteItem', {'ServerId': self.server, 'Id': self.item['Id'], 'Favorite': False})

        elif selected == OPTIONS['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.jellyfin)')

        elif selected == OPTIONS['Delete']:
            self.delete_item()

    def delete_item(self):

        delete = True

        if not settings('skipContextMenu.bool'):

            if not dialog("yesno", heading="{jellyfin}", line1=_(33015)):
                delete = False

        if delete:
            TheVoid('DeleteItem', {'ServerId': self.server, 'Id': self.item['Id']})

    def transcode(self):
        filename = xbmc.getInfoLabel("ListItem.Filenameandpath")
        filename += "&transcode=true"
        xbmc.executebuiltin("PlayMedia(%s)" % filename)
