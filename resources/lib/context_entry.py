# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcaddon

import api
import read_embyserver as embyserver
import embydb_functions as embydb
import musicutils as musicutils
from utils import settings, dialog, language as lang, kodiSQL
from dialogs import context

#################################################################################################

log = logging.getLogger("EMBY."+__name__)
OPTIONS = {

    'Refresh': lang(30410),
    'Delete': lang(30409),
    'Addon': lang(30408),
    'AddFav': lang(30405),
    'RemoveFav': lang(30406),
    'RateSong': lang(30407),
    'Transcode': lang(30412)
}

#################################################################################################


class ContextMenu(object):

    _selected_option = None


    def __init__(self):

        self.emby = embyserver.Read_EmbyServer()

        self.kodi_id = xbmc.getInfoLabel('ListItem.DBID').decode('utf-8')
        self.item_type = self._get_item_type()
        self.item_id = self._get_item_id(self.kodi_id, self.item_type)

        log.info("Found item_id: %s item_type: %s", self.item_id, self.item_type)

        if self.item_id:

            self.item = self.emby.getItem(self.item_id)
            self.api = api.API(self.item)

            if self._select_menu():
                self._action_menu()

                if self._selected_option in (OPTIONS['Delete'], OPTIONS['AddFav'],
                                             OPTIONS['RemoveFav'], OPTIONS['RateSong']):
                    log.info("refreshing container")
                    xbmc.sleep(500)
                    xbmc.executebuiltin('Container.Refresh')

    @classmethod
    def _get_item_type(cls):

        item_type = xbmc.getInfoLabel('ListItem.DBTYPE').decode('utf-8')

        if not item_type:

            if xbmc.getCondVisibility('Container.Content(albums)'):
                item_type = "album"
            elif xbmc.getCondVisibility('Container.Content(artists)'):
                item_type = "artist"
            elif xbmc.getCondVisibility('Container.Content(songs)'):
                item_type = "song"
            elif xbmc.getCondVisibility('Container.Content(pictures)'):
                item_type = "picture"
            else:
                log.info("item_type is unknown")

        return item_type

    @classmethod
    def _get_item_id(cls, kodi_id, item_type):

        item_id = xbmc.getInfoLabel('ListItem.Property(embyid)')

        if not item_id and kodi_id and item_type:

            conn = kodiSQL('emby')
            cursor = conn.cursor()
            emby_db = embydb.Embydb_Functions(cursor)
            item = emby_db.getItem_byKodiId(kodi_id, item_type)
            cursor.close()
            try:
                item_id = item[0]
            except TypeError:
                pass

        return item_id

    def _select_menu(self):
        # Display select dialog
        userdata = self.api.get_userdata()
        options = []

        if self.item_type in ("movie", "episode", "song"):
            #options.append(OPTIONS['Transcode'])
            pass

        if userdata['Favorite']:
            # Remove from emby favourites
            options.append(OPTIONS['RemoveFav'])
        else:
            # Add to emby favourites
            options.append(OPTIONS['AddFav'])

        if self.item_type == "song":
            # Set custom song rating
            options.append(OPTIONS['RateSong'])

        # Refresh item
        options.append(OPTIONS['Refresh'])
        # Delete item
        options.append(OPTIONS['Delete'])
        # Addon settings
        options.append(OPTIONS['Addon'])

        addon = xbmcaddon.Addon('plugin.video.emby')
        context_menu = context.ContextMenu("script-emby-context.xml", addon.getAddonInfo('path'),
                                           "default", "1080i")
        context_menu.set_options(options)
        context_menu.doModal()

        if context_menu.is_selected():
            self._selected_option = context_menu.get_selected()

        return self._selected_option

    def _action_menu(self):

        selected = self._selected_option

        if selected == OPTIONS['Transcode']:
            pass

        elif selected == OPTIONS['Refresh']:
            self.emby.refreshItem(self.item_id)

        elif selected == OPTIONS['AddFav']:
            self.emby.updateUserRating(self.item_id, favourite=True)

        elif selected == OPTIONS['RemoveFav']:
            self.emby.updateUserRating(self.item_id, favourite=False)

        elif selected == OPTIONS['RateSong']:
            self._rate_song()

        elif selected == OPTIONS['Addon']:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

        elif selected == OPTIONS['Delete']:
            self._delete_item()

    def _rate_song(self):

        conn = kodiSQL('music')
        cursor = conn.cursor()
        query = "SELECT rating FROM song WHERE idSong = ?"
        cursor.execute(query, (self.kodi_id,))
        try:
            value = cursor.fetchone()[0]
            current_value = int(round(float(value), 0))
        except TypeError:
            pass
        else:
            new_value = dialog("numeric", 0, lang(30411), str(current_value))
            if new_value > -1:

                new_value = int(new_value)
                if new_value > 5:
                    new_value = 5

                if settings('enableUpdateSongRating') == "true":
                    musicutils.updateRatingToFile(new_value, self.api.get_file_path())

                query = "UPDATE song SET rating = ? WHERE idSong = ?"
                cursor.execute(query, (new_value, self.kodi_id,))
                conn.commit()
        finally:
            cursor.close()

    def _delete_item(self):

        delete = True
        if settings('skipContextMenu') != "true":

            if not dialog(type_="yesno", heading="{emby}", line1=lang(33041)):
                log.info("User skipped deletion for: %s", self.item_id)
                delete = False

        if delete:
            log.info("Deleting request: %s", self.item_id)
            self.emby.deleteItem(self.item_id)
