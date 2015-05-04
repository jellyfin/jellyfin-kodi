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

from PluginFunctions import PluginFunctions


def json_query( method, unplayed=False, properties=None, sort=False, query_filter=False, limit=False, params=False):
    json_query = { "jsonrpc": "2.0", "id": 1, "method": method, "params": {} }
    if properties is not None:
        json_query["params"]["properties"] = properties
    if limit is not None:
        json_query["params"]["limits"] =  {"end":limit if limit else 25}
    if sort is not None:
        json_query["params"]["sort"] = sort
    if query_filter:
        json_query["params"]["filter"] = query_filter
    if params:
        json_query["params"].update(params)

    json_string = json.dumps(json_query)
    rv = xbmc.executeJSONRPC(json_string)
    
    return unicode(rv, 'utf-8', errors='ignore')


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

    
elif "getnextup" in sys.argv[0]:
    params = utils.get_params(sys.argv[2])
    tagname = params['tagname']
    xbmcplugin.setContent(int(sys.argv[1]), 'episodes')
    # First we get a list of all the in-progress TV shows - filtered by tag
    json_query_string = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "sort": { "order": "descending", "method": "lastplayed" }, "filter": {"and": [{"operator":"true", "field":"inprogress", "value":""}, {"operator": "contains", "field": "tag", "value": "%s"}]}, "properties": [ "title", "studio", "mpaa", "file", "art" ]  }, "id": "libTvShows"}' %tagname)
    print json_query_string    
    
    json_result = json.loads(json_query_string)
    # If we found any, find the oldest unwatched show for each one.
    if json_result.has_key('result') and json_result['result'].has_key('tvshows'):
        for item in json_result['result']['tvshows']:
            json_query2 = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": { "tvshowid": %d, "sort": {"method":"episode"}, "filter": {"field": "playcount", "operator": "lessthan", "value":"1"}, "properties": [ "title", "playcount", "season", "episode", "showtitle", "plot", "file", "rating", "resume", "tvshowid", "art", "streamdetails", "firstaired", "runtime", "writer", "dateadded", "lastplayed" ], "limits":{"end":1}}, "id": "1"}' %item['tvshowid'])

            if json_query2:
                json_query2 = json.loads(json_query2)
                if json_query2.has_key('result') and json_query2['result'].has_key('episodes'):
                    count = 0
                    for item in json_query2['result']['episodes']:
                        episode = "%.2d" % float(item['episode'])
                        season = "%.2d" % float(item['season'])
                        episodeno = "s%se%s" %(season,episode)
                        watched = False
                        if item['playcount'] >= 1:
                            watched = True
                        plot = item['plot']
                        liz = xbmcgui.ListItem(item['title'])
                        liz.setInfo( type="Video", infoLabels={ "Title": item['title'] })
                        liz.setInfo( type="Video", infoLabels={ "Episode": item['episode'] })
                        liz.setInfo( type="Video", infoLabels={ "Season": item['season'] })
                        liz.setInfo( type="Video", infoLabels={ "Premiered": item['firstaired'] })
                        liz.setInfo( type="Video", infoLabels={ "Plot": plot })
                        liz.setInfo( type="Video", infoLabels={ "TVshowTitle": item['showtitle'] })
                        liz.setInfo( type="Video", infoLabels={ "Rating": str(round(float(item['rating']),1)) })
                        liz.setInfo( type="Video", infoLabels={ "Playcount": item['playcount'] })
                        if "director" in item:
                            liz.setInfo( type="Video", infoLabels={ "Director": " / ".join(item['director']) })
                        if "writer" in item:
                            liz.setInfo( type="Video", infoLabels={ "Writer": " / ".join(item['writer']) })
                        if "cast" in item:
                            liz.setInfo( type="Video", infoLabels={ "Cast": cast[0] })
                            liz.setInfo( type="Video", infoLabels={ "CastAndRole": cast[1] })
                        liz.setProperty("episodeno", episodeno)
                        liz.setProperty("resumetime", str(item['resume']['position']))
                        liz.setProperty("totaltime", str(item['resume']['total']))
                        liz.setArt(item['art'])
                        liz.setThumbnailImage(item['art'].get('thumb',''))
                        liz.setIconImage('DefaultTVShows.png')
                        liz.setProperty("dbid", str(item['episodeid']))
                        liz.setProperty("fanart_image", item['art'].get('tvshow.fanart',''))
                        for key, value in item['streamdetails'].iteritems():
                            for stream in value:
                                liz.addStreamInfo( key, stream ) 
                        
                        xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=item['file'], listitem=liz)
    xbmcplugin.endOfDirectory(handle= int(sys.argv[1]))

    
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


elif sys.argv[1] == "reset":
    utils.reset()
else:   
    xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

