import xbmcaddon
import xbmcplugin
import xbmc
import xbmcgui
import xbmcvfs
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
from ReadEmbyDB import ReadEmbyDB
from API import API

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

elif mode == "reset":
    utils.reset()

#get extrafanart for listitem - this will only be used for skins that actually call the listitem's path + fanart dir... 
elif "extrafanart" in sys.argv[0]:
    itemPath = ""
    embyId = ""
    
    try:
        #only do this if the listitem has actually changed
        itemPath = xbmc.getInfoLabel("ListItem.FileNameAndPath")
            
        if not itemPath:
            itemPath = xbmc.getInfoLabel("ListItem.Path")
        
        if ("/tvshows/" in itemPath or "/musicvideos/" in itemPath or "/movies/" in itemPath):
            embyId = itemPath.split("/")[-2]

            #we need to store the images locally for this to work because of the caching system in xbmc
            fanartDir = xbmc.translatePath("special://thumbnails/emby/" + embyId + "/")
            
            if not xbmcvfs.exists(fanartDir):
                #download the images to the cache directory
                xbmcvfs.mkdir(fanartDir)
                item = ReadEmbyDB().getFullItem(embyId)
                if item != None:
                    if item.has_key("BackdropImageTags"):
                        if(len(item["BackdropImageTags"]) > 1):
                            totalbackdrops = len(item["BackdropImageTags"]) 
                            for index in range(1,totalbackdrops): 
                                backgroundUrl = API().getArtwork(item, "Backdrop",str(index))
                                fanartFile = os.path.join(fanartDir,"fanart" + str(index) + ".jpg")
                                li = xbmcgui.ListItem(str(index), path=fanartFile)
                                xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=fanartFile, listitem=li)
                                xbmcvfs.copy(backgroundUrl,fanartFile) 
                
            else:
                #use existing cached images
                dirs, files = xbmcvfs.listdir(fanartDir)
                count = 1
                for file in files:
                    count +=1
                    li = xbmcgui.ListItem(file, path=os.path.join(fanartDir,file))
                    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=os.path.join(fanartDir,file), listitem=li)
    except:
        pass
    
    #always do endofdirectory to prevent errors in the logs
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

else:   
    xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

