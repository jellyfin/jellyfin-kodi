import xbmcaddon
import xbmcplugin
import xbmc
import xbmcgui
import xbmcvfs
import os, sys
import threading
import json
import urllib


WINDOW = xbmcgui.Window(10000)

import Utils as utils
from PlaybackUtils import PlaybackUtils
from DownloadUtils import DownloadUtils
from ReadEmbyDB import ReadEmbyDB
from API import API


##### Play items via plugin://plugin.video.emby/ #####
def doPlayback(id):
    url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1" % id
    result = DownloadUtils().downloadUrl(url)
    item = PlaybackUtils().PLAY(result, setup="default")


#### DO RESET AUTH #####    
def resetAuth():
    # User tried login and failed too many times
    resp = xbmcgui.Dialog().yesno("Warning", "Emby might lock your account if you fail to log in too many times. Proceed anyway?")
    if resp == 1:
        xbmc.log("Reset login attempts.")
        WINDOW.setProperty("Server_status", "Auth")
    else:
        xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

##### BROWSE EMBY CHANNELS #####    
def BrowseChannels(id, folderid=None):
    
    _addon_id   =   int(sys.argv[1])
    _addon_url  =   sys.argv[0]
    
    
    if folderid:
        url = "{server}/mediabrowser/Channels/" + id + "/Items?userid={UserId}&folderid=" + folderid + "&format=json"
    else:
        if id == "0": # id 0 is the root channels folder
            url = "{server}/mediabrowser/Channels?{UserId}&format=json"
        else:
            url = "{server}/mediabrowser/Channels/" + id + "/Items?userid={UserId}&format=json"

    results = DownloadUtils().downloadUrl(url)
    if results:
        result = results.get("Items")
        if(result == None):
            result = []

        item_count = len(result)
        current_item = 1;
            
        for item in result:
            id=str(item.get("Id")).encode('utf-8')
            type=item.get("Type").encode('utf-8')
            
            
            if(item.get("Name") != None):
                tempTitle = item.get("Name")
                tempTitle=tempTitle.encode('utf-8')
            else:
                tempTitle = "Missing Title"
                
            if type=="ChannelFolderItem":
                isFolder = True
            else:
                isFolder = False
            item_type = str(type).encode('utf-8')
            
            if(item.get("ChannelId") != None):
               channelId = str(item.get("ChannelId")).encode('utf-8')
            
            channelName = ''   
            if(item.get("ChannelName") != None):
               channelName = item.get("ChannelName").encode('utf-8')   
               
            if(item.get("PremiereDate") != None):
                premieredatelist = (item.get("PremiereDate")).split("T")
                premieredate = premieredatelist[0]
            else:
                premieredate = ""
            
            #mediaStreams=API().getMediaStreams(item, True)
                    
            #people = API().getPeople(item)
            
            # Process Genres
            genre = API().getGenre(item)
                    
            # Process UserData
            userData = item.get("UserData")
            PlaybackPositionTicks = '100'
            overlay = "0"
            favorite = "False"
            seekTime = 0
            if(userData != None):
                if userData.get("Played") != True:
                    overlay = "7"
                    watched = "true"
                else:
                    overlay = "6"
                    watched = "false"
                if userData.get("IsFavorite") == True:
                    overlay = "5"
                    favorite = "True"
                else:
                    favorite = "False"
                if userData.get("PlaybackPositionTicks") != None:
                    PlaybackPositionTicks = str(userData.get("PlaybackPositionTicks"))
                    reasonableTicks = int(userData.get("PlaybackPositionTicks")) / 1000
                    seekTime = reasonableTicks / 10000
            
            playCount = 0
            if(userData != None and userData.get("Played") == True):
                playCount = 1
            # Populate the details list
            details={'title'        : tempTitle,
                     'channelname'  : channelName,
                     'plot'         : item.get("Overview"),
                     'Overlay'      : overlay,
                     'playcount'    : str(playCount)}
            
            if item.get("Type") == "ChannelVideoItem":
                xbmcplugin.setContent(_addon_id, 'movies')
            elif item.get("Type") == "ChannelAudioItem":
                xbmcplugin.setContent(_addon_id, 'songs')

            # Populate the extraData list
            extraData={'thumb'        : API().getArtwork(item, "Primary")  ,
                       'fanart_image' : API().getArtwork(item, "Backdrop") ,
                       'poster'       : API().getArtwork(item, "poster") , 
                       'tvshow.poster': API().getArtwork(item, "tvshow.poster") ,
                       'banner'       : API().getArtwork(item, "Banner") ,
                       'clearlogo'    : API().getArtwork(item, "Logo") ,
                       'discart'      : API().getArtwork(item, "Disc") ,
                       'clearart'     : API().getArtwork(item, "Art") ,
                       'landscape'    : API().getArtwork(item, "Thumb") ,
                       'id'           : id ,
                       'rating'       : item.get("CommunityRating"),
                       'year'         : item.get("ProductionYear"),
                       'premieredate' : premieredate,
                       'genre'        : genre,
                       'playcount'    : str(playCount),
                       'itemtype'     : item_type}
                       
            if extraData['thumb'] == '':
                extraData['thumb'] = extraData['fanart_image']
                
            liz = xbmcgui.ListItem(tempTitle)

            artTypes=['poster', 'tvshow.poster', 'fanart_image', 'clearlogo', 'discart', 'banner', 'clearart', 'landscape', 'small_poster', 'tiny_poster', 'medium_poster','small_fanartimage', 'medium_fanartimage', 'medium_landscape', 'fanart_noindicators']
            
            for artType in artTypes:
                imagePath=str(extraData.get(artType,''))
                liz=PlaybackUtils().setArt(liz,artType, imagePath)
            
            liz.setThumbnailImage(API().getArtwork(item, "Primary"))
            liz.setIconImage('DefaultTVShows.png')
            #liz.setInfo( type="Video", infoLabels={ "Rating": item.get("CommunityRating") })
            #liz.setInfo( type="Video", infoLabels={ "Plot": item.get("Overview") })
            
            if type=="Channel":
                file = _addon_url + "?id=%s&mode=channels"%id
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=file, listitem=liz, isFolder=True)
            
            elif isFolder == True:
                file = _addon_url + "?id=%s&mode=channelsfolder&folderid=%s" %(channelId, id)
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=file, listitem=liz, isFolder=True)
            else:
                file = _addon_url + "?id=%s&mode=play"%id
                liz.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(handle=_addon_id, url=file, listitem=liz)

    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

##### GET NEXTUP EPISODES FOR TAGNAME #####    
def getNextUpEpisodes(tagname,limit):
    #if the addon is called with nextup parameter, we return the nextepisodes list of the given tagname
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
                        liz.setProperty('IsPlayable', 'true')
                        liz.setInfo( type="Video", infoLabels={ "duration": str(item['runtime']/60) })
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
                        count +=1
                        if count == limit:
                            break
    xbmcplugin.endOfDirectory(handle=int(sys.argv[1]))

    
##### GET EXTRAFANART FOR LISTITEM #####
def getExtraFanArt():
    itemPath = ""
    embyId = ""
    #get extrafanart for listitem - this will only be used for skins that actually call the listitem's path + fanart dir... 
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
                        if(len(item["BackdropImageTags"]) > 0):
                            totalbackdrops = len(item["BackdropImageTags"]) 
                            for index in range(0,totalbackdrops): 
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

