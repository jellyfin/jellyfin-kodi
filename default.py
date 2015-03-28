import xbmcaddon
import xbmcplugin
import xbmc
import xbmcgui
import os
import threading
import json
import urllib

addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
cwd = addonSettings.getAddonInfo('path')
BASE_RESOURCE_PATH = xbmc.translatePath( os.path.join( cwd, 'resources', 'lib' ) )
sys.path.append(BASE_RESOURCE_PATH)

WINDOW = xbmcgui.Window( 10000 )

import Utils as utils
from PlaybackUtils import PlaybackUtils

# get the actions... 
params=utils.get_params(sys.argv[2])

mode = params.get('mode',"")
id = params.get('id',"")

if mode == "play":
    PlaybackUtils().PLAY(id)
    
else:
    utils.checkKodiSources()
    xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

