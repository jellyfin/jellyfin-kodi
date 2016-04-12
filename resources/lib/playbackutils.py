# -*- coding: utf-8 -*-

#################################################################################################

import json
import sys

import xbmc
import xbmcgui
import xbmcplugin

import api
import artwork
import clientinfo
import downloadutils
import playutils as putils
import playlist
import read_embyserver as embyserver
import utils

#################################################################################################


class PlaybackUtils():
    
    
    def __init__(self, item):

        self.item = item
        self.API = api.API(self.item)

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl

        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.pl = playlist.Playlist()

    def logMsg(self, msg, lvl=1):

        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, lvl)


    def play(self, itemid, dbid=None):

        window = utils.window
        settings = utils.settings

        listitem = xbmcgui.ListItem()
        playutils = putils.PlayUtils(self.item)

        self.logMsg("Play called.", 1)
        playurl = playutils.getPlayUrl()
        if not playurl:
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if dbid is None:
            # Item is not in Kodi database
            listitem.setPath(playurl)
            self.setProperties(playurl, listitem)
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        ############### ORGANIZE CURRENT PLAYLIST ################
        
        homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        startPos = max(playlist.getposition(), 0) # Can return -1
        sizePlaylist = playlist.size()
        currentPosition = startPos

        propertiesPlayback = window('emby_playbackProps') == "true"
        introsPlaylist = False
        dummyPlaylist = False

        self.logMsg("Playlist start position: %s" % startPos, 2)
        self.logMsg("Playlist plugin position: %s" % currentPosition, 2)
        self.logMsg("Playlist size: %s" % sizePlaylist, 2)

        ############### RESUME POINT ################
        
        userdata = self.API.getUserData()
        seektime = self.API.adjustResume(userdata['Resume'])

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:

            window('emby_playbackProps', value="true")
            self.logMsg("Setting up properties in playlist.", 1)

            if (not homeScreen and not seektime and 
                    window('emby_customPlaylist') != "true"):
                
                self.logMsg("Adding dummy file to playlist.", 2)
                dummyPlaylist = True
                playlist.add(playurl, listitem, index=startPos)
                # Remove the original item from playlist 
                self.pl.removefromPlaylist(startPos+1)
                # Readd the original item to playlist - via jsonrpc so we have full metadata
                self.pl.insertintoPlaylist(currentPosition+1, dbid, self.item['Type'].lower())
                currentPosition += 1
            
            ############### -- CHECK FOR INTROS ################

            if settings('enableCinema') == "true" and not seektime:
                # if we have any play them when the movie/show is not being resumed
                url = "{server}/emby/Users/{UserId}/Items/%s/Intros?format=json" % itemid    
                intros = self.doUtils(url)

                if intros['TotalRecordCount'] != 0:
                    getTrailers = True

                    if settings('askCinema') == "true":
                        resp = xbmcgui.Dialog().yesno("Emby for Kodi", utils.language(33016))
                        if not resp:
                            # User selected to not play trailers
                            getTrailers = False
                            self.logMsg("Skip trailers.", 1)
                    
                    if getTrailers:
                        for intro in intros['Items']:
                            # The server randomly returns intros, process them.
                            introListItem = xbmcgui.ListItem()
                            introPlayurl = putils.PlayUtils(intro).getPlayUrl()
                            self.logMsg("Adding Intro: %s" % introPlayurl, 1)

                            # Set listitem and properties for intros
                            pbutils = PlaybackUtils(intro)
                            pbutils.setProperties(introPlayurl, introListItem)

                            self.pl.insertintoPlaylist(currentPosition, url=introPlayurl)
                            introsPlaylist = True
                            currentPosition += 1


            ############### -- ADD MAIN ITEM ONLY FOR HOMESCREEN ###############

            if homeScreen and not seektime and not sizePlaylist:
                # Extend our current playlist with the actual item to play
                # only if there's no playlist first
                self.logMsg("Adding main item to playlist.", 1)
                self.pl.addtoPlaylist(dbid, self.item['Type'].lower())

            # Ensure that additional parts are played after the main item
            currentPosition += 1

            ############### -- CHECK FOR ADDITIONAL PARTS ################
            
            if self.item.get('PartCount'):
                # Only add to the playlist after intros have played
                partcount = self.item['PartCount']
                url = "{server}/emby/Videos/%s/AdditionalParts?format=json" % itemid
                parts = self.doUtils(url)
                for part in parts['Items']:

                    additionalListItem = xbmcgui.ListItem()
                    additionalPlayurl = putils.PlayUtils(part).getPlayUrl()
                    self.logMsg("Adding additional part: %s" % partcount, 1)

                    # Set listitem and properties for each additional parts
                    pbutils = PlaybackUtils(part)
                    pbutils.setProperties(additionalPlayurl, additionalListItem)
                    pbutils.setArtwork(additionalListItem)

                    playlist.add(additionalPlayurl, additionalListItem, index=currentPosition)
                    self.pl.verifyPlaylist()
                    currentPosition += 1

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                self.logMsg("Processed as a playlist. First item is skipped.", 1)
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)
                

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            self.logMsg("Resetting properties playback flag.", 2)
            window('emby_playbackProps', clear=True)

        #self.pl.verifyPlaylist()
        ########## SETUP MAIN ITEM ##########

        # For transcoding only, ask for audio/subs pref
        if window('emby_%s.playmethod' % playurl) == "Transcode":
            playurl = playutils.audioSubsPref(playurl, listitem)
            window('emby_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        self.setProperties(playurl, listitem)

        ############### PLAYBACK ################

        if homeScreen and seektime and window('emby_customPlaylist') != "true":
            self.logMsg("Play as a widget item.", 1)
            self.setListItem(listitem)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        elif ((introsPlaylist and window('emby_customPlaylist') == "true") or
                (homeScreen and not sizePlaylist)):
            # Playlist was created just now, play it.
            self.logMsg("Play playlist.", 1)
            xbmc.Player().play(playlist, startpos=startPos)

        else:
            self.logMsg("Play as a regular item.", 1)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

    def setProperties(self, playurl, listitem):

        window = utils.window
        # Set all properties necessary for plugin path playback
        itemid = self.item['Id']
        itemtype = self.item['Type']

        embyitem = "emby_%s" % playurl
        window('%s.runtime' % embyitem, value=str(self.item.get('RunTimeTicks')))
        window('%s.type' % embyitem, value=itemtype)
        window('%s.itemid' % embyitem, value=itemid)

        if itemtype == "Episode":
            window('%s.refreshid' % embyitem, value=self.item.get('SeriesId'))
        else:
            window('%s.refreshid' % embyitem, value=itemid)

        # Append external subtitles to stream
        playmethod = utils.window('%s.playmethod' % embyitem)
        # Only for direct stream
        if playmethod in ("DirectStream"):
            # Direct play automatically appends external
            subtitles = self.externalSubs(playurl)
            listitem.setSubtitles(subtitles)

        self.setArtwork(listitem)

    def externalSubs(self, playurl):

        externalsubs = []
        mapping = {}

        itemid = self.item['Id']
        try:
            mediastreams = self.item['MediaSources'][0]['MediaStreams']
        except (TypeError, KeyError, IndexError):
            return

        kodiindex = 0
        for stream in mediastreams:

            index = stream['Index']
            # Since Emby returns all possible tracks together, have to pull only external subtitles.
            # IsTextSubtitleStream if true, is available to download from emby.
            if (stream['Type'] == "Subtitle" and 
                    stream['IsExternal'] and stream['IsTextSubtitleStream']):

                # Direct stream
                url = ("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                        % (self.server, itemid, itemid, index))
                
                # map external subtitles for mapping
                mapping[kodiindex] = index
                externalsubs.append(url)
                kodiindex += 1
        
        mapping = json.dumps(mapping)
        utils.window('emby_%s.indexMapping' % playurl, value=mapping)

        return externalsubs

    def setArtwork(self, listItem):
        # Set up item and item info
        allartwork = self.artwork.getAllArtwork(self.item, parentInfo=True)
        # Set artwork for listitem
        arttypes = {

            'poster': "Primary",
            'tvshow.poster': "Primary",
            'clearart': "Art",
            'tvshow.clearart': "Art",
            'clearlogo': "Logo",
            'tvshow.clearlogo': "Logo",
            'discart': "Disc",
            'fanart_image': "Backdrop",
            'landscape': "Thumb"
        }
        for arttype in arttypes:

            art = arttypes[arttype]
            if art == "Backdrop":
                try: # Backdrop is a list, grab the first backdrop
                    self.setArtProp(listItem, arttype, allartwork[art][0])
                except: pass
            else:
                self.setArtProp(listItem, arttype, allartwork[art])

    def setArtProp(self, listItem, arttype, path):
        
        if arttype in (
                'thumb', 'fanart_image', 'small_poster', 'tiny_poster',
                'medium_landscape', 'medium_poster', 'small_fanartimage',
                'medium_fanartimage', 'fanart_noindicators'):
            
            listItem.setProperty(arttype, path)
        else:
            listItem.setArt({arttype: path})

    def setListItem(self, listItem):

        people = self.API.getPeople()
        studios = self.API.getStudios()

        metadata = {
            
            'title': self.item.get('Name', "Missing name"),
            'year': self.item.get('ProductionYear'),
            'plot': self.API.getOverview(),
            'director': people.get('Director'),
            'writer': people.get('Writer'),
            'mpaa': self.API.getMpaa(),
            'genre': " / ".join(self.item['Genres']),
            'studio': " / ".join(studios),
            'aired': self.API.getPremiereDate(),
            'rating': self.item.get('CommunityRating'),
            'votes': self.item.get('VoteCount')
        }

        if "Episode" in self.item['Type']:
            # Only for tv shows
            thumbId = self.item.get('SeriesId')
            season = self.item.get('ParentIndexNumber', -1)
            episode = self.item.get('IndexNumber', -1)
            show = self.item.get('SeriesName', "")

            metadata['TVShowTitle'] = show
            metadata['season'] = season
            metadata['episode'] = episode

        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        listItem.setLabel(metadata['title'])
        listItem.setInfo('video', infoLabels=metadata)