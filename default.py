import xbmcaddon
import xbmcplugin
import xbmc
import xbmcgui
import xbmcvfs
import os, sys


addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
cwd = addonSettings.getAddonInfo('path')
BASE_RESOURCE_PATH = xbmc.translatePath( os.path.join( cwd, 'resources', 'lib' ) )
sys.path.append(BASE_RESOURCE_PATH)



import Entrypoint as entrypoint
import Utils as utils


try:
    params = utils.get_params(sys.argv[2])
    mode = params['mode']
    id = params.get('id', None)
except:
    params = {}
    mode = None

##### Play items via plugin://plugin.video.emby/ #####
if  mode == "play":
    entrypoint.doPlayback(id)

##### DO DATABASE RESET #####
elif mode == "reset":
    utils.reset()

#### DO RESET AUTH #####    
elif mode == "resetauth":
    entrypoint.resetAuth()

##### BROWSE EMBY CHANNELS ROOT #####    
elif  mode == "channels":
    entrypoint.BrowseChannels(id)

##### BROWSE EMBY CHANNELS FOLDER #####    
elif  mode == "channelsfolder":
    folderid = params['folderid']
    entrypoint.BrowseChannels(id,folderid)    
    
##### GET NEXTUP EPISODES FOR TAGNAME #####    
elif  mode == "nextup":
    limit = int(params['limit'])
    entrypoint.getNextUpEpisodes(id, limit)

    
##### GET EXTRAFANART FOR LISTITEM #####
elif "extrafanart" in sys.argv[0]:
    entrypoint.getExtraFanArt()
    

##### SHOW ADDON SETTINGS #####    
else:
    #open the addon settings if the addon is called directly from video addons
    try:
        if "content_type" in sys.argv[2]:
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')
    except: pass

