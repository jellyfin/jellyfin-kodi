# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import requests
import os
import shutil
import sys

import xbmc
import xbmcgui
import xbmcplugin
import xbmcvfs

import api
import artwork
import downloadutils
import playutils as putils
import playlist
import read_embyserver as embyserver
import shutil
from utils import window, settings, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class PlaybackUtils():
    
    
    def __init__(self, item):

        self.item = item
        self.API = api.API(self.item)

        self.doUtils = downloadutils.DownloadUtils().downloadUrl

        self.userid = window('emby_currUser')
        self.server = window('emby_server%s' % self.userid)

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.pl = playlist.Playlist()


    def play(self, itemid, dbid=None):

        listitem = xbmcgui.ListItem()
        playutils = putils.PlayUtils(self.item)

        log.info("Play called.")
        playurl = playutils.getPlayUrl()
        if not playurl:
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if dbid is None:
            # Item is not in Kodi database
            listitem.setPath(playurl)
            self.setProperties(playurl, listitem)
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        # TODO: Review once Krypton is RC, no need for workaround.

        ############### ORGANIZE CURRENT PLAYLIST ################
        
        homeScreen = xbmc.getCondVisibility('Window.IsActive(home)')
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        startPos = max(playlist.getposition(), 0) # Can return -1
        sizePlaylist = playlist.size()
        currentPosition = startPos

        propertiesPlayback = window('emby_playbackProps') == "true"
        introsPlaylist = False
        dummyPlaylist = False

        log.debug("Playlist start position: %s" % startPos)
        log.debug("Playlist plugin position: %s" % currentPosition)
        log.debug("Playlist size: %s" % sizePlaylist)

        ############### RESUME POINT ################
        
        userdata = self.API.get_userdata()
        seektime = self.API.adjust_resume(userdata['Resume'])

        # We need to ensure we add the intro and additional parts only once.
        # Otherwise we get a loop.
        if not propertiesPlayback:

            window('emby_playbackProps', value="true")
            log.info("Setting up properties in playlist.")

            if not homeScreen and not seektime and window('emby_customPlaylist') != "true":
                
                log.debug("Adding dummy file to playlist.")
                dummyPlaylist = True
                playlist.add(playurl, listitem, index=startPos)
                # Remove the original item from playlist 
                self.pl.remove_from_playlist(startPos+1)
                # Readd the original item to playlist - via jsonrpc so we have full metadata
                self.pl.insert_to_playlist(currentPosition+1, dbid, self.item['Type'].lower())
                currentPosition += 1
            
            ############### -- CHECK FOR INTROS ################

            if settings('enableCinema') == "true" and not seektime:
                # if we have any play them when the movie/show is not being resumed
                url = "{server}/emby/Users/{UserId}/Items/%s/Intros?format=json" % itemid    
                intros = self.doUtils(url)

                if intros['TotalRecordCount'] != 0:
                    getTrailers = True

                    if settings('askCinema') == "true":
                        resp = xbmcgui.Dialog().yesno("Emby for Kodi", lang(33016))
                        if not resp:
                            # User selected to not play trailers
                            getTrailers = False
                            log.info("Skip trailers.")
                    
                    if getTrailers:
                        for intro in intros['Items']:
                            # The server randomly returns intros, process them.
                            introListItem = xbmcgui.ListItem()
                            introPlayurl = putils.PlayUtils(intro).getPlayUrl()
                            log.info("Adding Intro: %s" % introPlayurl)

                            # Set listitem and properties for intros
                            pbutils = PlaybackUtils(intro)
                            pbutils.setProperties(introPlayurl, introListItem)

                            self.pl.insert_to_playlist(currentPosition, url=introPlayurl)
                            introsPlaylist = True
                            currentPosition += 1


            ############### -- ADD MAIN ITEM ONLY FOR HOMESCREEN ###############

            if homeScreen and not seektime and not sizePlaylist:
                # Extend our current playlist with the actual item to play
                # only if there's no playlist first
                log.info("Adding main item to playlist.")
                self.pl.add_to_playlist(dbid, self.item['Type'].lower())

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
                    log.info("Adding additional part: %s" % partcount)

                    # Set listitem and properties for each additional parts
                    pbutils = PlaybackUtils(part)
                    pbutils.setProperties(additionalPlayurl, additionalListItem)
                    pbutils.setArtwork(additionalListItem)

                    playlist.add(additionalPlayurl, additionalListItem, index=currentPosition)
                    self.pl.verify_playlist()
                    currentPosition += 1

            if dummyPlaylist:
                # Added a dummy file to the playlist,
                # because the first item is going to fail automatically.
                log.info("Processed as a playlist. First item is skipped.")
                return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)
                

        # We just skipped adding properties. Reset flag for next time.
        elif propertiesPlayback:
            log.debug("Resetting properties playback flag.")
            window('emby_playbackProps', clear=True)

        #self.pl.verify_playlist()
        ########## SETUP MAIN ITEM ##########

        # For transcoding only, ask for audio/subs pref
        if window('emby_%s.playmethod' % playurl) == "Transcode":
            # Filter ISO since Emby does not probe anymore
            if self.item.get('VideoType') == "Iso":
                log.info("Skipping audio/subs prompt, ISO detected.")
            else:
                playurl = playutils.audioSubsPref(playurl, listitem)
                window('emby_%s.playmethod' % playurl, value="Transcode")

        listitem.setPath(playurl)
        self.setProperties(playurl, listitem)

        ############### PLAYBACK ################

        if homeScreen and seektime and window('emby_customPlaylist') != "true":
            log.info("Play as a widget item.")
            self.setListItem(listitem)
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

        elif ((introsPlaylist and window('emby_customPlaylist') == "true") or
                (homeScreen and not sizePlaylist)):
            # Playlist was created just now, play it.
            log.info("Play playlist.")
            xbmc.Player().play(playlist, startpos=startPos)

        else:
            log.info("Play as a regular item.")
            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, listitem)

    def setProperties(self, playurl, listitem):

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
        playmethod = window('%s.playmethod' % embyitem)
        # Only for direct stream
        if playmethod in ("DirectStream") and settings('enableExternalSubs') == "true":
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

        temp = xbmc.translatePath(
               "special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

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

                if "Language" in stream:
                    
                    filename = "Stream.%s.srt" % stream['Language']
                    try:
                        path = self._download_external_subs(url, temp, filename)
                        externalsubs.append(path)
                    except Exception as e:
                        log.error(e)
                        continue
                else:
                    externalsubs.append(url)
                
                # map external subtitles for mapping
                mapping[kodiindex] = index
                kodiindex += 1
        
        mapping = json.dumps(mapping)
        window('emby_%s.indexMapping' % playurl, value=mapping)

        return externalsubs

    def _download_external_subs(self, src, dst, filename):

        if not xbmcvfs.exists(dst):
            xbmcvfs.mkdir(dst)

        path = os.path.join(dst, filename)

        try:
            response = requests.get(src, stream=True)
            response.encoding = 'utf-8'
            response.raise_for_status()
        except Exception as e:
            del response
            raise
        else:
            with open(path, 'wb') as f:
                f.write(response.content)
                del response

            return path

    def setArtwork(self, listItem):
        # Set up item and item info
        allartwork = self.artwork.get_all_artwork(self.item, parent_info=True)
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

    def setListItem(self, listItem, dbid=None):

        people = self.API.get_people()
        studios = self.API.get_studios()

        metadata = {
            
            'title': self.item.get('Name', "Missing name"),
            'year': self.item.get('ProductionYear'),
            'plot': self.API.get_overview(),
            'director': people.get('Director'),
            'writer': people.get('Writer'),
            'mpaa': self.API.get_mpaa(),
            'genre': " / ".join(self.item['Genres']),
            'studio': " / ".join(studios),
            'aired': self.API.get_premiere_date(),
            'rating': self.item.get('CommunityRating'),
            'votes': self.item.get('VoteCount')
        }

        if "Episode" in self.item['Type']:
            # Only for tv shows
            # For Kodi Krypton
            metadata['mediatype'] = "episode"
            metadata['dbid'] = dbid

            thumbId = self.item.get('SeriesId')
            season = self.item.get('ParentIndexNumber', -1)
            episode = self.item.get('IndexNumber', -1)
            show = self.item.get('SeriesName', "")

            metadata['TVShowTitle'] = show
            metadata['season'] = season
            metadata['episode'] = episode

        if "Movie" in self.item['Type']:
            # For Kodi Krypton
            metadata['mediatype'] = "movie"
            metadata['dbid'] = dbid

        listItem.setProperty('IsPlayable', 'true')
        listItem.setProperty('IsFolder', 'false')
        listItem.setLabel(metadata['title'])
        listItem.setInfo('video', infoLabels=metadata)