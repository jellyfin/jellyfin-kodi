# -*- coding: utf-8 -*-

#################################################################################################

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
from utils import Logging, settings, language as lang, kodiSQL
log = Logging('ContextMenu').log

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
            log("Itemtype is unknown.")

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

    
    log("Found ItemId: %s/Itemtype: %s" % (itemId, itemType), 1)
    if itemId:

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

        ret = xbmcgui.Dialog().select(lang(30401), options)
        if ret != -1:
            if options[ret] == lang(30410):
                emby.refreshItem(itemId)
            if options[ret] == lang(30402):
                emby.updateUserRating(itemId, deletelike=True)
            if options[ret] == lang(30403):
                emby.updateUserRating(itemId, like=True)
            if options[ret] == lang(30404):
                emby.updateUserRating(itemId, like=False)
            if options[ret] == lang(30405):
                emby.updateUserRating(itemId, favourite=True)
            if options[ret] == lang(30406):
                emby.updateUserRating(itemId, favourite=False)
            if options[ret] == lang(30407):
                kodiconn = kodiSQL('music')
                kodicursor = kodiconn.cursor()
                query = ' '.join(("SELECT rating", "FROM song", "WHERE idSong = ?" ))
                kodicursor.execute(query, (itemid,))
                currentvalue = int(round(float(kodicursor.fetchone()[0]),0))
                newvalue = xbmcgui.Dialog().numeric(0, "Set custom song rating (0-5)", str(currentvalue))
                if newvalue:
                    newvalue = int(newvalue)
                    if newvalue > 5: newvalue = "5"
                    if settings('enableUpdateSongRating') == "true":
                        musicutils.updateRatingToFile(newvalue, API.getFilePath())
                    if settings('enableExportSongRating') == "true":
                        like, favourite, deletelike = musicutils.getEmbyRatingFromKodiRating(newvalue)
                        emby.updateUserRating(itemId, like, favourite, deletelike)
                    query = ' '.join(( "UPDATE song","SET rating = ?", "WHERE idSong = ?" ))
                    kodicursor.execute(query, (newvalue,itemid,))
                    kodiconn.commit()

            if options[ret] == lang(30408):
                #Open addon settings
                xbmc.executebuiltin("Addon.OpenSettings(plugin.video.emby)")
                
            if options[ret] == lang(30409):
                #delete item from the server
                delete = True
                if settings('skipContextMenu') != "true":
                    resp = xbmcgui.Dialog().yesno(
                                            heading="Confirm delete",
                                            line1=("Delete file from Emby Server? This will "
                                                    "also delete the file(s) from disk!"))
                    if not resp:
                        log("User skipped deletion for: %s." % itemId, 1)
                        delete = False
                
                if delete:
                    import downloadutils
                    doUtils = downloadutils.DownloadUtils()
                    url = "{server}/emby/Items/%s?format=json" % itemId
                    log("Deleting request: %s" % embyid, 0)
                    doUtils.downloadUrl(url, action_type="DELETE")

                '''if settings('skipContextMenu') != "true":
                    if xbmcgui.Dialog().yesno(
                                        heading="Confirm delete",
                                        line1=("Delete file on Emby Server? This will "
                                                "also delete the file(s) from disk!")):
                        import downloadutils
                        doUtils = downloadutils.DownloadUtils()
                        doUtils.downloadUrl("{server}/emby/Items/%s?format=json" % embyid, action_type="DELETE")'''
            
            xbmc.sleep(500)
            xbmc.executebuiltin('Container.Update')