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

        ############### RESUME POINT ################
        
        # Resume point for widget only
        timeInfo = api.getTimeInfo(result)
        jumpBackSec = int(utils.settings('resumeJumpBack'))
        seekTime = round(float(timeInfo.get('ResumeTime')), 6)
        if seekTime > jumpBackSec:
            # To avoid negative bookmark
            seekTime = seekTime - jumpBackSec

        # Show the additional resume dialog if launched from a widget
        if xbmc.getCondVisibility('Window.IsActive(home)') and seekTime:
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

        ############### ORGANIZE CURRENT PLAYLIST ################

        # In order, intros, original item requested and any additional part
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        startPos = max(playlist.getposition(), 0) # Can return -1
        sizePlaylist = playlist.size()
        currentPosition = startPos

        self.logMsg("Playlist start position: %s" % startPos, 2)
        self.logMsg("Playlist current position: %s" % currentPosition, 2)
        self.logMsg("Playlist size: %s" % sizePlaylist, 2)
        
        # Properties to ensure we have have proper playlists with additional items.
        introsPlaylist = False
        introProperty = utils.window('PlaylistIntroSet') == "true"
        dummyProperty = utils.window('PlaylistsetDummy') == "true"
        additionalProperty = utils.window('PlaylistAdditional') == "true"

        ############### -- CHECK FOR INTROS ################

        if utils.settings('disableCinema') == "false" and not introProperty and not seekTime:
            # if we have any play them when the movie/show is not being resumed
            url = "{server}/mediabrowser/Users/{UserId}/Items/%s/Intros?format=json&ImageTypeLimit=1&Fields=Etag" % id    
            
            intros = doUtils.downloadUrl(url)
            if intros['TotalRecordCount'] != 0:
                # The server randomly returns one custom intro
                intro = intros['Items'][0]
                introId = intro['Id']
                introListItem = xbmcgui.ListItem()
                introPlayurl = PlayUtils().getPlayUrl(server, introId, intro)

                self.logMsg("Intro play: %s" % introPlayurl, 1)

                self.setProperties(introPlayurl, intro, introListItem)
                self.setListItemProps(server, introId, introListItem, intro)
                
                introsPlaylist = True
                utils.window('PlaylistIntroSet', value="true")
                playlist.add(introPlayurl, introListItem, index=currentPosition)
                currentPosition += 1
        
        elif introProperty:
            # Play main item, do not play the intro since we already played it. Reset property for next time.
            utils.window('PlaylistIntroSet', clear=True)
            self.logMsg("Clear intro property.", 2)

        ############### -- SETUP MAIN ITEM ################
        
        ##### Set listitem and properties for main item
        self.logMsg("Returned playurl: %s" % playurl, 1)
        listItem.setPath(playurl)
        self.setProperties(playurl, result, listItem)

        mainArt = API().getArtwork(result, "Primary")
        listItem.setThumbnailImage(mainArt)
        listItem.setIconImage(mainArt)

        if introsPlaylist and not sizePlaylist:
            # Extend our current playlist with the actual item to play only if there's no playlist first
            self.logMsg("No playlist detected at the start. Creating playlist with intro and play item.", 1)
            self.logMsg("Playlist current position: %s" % (currentPosition), 1)
            playlist.add(playurl, listItem, index=currentPosition)
            currentPosition += 1

        ############### -- CHECK FOR ADDITIONAL PARTS ################

        if result.get('PartCount') and not additionalProperty:
            # Only add to the playlist after intros have played
            url = "{server}/mediabrowser/Videos/%s/AdditionalParts" % id
            
            parts = doUtils.downloadUrl(url)
            for part in parts['Items']:
                partId = part['Id']
                additionalPlayurl = PlayUtils().getPlayUrl(server, partId, part)
                additionalListItem = xbmcgui.ListItem()

                # Set listitem and properties for each additional parts
                self.logMsg("Adding to playlist: %s position: %s" % (additionalPlayurl, currentPosition), 1)
                self.setProperties(additionalPlayurl, part, additionalListItem)
                self.setListItemProps(server, partId, additionalListItem, part)

                # Add item to playlist, after the main item
                utils.window('PlaylistAdditional', value="true")
                playlist.add(additionalPlayurl, additionalListItem, index=currentPosition+1)
                currentPosition += 1
        
        elif additionalProperty:
            # Additional parts are already set, reset property for next time
            utils.window('PlaylistAdditional', clear=True)
            self.logMsg("Clear additional property", 2)

        ############### PLAYBACK ################

        if setup == "service" or xbmc.getCondVisibility('Window.IsActive(home)'):
            # Sent via websocketclient.py or default.py but via widgets
            self.logMsg("Detecting playback happening via service.py or home menu.", 1)
            self.setListItemProps(server, id, listItem, result)

            playlistPlayer = False

            if introsPlaylist and not sizePlaylist:
                # Extend our current playlist with the actual item to play only if there's no playlist first
                playlistPlayer = True

            elif sizePlaylist > 0 and not dummyProperty:
                # Playlist will fail on the current position. Adding dummy url
                playlist.add(playurl, index=startPos)
                self.logMsg("Adding dummy path as replacement for position: %s" % startPos, 2)
                utils.window('PlaylistsetDummy', value="true")
                playlistPlayer = True

            elif dummyProperty:
                # Already failed, play the item as a single item
                utils.window('PlaylistsetDummy', clear=True)
                self.logMsg("Clear dummy property.", 2)


            if playlistPlayer:
                self.logMsg("Processed as a playlist.", 1)
                return xbmc.Player().play(playlist)
            else:
                self.logMsg("Processed as a single item.", 1)
                return xbmc.Player().play(playurl, listItem)

        elif setup == "default":
            self.logMsg("Detecting playback happening via default.py.", 1)
            playlistPlayer = False

            if sizePlaylist > 0 and not dummyProperty:
                # Playlist will fail on the current position. Adding dummy url
                playlist.add(playurl, index=startPos)
                self.logMsg("Adding dummy path as replacement for position: %s" % startPos, 2)
                utils.window('PlaylistsetDummy', value="true")
                playlistPlayer = True

            elif dummyProperty:
                # Already failed, play the item as a single item
                utils.window('PlaylistsetDummy', clear=True)
                self.logMsg("Clear dummy property.", 2)

            
            if playlistPlayer:
                self.logMsg("Processed as a playlist.", 1)
                return xbmc.Player().play(playlist, startpos=startPos)
            else: # Sent via default.py
                self.logMsg("Processed as a single item.", 1)
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listItem)


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
        
        if name in {"thumb", "fanart_image", "small_poster", "tiny_poster", "medium_landscape", "medium_poster", "small_fanartimage", "medium_fanartimage", "fanart_noindicators"}:
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