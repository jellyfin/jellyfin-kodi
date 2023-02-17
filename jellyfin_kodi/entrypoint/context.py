# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import sys

from kodi_six import xbmc, xbmcaddon

from .. import database
from ..dialogs import context
from ..helper import translate, settings, dialog, LazyLogger
from ..helper.utils import translate_path
from ..jellyfin import Jellyfin

#################################################################################################

LOG = LazyLogger(__name__)
XML_PATH = (xbmcaddon.Addon('plugin.video.jellyfin').getAddonInfo('path'), "default", "1080i")
OPTIONS = {
    'Refresh': translate(30410),
    'Delete': translate(30409),
    'Addon': translate(30408),
    'AddFav': translate(30405),
    'RemoveFav': translate(30406),
    'Transcode': translate(30412)
}

#################################################################################################


class Context(object):

    _selected_option = None

    def __init__(self, transcode=False, delete=False):

        try:
            self.kodi_id = sys.listitem.getVideoInfoTag().getDbId() or None
            self.media = self.get_media_type()
            self.server_id = sys.listitem.getProperty('jellyfinserver') or None
            self.api_client = Jellyfin(self.server_id).get_client().jellyfin
            item_id = sys.listitem.getProperty('jellyfinid')
        except AttributeError:
            self.server_id = None

            if xbmc.getInfoLabel('ListItem.Property(jellyfinid)'):
                item_id = xbmc.getInfoLabel('ListItem.Property(jellyfinid)')
            else:
                self.kodi_id = xbmc.getInfoLabel('ListItem.DBID')
                self.media = xbmc.getInfoLabel('ListItem.DBTYPE')
                item_id = None

        addon_data = translate_path("special://profile/addon_data/plugin.video.jellyfin/data.json")
        with open(addon_data, 'rb') as infile:
            data = json.load(infile)

        try:
            server_data = data['Servers'][0]
            self.api_client.config.data['auth.server'] = server_data.get('address')
            self.api_client.config.data['auth.server-name'] = server_data.get('Name')
            self.api_client.config.data['auth.user_id'] = server_data.get('UserId')
            self.api_client.config.data['auth.token'] = server_data.get('AccessToken')
        except Exception as e:
            LOG.warning('Addon appears to not be configured yet: {}'.format(e))

        if self.server_id or item_id:
            self.item = self.api_client.get_item(item_id)
        else:
            self.item = self.get_item_id()

        if self.item:

            if transcode:
                self.transcode()

            elif delete:
                self.delete_item()

            elif self.select_menu():
                self.action_menu()

                if self._selected_option in (OPTIONS['Delete'], OPTIONS['AddFav'], OPTIONS['RemoveFav']):

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

        return media

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

        if self.item['Type'] != 'Season':

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

        selected = self._selected_option

        if selected == OPTIONS['Refresh']:
            self.api_client.refresh_item(self.item['Id'])

        elif selected == OPTIONS['AddFav']:
            self.api_client.favorite(self.item['Id'], True)

        elif selected == OPTIONS['RemoveFav']:
            self.api_client.favorite(self.item['Id'], False)

        elif selected == OPTIONS['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.jellyfin)')

        elif selected == OPTIONS['Delete']:
            self.delete_item()

    def delete_item(self):
        if settings('skipContextMenu.bool') or dialog("yesno", "{jellyfin}", translate(33015)):
            self.api_client.delete_item(self.item['Id'])

    def transcode(self):
        filename = xbmc.getInfoLabel("ListItem.Filenameandpath")
        filename += "&transcode=true"
        xbmc.executebuiltin("PlayMedia(%s)" % filename)
