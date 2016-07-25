# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys
import urlparse

import xbmc
import xbmcaddon
import xbmcgui

#################################################################################################

_addon = xbmcaddon.Addon(id='plugin.video.emby')
_addon_path = _addon.getAddonInfo('path').decode('utf-8')
_base_resource = xbmc.translatePath(os.path.join(_addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(_base_resource)

#################################################################################################

import api
import artwork
import downloadutils
import librarysync
import read_embyserver as embyserver
import embydb_functions as embydb
import kodidb_functions as kodidb
import musicutils as musicutils
from utils import settings, language as lang, kodiSQL

#################################################################################################

import loghandler

loghandler.config()
log = logging.getLogger("EMBY.contextmenu")

#################################################################################################

# Kodi contextmenu item to configure the emby settings
if __name__ == '__main__':

    kodiId = xbmc.getInfoLabel('ListItem.DBID').decode('utf-8')
    itemType = xbmc.getInfoLabel('ListItem.DBTYPE').decode('utf-8')
    itemId = ""
    
    if not itemType:

        if xbmc.getCondVisibility("Container.Content(albums)"):
            itemType = "album"
        elif xbmc.getCondVisibility("Container.Content(artists)"):
            itemType = "artist"
        elif xbmc.getCondVisibility("Container.Content(songs)"):
            itemType = "song"
        elif xbmc.getCondVisibility("Container.Content(pictures)"):
            itemType = "picture"
        else:
            log.info("ItemType is unknown.")

    if (not kodiId or kodiId == "-1") and xbmc.getInfoLabel("ListItem.Property(embyid)"):
        itemId = xbmc.getInfoLabel("ListItem.Property(embyid)")
    
    elif kodiId and itemType:
        embyconn = kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)
        item = emby_db.getItem_byKodiId(kodiId, itemType)
        embycursor.close()
        try:
            itemId = item[0]
        except TypeError:
            pass

    
    log.info("Found ItemId: %s ItemType: %s" % (itemId, itemType))
    if itemId:

        dialog = xbmcgui.Dialog()

        emby = embyserver.Read_EmbyServer()
        item = emby.getItem(itemId)
        API = api.API(item)
        userdata = API.getUserData()
        likes = userdata['Likes']
        favourite = userdata['Favorite']
        
        options = []

        if favourite:
            # Remove from emby favourites
            options.append(lang(30406))
        else:
            # Add to emby favourites
            options.append(lang(30405)) 

        if itemType == "song":
            # Set custom song rating
            options.append(lang(30407))
        
        # Refresh item
        options.append(lang(30410))
        # Delete item
        options.append(lang(30409))
        # Addon settings
        options.append(lang(30408))
        
        # Display select dialog and process results
        resp = xbmcgui.Dialog().select(lang(30401), options)
        if resp > -1:
            selected = options[resp]

            if selected == lang(30410):
                # Refresh item
                emby.refreshItem(itemId)
            elif selected == lang(30405):
                # Add favourite
                emby.updateUserRating(itemId, favourite=True)
            elif selected == lang(30406):
                # Delete favourite
                emby.updateUserRating(itemId, favourite=False)
            elif selected == lang(30407):
                # Update song rating
                kodiconn = kodiSQL('music')
                kodicursor = kodiconn.cursor()
                query = "SELECT rating FROM song WHERE idSong = ?"
                kodicursor.execute(query, (kodiId,))
                try:
                    value = kodicursor.fetchone()[0]
                    current_value = int(round(float(value),0))
                except TypeError:
                    pass
                else:
                    new_value = dialog.numeric(0, lang(30411), str(current_value))
                    if new_value > -1:
                        
                        new_value = int(new_value)
                        if new_value > 5:
                            new_value = 5

                        if settings('enableUpdateSongRating') == "true":
                            musicutils.updateRatingToFile(new_value, API.getFilePath())

                        query = "UPDATE song SET rating = ? WHERE idSong = ?"
                        kodicursor.execute(query, (new_value, kodiId,))
                        kodiconn.commit()
                        
                        '''if settings('enableExportSongRating') == "true":
                            like, favourite, deletelike = musicutils.getEmbyRatingFromKodiRating(new_value)
                            emby.updateUserRating(itemId, like, favourite, deletelike)'''
                finally:
                    kodicursor.close()

            elif selected == lang(30408):
                # Open addon settings
                xbmc.executebuiltin("Addon.OpenSettings(plugin.video.emby)")
                
            elif selected == lang(30409):
                # delete item from the server
                delete = True
                if settings('skipContextMenu') != "true":
                    resp = dialog.yesno(
                                heading=lang(29999),
                                line1=lang(33041))
                    if not resp:
                        log.info("User skipped deletion for: %s." % itemId)
                        delete = False
                
                if delete:
                    log.info("Deleting request: %s" % itemId)
                    emby.deleteItem(itemId)
            
            xbmc.sleep(500)
            xbmc.executebuiltin('Container.Refresh')