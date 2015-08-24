
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
from PlayUtils import PlayUtils
from ReadKodiDB import ReadKodiDB
from ReadEmbyDB import ReadEmbyDB
import Utils as utils
from API import API
import os
import xbmcvfs

addon = xbmcaddon.Addon()
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))

WINDOW = xbmcgui.Window( 10000 )

class PlaybackUtils():
    
    settings = None
    language = addon.getLocalizedString
    logLevel = 0
    downloadUtils = DownloadUtils()

    WINDOW.clearProperty('playurlFalse')
    
    def __init__(self, *args):
        pass    

    def PLAY(self, result, setup="service"):
        xbmc.log("PLAY Called")
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        try:
            id = result["Id"]
        except:
            return

        userData = result['UserData']

        # BOOKMARK - RESUME POINT
        timeInfo = API().getTimeInfo(result)
        jumpBackSec = int(utils.settings("resumeJumpBack"))
        seekTime = round(float(timeInfo.get('ResumeTime')), 6)
        if seekTime > jumpBackSec:
            # To avoid negative bookmark
            seekTime = seekTime - jumpBackSec

        itemsToPlay = []
        # Check for intros
        if seekTime == 0:
            # if we have any play them when the movie/show is not being resumed
            # We can add the option right here
            url = "{server}/mediabrowser/Users/{UserId}/Items/%s/Intros?format=json&ImageTypeLimit=1&Fields=Etag" % id    
            intros = self.downloadUtils.downloadUrl(url)
            if intros[u'TotalRecordCount'] == 0:
                pass
            else:
                for intro in intros[u'Items']:
                    introId = intro[u'Id']
                    itemsToPlay.append(introId)

        # Add original item
        itemsToPlay.append(id)
        
        # For split movies
        if u'PartCount' in result:
            partcount = result[u'PartCount']
            # Get additional parts/playurl
            url = "{server}/mediabrowser/Videos/%s/AdditionalParts" % id
            parts = self.downloadUtils.downloadUrl(url)
            for part in parts[u'Items']:
                partId = part[u'Id']
                itemsToPlay.append(partId)

        if len(itemsToPlay) > 1:
            # Let's play the playlist
            return self.AddToPlaylist(itemsToPlay)

        playurl = PlayUtils().getPlayUrl(server, id, result)

        if playurl == False or WINDOW.getProperty('playurlFalse') == "true":
            WINDOW.clearProperty('playurlFalse')
            xbmc.log("Failed to retrieve the playback path/url.")
            return

        if WINDOW.getProperty("%splaymethod" % playurl) == "Transcode":
            # Transcoding, we pull every track to set before playback starts
            playurlprefs = self.audioSubsPref(playurl, result.get("MediaSources"))
            if playurlprefs:
                playurl = playurlprefs
            else: # User cancelled dialog
                return


        thumbPath = API().getArtwork(result, "Primary")
        
        #if the file is a virtual strm file, we need to override the path by reading it's contents
        if playurl.endswith(".strm"):
            xbmc.log("virtual strm file file detected, starting playback with 3th party addon...")
            StrmTemp = "special://temp/temp.strm"
            xbmcvfs.copy(playurl, StrmTemp)
            playurl = open(xbmc.translatePath(StrmTemp), 'r').readline()
                 
        listItem = xbmcgui.ListItem(path=playurl, iconImage=thumbPath, thumbnailImage=thumbPath)

        if WINDOW.getProperty("%splaymethod" % playurl) != "Transcode":
            # Only for direct play and direct stream
            # Append external subtitles to stream
            subtitleList = self.externalSubs(id, playurl, server, result.get('MediaSources'))
            listItem.setSubtitles(subtitleList)
            #pass

        # Can not play virtual items
        if (result.get("LocationType") == "Virtual"):
          xbmcgui.Dialog().ok(self.language(30128), self.language(30129))

        watchedurl = "%s/mediabrowser/Users/%s/PlayedItems/%s" % (server, userid, id)
        positionurl = "%s/mediabrowser/Users/%s/PlayingItems/%s" % (server, userid, id)
        deleteurl = "%s/mediabrowser/Items/%s" % (server, id)

        # set the current playing info
        WINDOW.setProperty(playurl+"watchedurl", watchedurl)
        WINDOW.setProperty(playurl+"positionurl", positionurl)
        WINDOW.setProperty(playurl+"deleteurl", "")
        WINDOW.setProperty(playurl+"deleteurl", deleteurl)

        #show the additional resume dialog if launched from a widget
        if xbmc.getCondVisibility("Window.IsActive(home)"):
            if seekTime != 0:
                displayTime = str(datetime.timedelta(seconds=(int(seekTime))))
                display_list = [ self.language(30106) + ' ' + displayTime, self.language(30107)]
                resumeScreen = xbmcgui.Dialog()
                resume_result = resumeScreen.select(self.language(30105), display_list)
                if resume_result == 0:
                    listItem.setProperty('StartOffset', str(seekTime))

                elif resume_result < 0:
                    # User cancelled dialog
                    xbmc.log("Emby player -> User cancelled resume dialog.")
                    xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listItem)
                    return

        if result.get("Type")=="Episode":
            WINDOW.setProperty(playurl+"refresh_id", result.get("SeriesId"))
        else:
            WINDOW.setProperty(playurl+"refresh_id", id)
            
        WINDOW.setProperty(playurl+"runtimeticks", str(result.get("RunTimeTicks")))
        WINDOW.setProperty(playurl+"type", result.get("Type"))
        WINDOW.setProperty(playurl+"item_id", id)

        #launch the playback - only set the listitem props if we're not using the setresolvedurl approach
        if setup == "service":
            self.setListItemProps(server, id, listItem, result)
            xbmc.Player().play(playurl,listItem)
        elif setup == "default":
            if xbmc.getCondVisibility("Window.IsActive(home)"):
                self.setListItemProps(server, id, listItem, result)
                xbmc.Player().play(playurl,listItem)   
            else:
               xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listItem)

    def externalSubs(self, id, playurl, server, mediaSources):

        externalsubs = []
        mapping = {}

        mediaStream = mediaSources[0].get('MediaStreams')
        kodiindex = 0
        for stream in mediaStream:
            
            index = stream['Index']
            # Since Emby returns all possible tracks together, have to pull only external subtitles.
            # IsTextSubtitleStream if true, is available to download from emby.
            if "Subtitle" in stream['Type'] and stream['IsExternal'] and stream['IsTextSubtitleStream']:
                
                playmethod = utils.window("%splaymethod" % playurl)

                if "DirectPlay" in playmethod:
                    # Direct play, get direct path
                    url = PlayUtils().directPlay(stream)
                elif "DirectStream" in playmethod: # Direct stream
                    url = "%s/Videos/%s/%s/Subtitles/%s/Stream.srt" % (server, id, id, index)
                
                # map external subtitles for mapping
                mapping[kodiindex] = index
                externalsubs.append(url)
                kodiindex += 1
        
        mapping = json.dumps(mapping)
        utils.window('%sIndexMapping' % playurl, mapping)

        return externalsubs

    def audioSubsPref(self, url, mediaSources):

        WINDOW = xbmcgui.Window(10000)
        # Present the list of audio to select from
        audioStreamsList = {}
        audioStreams = []
        selectAudioIndex = ""
        subtitleStreamsList = {}
        subtitleStreams = ['No subtitles']
        selectSubsIndex = ""
        playurlprefs = "%s" % url

        mediaStream = mediaSources[0].get('MediaStreams')
        for stream in mediaStream:
            index = stream['Index']
            # Since Emby returns all possible tracks together, have to sort them.
            if 'Audio' in stream['Type']:
                try:
                    track = stream['Language']
                    audioStreamsList[track] = index
                    audioStreams.append(track)
                except:
                    track = stream['Codec']
                    audioStreamsList[track] = index
                    audioStreams.append(track)

            elif 'Subtitle' in stream['Type']:
                try:
                    track = stream['Language']
                    subtitleStreamsList[track] = index
                    subtitleStreams.append(track)
                except:
                    track = stream['Codec']
                    subtitleStreamsList[track] = index
                    subtitleStreams.append(track)

        if len(audioStreams) > 1:
            resp = xbmcgui.Dialog().select("Choose the audio stream", audioStreams)
            if resp > -1:
                # User selected audio
                selected = audioStreams[resp]
                selected_audioIndex = audioStreamsList[selected]
                playurlprefs += "&AudioStreamIndex=%s" % selected_audioIndex
                selectAudioIndex = str(selected_audioIndex)
            else: return False
        else: # There's only one audiotrack.
            audioIndex = audioStreamsList[audioStreams[0]]
            playurlprefs += "&AudioStreamIndex=%s" % audioIndex
            selectAudioIndex = str(audioIndex)

        if len(subtitleStreams) > 1:
            resp = xbmcgui.Dialog().select("Choose the subtitle stream", subtitleStreams)
            if resp == 0:
                # User selected no subtitles
                pass
            elif resp > -1:
                # User selected subtitles
                selected = subtitleStreams[resp]
                selected_subsIndex = subtitleStreamsList[selected]
                playurlprefs += "&SubtitleStreamIndex=%s" % selected_subsIndex
                selectSubsIndex = str(selected_subsIndex)
            else: return False
        
        # Reset the method with the new playurl
        WINDOW.setProperty("%splaymethod" % playurlprefs, "Transcode")
        WINDOW.setProperty("%sAudioStreamIndex" % playurlprefs, selectAudioIndex)
        WINDOW.setProperty("%sSubtitleStreamIndex" % playurlprefs, selectSubsIndex)

        return playurlprefs

    def setArt(self, list,name,path):
        if name=='thumb' or name=='fanart_image' or name=='small_poster' or name=='tiny_poster'  or name == "medium_landscape" or name=='medium_poster' or name=='small_fanartimage' or name=='medium_fanartimage' or name=='fanart_noindicators':
            list.setProperty(name, path)
        else:
            list.setArt({name:path})
        return list
    
    def setListItemProps(self, server, id, listItem, result):
        # set up item and item info
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
            
        details = {
                 'title'        : result.get("Name", "Missing Name"),
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
        listItem.setInfo('video', {'genre': API().getGenre(result)})
    
    def seekToPosition(self, seekTo):
    
        #Set a loop to wait for positive confirmation of playback
        count = 0
        while not xbmc.Player().isPlaying():
            count = count + 1
            if count >= 10:
                return
            else:
                xbmc.sleep(500)
            
        #Jump to resume point
        jumpBackSec = int(addon.getSetting("resumeJumpBack"))
        seekToTime = seekTo - jumpBackSec
        count = 0
        while xbmc.Player().getTime() < (seekToTime - 5) and count < 11: # only try 10 times
            count = count + 1
            #xbmc.Player().pause
            #xbmc.sleep(100)
            xbmc.Player().seekTime(seekToTime)
            xbmc.sleep(100)
            #xbmc.Player().play()
    
    def PLAYAllItems(self, items, startPositionTicks):
        utils.logMsg("PlayBackUtils", "== ENTER: PLAYAllItems ==")
        utils.logMsg("PlayBackUtils", "Items : " + str(items))
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()        
        started = False
        
        for itemID in items:
        
            utils.logMsg("PlayBackUtils", "Adding Item to Playlist : " + itemID)
            item_url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % itemID
            jsonData = self.downloadUtils.downloadUrl(item_url)

            item_data = jsonData
            added = self.addPlaylistItem(playlist, item_data, server, userid)
            if(added and started == False):
                started = True
                utils.logMsg("PlayBackUtils", "Starting Playback Pre")
                xbmc.Player().play(playlist)
        
        if(started == False):
            utils.logMsg("PlayBackUtils", "Starting Playback Post")
            xbmc.Player().play(playlist)
        
        #seek to position
        seekTime = 0
        if(startPositionTicks != None):
            seekTime = (startPositionTicks / 1000) / 10000
            
        if seekTime > 0:
            self.seekToPosition(seekTime)
            
    def PLAYAllEpisodes(self, items):
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()        
        
        for item in items:
        
            item_url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1" % item["Id"]
            jsonData = self.downloadUtils.downloadUrl(item_url)
            
            item_data = jsonData
            self.addPlaylistItem(playlist, item_data, server, userid)
        
        xbmc.Player().play(playlist)
    
    def AddToPlaylist(self, itemIds):
        utils.logMsg("PlayBackUtils", "== ENTER: PLAYAllItems ==")
        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)     
        
        for itemID in itemIds:
        
            utils.logMsg("PlayBackUtils", "Adding Item to Playlist : " + itemID)
            item_url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % itemID
            jsonData = self.downloadUtils.downloadUrl(item_url)
            
            item_data = jsonData
            self.addPlaylistItem(playlist, item_data, server, userid)
    
        return playlist
    
    def addPlaylistItem(self, playlist, item, server, userid):

        id = item.get("Id")
        
        playurl = PlayUtils().getPlayUrl(server, id, item)
        utils.logMsg("PlayBackUtils", "Play URL: " + playurl)    
        thumbPath = API().getArtwork(item, "Primary")
        listItem = xbmcgui.ListItem(path=playurl, iconImage=thumbPath, thumbnailImage=thumbPath)
        self.setListItemProps(server, id, listItem, item)

        WINDOW = xbmcgui.Window(10000)

        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)

        # Can not play virtual items
        if (item.get("LocationType") == "Virtual") or (item.get("IsPlaceHolder") == True):
        
            xbmcgui.Dialog().ok(self.language(30128), self.language(30129))
            return False
            
        else:
        
            watchedurl = "%s/mediabrowser/Users/%s/PlayedItems/%s" % (server, userid, id)
            positionurl = "%s/mediabrowser/Users/%s/PlayingItems/%s" % (server, userid, id)
            deleteurl = "%s/mediabrowser/Items/%s" % (server, id)

            # set the current playing info
            WINDOW = xbmcgui.Window( 10000 )
            WINDOW.setProperty(playurl + "watchedurl", watchedurl)
            WINDOW.setProperty(playurl + "positionurl", positionurl)
            WINDOW.setProperty(playurl + "deleteurl", "")
            
            if item.get("Type") == "Episode" and addon.getSetting("offerDeleteTV")=="true":
               WINDOW.setProperty(playurl + "deleteurl", deleteurl)
            if item.get("Type") == "Movie" and addon.getSetting("offerDeleteMovies")=="true":
               WINDOW.setProperty(playurl + "deleteurl", deleteurl)            
        
            WINDOW.setProperty(playurl + "runtimeticks", str(item.get("RunTimeTicks")))
            WINDOW.setProperty(playurl+"type", item.get("Type"))
            WINDOW.setProperty(playurl + "item_id", id)
            
            if (item.get("Type") == "Episode"):
                WINDOW.setProperty(playurl + "refresh_id", item.get("SeriesId"))
            else:
                WINDOW.setProperty(playurl + "refresh_id", id)            
            
            utils.logMsg("PlayBackUtils", "PlayList Item Url : " + str(playurl))
            
            playlist.add(playurl, listItem)
            
            return True