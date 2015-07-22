# -*- coding: utf-8 -*-

import os
import sys
from urlparse import parse_qs

import xbmcaddon
import xbmc

addon_ = xbmcaddon.Addon(id='plugin.video.emby')
addon_path = addon_.getAddonInfo('path').decode('utf-8')
base_resource_path = xbmc.translatePath(os.path.join(addon_path, 'resources', 'lib')).decode('utf-8')
sys.path.append(base_resource_path)

import Entrypoint as entrypoint

# Parse parameters
base_url = sys.argv[0]
addon_handle = int(sys.argv[1])
params = parse_qs(sys.argv[2][1:])
xbmc.log("Parameter string: %s" % sys.argv[2])

try:
    mode = params['mode'][0]
    id = params.get('id', None)
    if id:
        id = id[0]
except:
    params = {}
    mode = ""

##### PLAY ITEM VIA plugin://plugin.video.emby/ #####
if "play" in mode or "playnow" in mode:
    entrypoint.doPlayback(id)

#### DO RESET AUTH #####    
elif "resetauth" in mode:
    entrypoint.resetAuth()
   
##### DO DATABASE RESET #####
elif "reset" in mode:
    import Utils as utils
    utils.reset()

##### ADD/REMOVE USER FROM SESSION #####
elif "adduser" in mode:
    entrypoint.addUser()

##### SYNC THEME MEDIA #####
elif "thememedia" in mode:
    entrypoint.getThemeMedia()

##### LAUNCH EMBY USER PREFS #####
elif "userprefs" in mode:
    entrypoint.userPreferences()

##### OPEN ADDON SETTINGS #####
elif "settings" in mode:
    xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

##### MANUALLY SYNC LIBRARY #####
elif "manualsync" in mode:
    from LibrarySync import LibrarySync
    LibrarySync().FullLibrarySync(True)

##### CACHE ARTWORK #####
elif "texturecache" in mode:
    from TextureCache import TextureCache
    TextureCache().FullTextureCacheSync()

##### BROWSE EMBY CHANNELS FOLDER #####    
elif "channelsfolder" in mode:
    folderid = params['folderid'][0]
    entrypoint.BrowseChannels(id,folderid)    
    
##### BROWSE EMBY CHANNELS ROOT #####    
elif "channels" in mode:
    entrypoint.BrowseChannels(id)
    
##### GET NEXTUP EPISODES FOR TAGNAME #####    
elif "nextup" in mode:
    limit = params['limit'][0]
    entrypoint.getNextUpEpisodes(id, limit)

##### GET INPROGRESS EPISODES FOR TAGNAME #####    
elif "inprogressepisodes" in mode:
    limit = params['limit'][0]
    entrypoint.getInProgressEpisodes(id, limit)

##### GET RECENT EPISODES FOR TAGNAME #####    
elif "recentepisodes" in mode:
    limit = params['limit'][0]
    entrypoint.getRecentEpisodes(id, limit)
    
##### GET EXTRAFANART FOR LISTITEM #####
elif "extrafanart" in sys.argv[0]:
    entrypoint.getExtraFanArt()
    
##### SHOW ADDON NODES LISTING #####    
if not mode:
    entrypoint.doMainListing()