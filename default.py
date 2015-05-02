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

try:
    params=utils.get_params(sys.argv[2])
    mode = params.get('mode',"")
    id = params.get('id',"")
except:
    params={}
    mode=None
    id=None

if  mode != None and mode == "play":
    listItem = xbmcgui.ListItem(path="")
    xbmcplugin.setResolvedUrl (int(sys.argv[1]), True, listItem)
    WINDOW.setProperty('GUIPLAY', str(id)) # set window prop
elif sys.argv[1] == "reset":
    utils.reset()
else:
    xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

