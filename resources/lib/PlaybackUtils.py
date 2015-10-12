# -*- coding: utf-8 -*-

#################################################################################################

import datetime
import json as json
import sys

import xbmc
import xbmcaddon
import xbmcplugin
import xbmcgui

from API import API
from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ClientInformation import ClientInformation
import Utils as utils

#################################################################################################

class PlaybackUtils():
    
    clientInfo = ClientInformation()
    doUtils = DownloadUtils()
    api = API()

    addon = xbmcaddon.Addon()
    language = addon.getLocalizedString
    addonName = clientInfo.getAddonName()

    def logMsg(self, msg, lvl=1):
        
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))

    def PLAY(self, result, setup = "service"):

        self.logMsg("PLAY Called", 1)

        api = self.api
        doUtils = self.doUtils
        username = utils.window('currUser')
        server = utils.window('server%s' % username)

        id = result['Id']
        userdata = result['UserData']
        # Get the playurl - direct play, direct stream or transcoding
        playurl = PlayUtils().getPlayUrl(server, id, result)
        listItem = xbmcgui.ListItem()

        if utils.window('playurlFalse') == "true":
            # Playurl failed - set in PlayUtils.py
            utils.window('playurlFalse', clear=True)
            self.logMsg("Failed to retrieve the playback path/url or dialog was cancelled.", 1)
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listItem)

        
        ############### -- SETUP MAIN ITEM ################
            
        # Set listitem and properties for main item
        self.logMsg("Returned playurl: %s" % playurl, 1)
        listItem.setPath(playurl)
        self.setProperties(playurl, result, listItem)

        mainArt = API().getArtwork(result, "Primary")
        listItem.setThumbnailImage(mainArt)
        listItem.setIconImage(mainArt)
        

        ############### ORGANIZE CURRENT PLAYLIST ################
        
        homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        startPos = max(playlist.getposition(), 0) # Can return -1
        sizePlaylist = playlist.size()

        propertiesPlayback = utils.window('propertiesPlayback') == "true"
        introsPlaylist = False
        currentPosition = startPos

        self.logMsg("Playlist start position: %s" % startPos, 2)
        self.logMsg("Playlist plugin position: %s" % currentPosition, 2)
        self.logMsg("Playlist size: %s" % sizePlaylist, 2)


        ############### RESUME POINT ################
        
        # Resume point for widget only
        timeInfo = api.getTimeInfo(result)
        jumpBackSec = int(utils.settings('resumeJumpBack'))
        seekTime = round(float(timeInfo.get('ResumeTime')), 6)
        if seekTime > jumpBackSec:
            # To avoid negative bookmark
            seekTime = seekTime - jumpBackSec

        # Show the additional resume dialog if launched from a widget
        if homeScreen and seekTime:
            # Dialog presentation
            displayTime = str(datetime.timedelta(seconds=(int(seekTime))))
            display_list = ["%s %s" % (self.language(30106), displayTime), self.language(30107)]
            resume_result = xbmcgui.Dialog().select(self.language(30105), display_list)

            if resume_result == 0:
                # User selected to resume, append resume point to listitem
                listItem.setProperty('StartOffset', str(seekTime))
            
            elif resume_result > 0:
                # User selected to start from beginning
                seekTime = 0

            else: # User cancelled the dialog
                self.logMsg("User cancelled resume dialog.", 1)
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listItem)

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:

            utils.window('propertiesPlayback', value="true")
            self.logMsg("Setting up properties in playlist.")
            
            ############### -- CHECK FOR INTROS ################

            if utils.settings('disableCinema') == "false" and not seekTime:
                # if we have any play them when the movie/show is not being resumed
                url = "{server}/mediabrowser/Users/{UserId}/Items/%s/Intros?format=json&ImageTypeLimit=1&Fields=Etag" % id    
                intros = doUtils.downloadUrl(url)

                if intros['TotalRecordCount'] != 0:
                    for intro in intros['Items']:
                        # The server randomly returns intros, process them.
                        introId = intro['Id']
                        
                        introPlayurl = PlayUtils().getPlayUrl(server, introId, intro)
                        introListItem = xbmcgui.ListItem()
                        self.logMsg("Adding Intro: %s" % introPlayurl, 1)

                        # Set listitem and properties for intros
                        self.setProperties(introPlayurl, intro, introListItem)
                        self.setListItemProps(server, introId, introListItem, intro)
                        
                        playlist.add(introPlayurl, introListItem, index=currentPosition)
                        introsPlaylist = True
                        currentPosition += 1


            ############### -- ADD MAIN ITEM ONLY FOR HOMESCREEN ###############

            if homeScreen and not sizePlaylist:
                # Extend our current playlist with the actual item to play only if there's no playlist first
                self.logMsg("Adding main item to playlist.", 1)
                self.setListItemProps(server, id, listItem, result)
                playlist.add(playurl, listItem, index=currentPosition)
            
            # Ensure that additional parts are played after the main item
            currentPosition += 1


            ############### -- CHECK FOR ADDITIONAL PARTS ################
            
            if result.get('PartCount'):
                # Only add to the playlist after intros have played
                partcount = result['PartCount']
                url = "{server}/mediabrowser/Videos/%s/AdditionalParts" % id
                parts = doUtils.downloadUrl(url)

                for part in parts['Items']:

                    partId = part['Id']
                    additionalPlayurl = PlayUtils().getPlayUrl(server, partId, part)
                    additionalListItem = xbmcgui.ListItem()
                    self.logMsg("Adding additional part: %s" % partcount, 1)

                    # Set listitem and properties for each additional parts
                    self.setProperties(additionalPlayurl, part, additionalListItem)
                    self.setListItemProps(server, partId, additionalListItem, part)

                    playlist.add(additionalPlayurl, additionalListItem, index=currentPosition)
                    currentPosition += 1

            
            ############### ADD DUMMY TO PLAYLIST #################

            if (not homeScreen and introsPlaylist) or (homeScreen and sizePlaylist > 0):
                # Playlist will fail on the current position. Adding dummy url
                self.logMsg("Adding dummy url to counter the setResolvedUrl error.", 2)
                playlist.add(playurl, index=startPos)
                currentPosition += 1
                

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            self.logMsg("Resetting properties playback flag.", 2)
            utils.window('propertiesPlayback', clear=True)

        self.verifyPlaylist()

        ############### PLAYBACK ################
        
        if not homeScreen and not introsPlaylist:
            
            self.logMsg("Processed as a single item.", 1)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listItem)

        elif not homeScreen:

            self.logMsg("Processed as a playlist. First item is skipped.", 1)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listItem)

        else:
            self.logMsg("Play as a regular item.", 1)
            xbmc.Player().play(playlist, startpos=startPos)

                
    def verifyPlaylist(self):
        
        playlistitems = '{"jsonrpc": "2.0", "method": "Playlist.GetItems", "params": { "playlistid": 1 }, "id": 1}'
        items = xbmc.executeJSONRPC(playlistitems)
        self.logMsg(items, 2)

    def removeFromPlaylist(self, pos):

        playlistremove = '{"jsonrpc": "2.0", "method": "Playlist.Remove", "params": { "playlistid": 1, "position": %d }, "id": 1}' % pos
        result = xbmc.executeJSONRPC(playlistremove)
        self.logMsg(result, 1)


    def externalSubs(self, id, playurl, mediaSources):

        username = utils.window('currUser')
        server = utils.window('server%s' % username)
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
        utils.window('%sIndexMapping' % playurl, value=mapping)

        return externalsubs


    def setProperties(self, playurl, result, listItem):
        # Set runtimeticks, type, refresh_id and item_id
        id = result.get('Id')
        type = result.get('Type', "")

        utils.window("%sruntimeticks" % playurl, value=str(result.get('RunTimeTicks')))
        utils.window("%stype" % playurl, value=type)
        utils.window("%sitem_id" % playurl, value=id)

        if type == "Episode":
            utils.window("%srefresh_id" % playurl, value=result.get('SeriesId'))
        else:
            utils.window("%srefresh_id" % playurl, value=id)

        if utils.window("%splaymethod" % playurl) != "Transcode":
            # Only for direct play and direct stream
            # Append external subtitles to stream
            subtitleList = self.externalSubs(id, playurl, result['MediaSources'])
            listItem.setSubtitles(subtitleList)

    def setArt(self, list, name, path):
        
        if name in ("thumb", "fanart_image", "small_poster", "tiny_poster", "medium_landscape", "medium_poster", "small_fanartimage", "medium_fanartimage", "fanart_noindicators"):
            list.setProperty(name, path)
        else:
            list.setArt({name:path})
        
        return list
    
    def setListItemProps(self, server, id, listItem, result):
        # Set up item and item info
        api = self.api

        type = result.get('Type')
        people = api.getPeople(result)
        studios = api.getStudios(result)

        metadata = {
            
            'title': result.get('Name', "Missing name"),
            'year': result.get('ProductionYear'),
            'plot': api.getOverview(result),
            'director': people.get('Director'),
            'writer': people.get('Writer'),
            'mpaa': api.getMpaa(result),
            'genre': api.getGenre(result),
            'studio': " / ".join(studios),
            'aired': api.getPremiereDate(result),
            'rating': result.get('CommunityRating'),
            'votes': result.get('VoteCount')
        }

        if "Episode" in type:
            # Only for tv shows
            thumbId = result.get('SeriesId')
            season = result.get('ParentIndexNumber', -1)
            episode = result.get('IndexNumber', -1)
            show = result.get('SeriesName', "")

            metadata['TVShowTitle'] = show
            metadata['season'] = season
            metadata['episode'] = episode

        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        listItem.setLabel(metadata['title'])
        listItem.setInfo('video', infoLabels=metadata)

        # Set artwork for listitem
        self.setArt(listItem,'poster', API().getArtwork(result, "Primary"))
        self.setArt(listItem,'tvshow.poster', API().getArtwork(result, "SeriesPrimary"))
        self.setArt(listItem,'clearart', API().getArtwork(result, "Art"))
        self.setArt(listItem,'tvshow.clearart', API().getArtwork(result, "Art"))
        self.setArt(listItem,'clearlogo', API().getArtwork(result, "Logo"))
        self.setArt(listItem,'tvshow.clearlogo', API().getArtwork(result, "Logo"))
        self.setArt(listItem,'discart', API().getArtwork(result, "Disc"))
        self.setArt(listItem,'fanart_image', API().getArtwork(result, "Backdrop"))
        self.setArt(listItem,'landscape', API().getArtwork(result, "Thumb"))
    
    def seekToPosition(self, seekTo):
        # Set a loop to wait for positive confirmation of playback
        count = 0
        while not xbmc.Player().isPlaying():
            count += 1
            if count >= 10:
                return
            else:
                xbmc.sleep(500)
            
        # Jump to seek position
        count = 0
        while xbmc.Player().getTime() < (seekToTime - 5) and count < 11: # only try 10 times
            count += 1
            xbmc.Player().seekTime(seekTo)
            xbmc.sleep(100)
    
    def PLAYAllItems(self, items, startPositionTicks):
        
        self.logMsg("== ENTER: PLAYAllItems ==")
        self.logMsg("Items: %s" % items)

        doUtils = self.doUtils

        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()
        started = False

        for itemId in items:
            self.logMsg("Adding Item to playlist: %s" % itemId, 1)
            url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % itemId
            result = doUtils.downloadUrl(url)

            addition = self.addPlaylistItem(playlist, result)
            if not started and addition:
                started = True
                self.logMsg("Starting Playback Pre", 1)
                xbmc.Player().play(playlist)

        if not started:
            self.logMsg("Starting Playback Post", 1)
            xbmc.Player().play(playlist)

        # Seek to position
        if startPositionTicks:
            seekTime = startPositionTicks / 10000000.0
            self.seekToPosition(seekTime)
    
    def AddToPlaylist(self, itemIds):

        self.logMsg("== ENTER: PLAYAllItems ==")
        
        doUtils = self.doUtils
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        for itemId in itemIds:
            self.logMsg("Adding Item to Playlist: %s" % itemId)
            url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json" % itemId
            result = doUtils.downloadUrl(url)

            self.addPlaylistItem(playlist, result)
        
        return playlist
    
    def addPlaylistItem(self, playlist, item):

        id = item['Id']
        username = utils.window('currUser')
        server = utils.window('server%s' % username)

        playurl = PlayUtils().getPlayUrl(server, id, item)
        
        if utils.window('playurlFalse') == "true":
            # Playurl failed - set in PlayUtils.py
            utils.window('playurlFalse', clear=True)
            self.logMsg("Failed to retrieve the playback path/url or dialog was cancelled.", 1)
            return

        self.logMsg("Playurl: %s" % playurl)

        thumb = API().getArtwork(item, "Primary")
        listItem = xbmcgui.ListItem(path=playurl, iconImage=thumb, thumbnailImage=thumb)
        self.setListItemProps(server, id, listItem, item)
        self.setProperties(playurl, item)

        playlist.add(playurl, listItem)

    # Not currently being used
    '''def PLAYAllEpisodes(self, items):
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
        
        xbmc.Player().play(playlist)'''