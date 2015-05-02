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

WINDOW = xbmcgui.Window(10000)

import Utils as utils
from PlaybackUtils import PlaybackUtils
from DownloadUtils import DownloadUtils

try:
    params = utils.get_params(sys.argv[2])
    mode = params['mode']
    id = params['id']
except:
    params = {}
    mode = None

if  mode == "play":
    # Play items via plugin://plugin.video.emby/
    url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1" % id
    result = DownloadUtils().downloadUrl(url)
    item = PlaybackUtils().PLAY(result, setup="default")

elif sys.argv[1] == "reset":
    utils.reset()
else:
    xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

