
import xbmc
import xbmcplugin
import xbmcgui
import xbmcaddon
import urllib
import datetime
import time
import json as json
import inspect
import sys

from DownloadUtils import DownloadUtils
downloadUtils = DownloadUtils()
from PlayUtils import PlayUtils
from API import API
import Utils as utils

addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
language = addon.getLocalizedString   

WINDOW = xbmcgui.Window( 10000 )
port = addon.getSetting('port')
host = addon.getSetting('ipaddress')
server = host + ":" + port
userid = downloadUtils.getUserId()


class PlaybackUtils():
    
    settings = None
    language = None 
    logLevel = 0

    
    def __init__(self, *args):
        pass    


    def PLAY(self, id):
        
        jsonData = downloadUtils.downloadUrl("http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + id + "?format=json&ImageTypeLimit=1", suppress=False, popup=1 )     
        result = json.loads(jsonData)

        userData = result.get("UserData")
        resume_result = 0
        seekTime = 0

        if userData.get("PlaybackPositionTicks") != 0:
            reasonableTicks = int(userData.get("PlaybackPositionTicks")) / 1000
            seekTime = reasonableTicks / 10000
            displayTime = str(datetime.timedelta(seconds=seekTime))
            display_list = [ language(30106) + ' ' + displayTime, language(30107)]
            resumeScreen = xbmcgui.Dialog()
            resume_result = resumeScreen.select(language(30105), display_list)

        
        playurl = PlayUtils().getPlayUrl(server, id, result)
        xbmc.log("Play URL: " + playurl)    
        thumbPath = API().getArtwork(result, "Primary")
        listItem = xbmcgui.ListItem(path=playurl, iconImage=thumbPath, thumbnailImage=thumbPath)

        self.setListItemProps(server, id, listItem, result)    

        # Can not play virtual items
        if (result.get("LocationType") == "Virtual"):
          xbmcgui.Dialog().ok(self.language(30128), language(30129))

        watchedurl = 'http://' + server + '/mediabrowser/Users/'+ userid + '/PlayedItems/' + id
        positionurl = 'http://' + server + '/mediabrowser/Users/'+ userid + '/PlayingItems/' + id
        deleteurl = 'http://' + server + '/mediabrowser/Items/' + id

        # set the current playing info
        WINDOW.setProperty(playurl+"watchedurl", watchedurl)
        WINDOW.setProperty(playurl+"positionurl", positionurl)
        WINDOW.setProperty(playurl+"deleteurl", "")
        WINDOW.setProperty(playurl+"deleteurl", deleteurl)
        if resume_result == 0:
            WINDOW.setProperty(playurl+"seektime", str(seekTime))
        else:
            WINDOW.clearProperty(playurl+"seektime")

        if result.get("Type")=="Episode":
            WINDOW.setProperty(playurl+"refresh_id", result.get("SeriesId"))
        else:
            WINDOW.setProperty(playurl+"refresh_id", id)
            
        WINDOW.setProperty(playurl+"runtimeticks", str(result.get("RunTimeTicks")))
        WINDOW.setProperty(playurl+"type", result.get("Type"))
        WINDOW.setProperty(playurl+"item_id", id)

        if PlayUtils().isDirectPlay(result) == True:
            playMethod = "DirectPlay"
        else:
            playMethod = "Transcode"
            
          
        WINDOW.setProperty(playurl+"playmethod", playMethod)
            
        mediaSources = result.get("MediaSources")
        if(mediaSources != None):
            if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                WINDOW.setProperty(playurl+"AudioStreamIndex", str(mediaSources[0].get('DefaultAudioStreamIndex')))  
            if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                WINDOW.setProperty(playurl+"SubtitleStreamIndex", str(mediaSources[0].get('DefaultSubtitleStreamIndex')))

        #this launches the playback
        #artwork only works with both resolvedurl and player command
        xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listItem)
        xbmc.Player().play(playurl,listItem)

    def setArt(self, list,name,path):
        if name=='thumb' or name=='fanart_image' or name=='small_poster' or name=='tiny_poster'  or name == "medium_landscape" or name=='medium_poster' or name=='small_fanartimage' or name=='medium_fanartimage' or name=='fanart_noindicators':
            list.setProperty(name, path)
        else:
            list.setArt({name:path})
        return list
    
    def setListItemProps(self, server, id, listItem, result):
        # set up item and item info
        userid = downloadUtils.getUserId()
        thumbID = id
        eppNum = -1
        seasonNum = -1
        tvshowTitle = ""
        
        if(result.get("Type") == "Episode"):
            thumbID = result.get("SeriesId")
            seasonNum = result.get("ParentIndexNumber")
            eppNum = result.get("IndexNumber")
            tvshowTitle = result.get("SeriesName")
            
        self.setArt(listItem,'poster', API().getArtwork(result, "Primary"))
        self.setArt(listItem,'tvshow.poster', API().getArtwork(result, "SeriesPrimary"))
        self.setArt(listItem,'clearart', API().getArtwork(result, "Art"))
        self.setArt(listItem,'tvshow.clearart', API().getArtwork(result, "Art"))    
        self.setArt(listItem,'clearlogo', API().getArtwork(result, "Logo"))
        self.setArt(listItem,'tvshow.clearlogo', API().getArtwork(result, "Logo"))    
        self.setArt(listItem,'discart', API().getArtwork(result, "Disc"))  
        self.setArt(listItem,'fanart_image', API().getArtwork(result, "Backdrop"))
        self.setArt(listItem,'landscape', API().getArtwork(result, "Thumb"))   
        
        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        
        # Process Studios
        studios = API().getStudios(result)
        if studios == []:
            studio = ""
        else:
            studio = studios[0]
        listItem.setInfo('video', {'studio' : studio})    

        # play info
        playinformation = ''
        if PlayUtils().isDirectPlay(result) == True:
            playinformation = language(30165)
        else:
            playinformation = language(30166)
            
        details = {
                 'title'        : result.get("Name", "Missing Name") + ' - ' + playinformation,
                 'plot'         : result.get("Overview")
                 }
                 
        if(eppNum > -1):
            details["episode"] = str(eppNum)
            
        if(seasonNum > -1):
            details["season"] = str(seasonNum)  

        if tvshowTitle != None:
            details["TVShowTitle"] = tvshowTitle	
        
        listItem.setInfo( "Video", infoLabels=details )

        people = API().getPeople(result)

        # Process Genres
        genre = API().getGenre(result)
        
        listItem.setInfo('video', {'director' : people.get('Director')})
        listItem.setInfo('video', {'writer' : people.get('Writer')})
        listItem.setInfo('video', {'mpaa': result.get("OfficialRating")})
        listItem.setInfo('video', {'genre': genre})
