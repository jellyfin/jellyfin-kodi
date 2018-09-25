# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import threading
import sys
from datetime import timedelta

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

import database
from downloader import TheVoid
from obj import Objects
from helper import _, playutils, api, window, settings, dialog, JSONRPC
from dialogs import resume
from emby import Emby
from utils import get_play_action

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Actions(object):

    def __init__(self, server_id=None):

        self.server_id = server_id or None
        self.server = TheVoid('GetServerAddress', {'ServerId': self.server_id}).get()
        self.stack = []

    def get_playlist(self, item):

        if item['Type'] == 'Audio':
            return xbmc.PlayList(xbmc.PLAYLIST_MUSIC)

        return xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def play(self, item, db_id=None, transcode=False, playlist=False):

        ''' Play item based on if playback started from widget ot not.
            To get everything to work together, play the first item in the stack with setResolvedUrl,
            add the rest to the regular playlist.
        '''
        listitem = xbmcgui.ListItem()
        LOG.info("[ play/%s ] %s", item['Id'], item['Name'])

        playlist = self.get_playlist(item)
        play = playutils.PlayUtils(item, transcode, self.server_id, self.server)
        source = play.select_source(play.get_sources())
        play.set_external_subs(source, listitem)

        self.set_playlist(item, listitem, db_id, transcode)
        index = max(playlist.getposition(), 0) + 1 # Can return -1
        force_play = False

        self.stack[0][1].setPath(self.stack[0][0])
        try:
            if not playlist and self.detect_widgets(item):
                LOG.info(" [ play/widget ]")

                raise IndexError

            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, self.stack[0][1])
            self.stack.pop(0)
        except IndexError:
            force_play = True

        for stack in self.stack:

            playlist.add(url=stack[0], listitem=stack[1], index=index)
            index += 1

        if force_play:
            if len(sys.argv) > 1: xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, self.stack[0][1])
            xbmc.Player().play(playlist, windowed=False)

    def set_playlist(self, item, listitem, db_id=None, transcode=False):

        ''' Verify seektime, set intros, set main item and set additional parts.
            Detect the seektime for video type content.
            Verify the default video action set in Kodi for accurate resume behavior.
        '''
        seektime = window('emby.resume.bool')
        window('emby.resume', clear=True)

        if item['MediaType'] in ('Video', 'Audio'):
            resume = item['UserData'].get('PlaybackPositionTicks')

            if resume:
                if get_play_action() == "Resume":
                    seektime = True

                if transcode and not seektime and resume:
                    choice = self.resume_dialog(api.API(item, self.server).adjust_resume((resume or 0) / 10000000.0))
                    
                    if choice is None:
                        return

                    elif not choice:
                        seektime = False

        if settings('enableCinema.bool') and not seektime:
            self._set_intros(item)

        self.set_listitem(item, listitem, db_id, seektime)
        playutils.set_properties(item, item['PlaybackInfo']['Method'], self.server_id)
        self.stack.append([item['PlaybackInfo']['Path'], listitem])

        if item.get('PartCount'):
            self._set_additional_parts(item['Id'])

    def _set_intros(self, item):
        
        ''' if we have any play them when the movie/show is not being resumed.
        '''
        intros = TheVoid('GetIntros', {'ServerId': self.server_id, 'Id': item['Id']}).get()

        if intros['Items']:
            enabled = True

            if settings('askCinema') == "true":

                resp = dialog("yesno", heading="{emby}", line1=_(33016))
                if not resp:

                    enabled = False
                    LOG.info("Skip trailers.")

            if enabled:
                for intro in intros['Items']:

                    listitem = xbmcgui.ListItem()
                    LOG.info("[ intro/%s ] %s", intro['Id'], intro['Name'])

                    play = playutils.PlayUtils(intro, False, self.server_id, self.server)
                    source = play.select_source(play.get_sources())
                    self.set_listitem(intro, listitem, intro=True)
                    listitem.setPath(intro['PlaybackInfo']['Path'])
                    playutils.set_properties(intro, intro['PlaybackInfo']['Method'], self.server_id)

                    self.stack.append([intro['PlaybackInfo']['Path'], listitem])

                window('emby.skip.%s' % intro['Id'], value="true")

    def _set_additional_parts(self, item_id):

        ''' Create listitems and add them to the stack of playlist.
        '''
        parts = TheVoid('GetAdditionalParts', {'ServerId': self.server_id, 'Id': item_id}).get()

        for part in parts['Items']:

            listitem = xbmcgui.ListItem()
            LOG.info("[ part/%s ] %s", part['Id'], part['Name'])

            play = playutils.PlayUtils(part, False, self.server_id, self.server)
            source = play.select_source(play.get_sources())
            play.set_external_subs(source, listitem)
            self.set_listitem(part, listitem)
            listitem.setPath(part['PlaybackInfo']['Path'])
            playutils.set_properties(part, part['PlaybackInfo']['Method'], self.server_id)

            self.stack.append([part['PlaybackInfo']['Path'], listitem])

    def play_playlist(self, items, clear=True, seektime=None, audio=None, subtitle=None):

        ''' Play a list of items. Creates a new playlist. Add additional items as plugin listing.
        '''
        item = items[0]
        playlist = self.get_playlist(item)

        if clear:
            playlist.clear()
            index = 0
        else:
            index = max(playlist.getposition(), 0) + 1 # Can return -1

        listitem = xbmcgui.ListItem()
        LOG.info("[ playlist/%s ] %s", item['Id'], item['Name'])

        play = playutils.PlayUtils(item, False, self.server_id, self.server)
        source = play.select_source(play.get_sources())
        play.set_external_subs(source, listitem)

        item['PlaybackInfo']['AudioStreamIndex'] = audio or item['PlaybackInfo']['AudioStreamIndex']
        item['PlaybackInfo']['SubtitleStreamIndex'] = subtitle or item['PlaybackInfo'].get('SubtitleStreamIndex')

        self.set_listitem(item, listitem, None, True if seektime else False)
        listitem.setPath(item['PlaybackInfo']['Path'])
        playutils.set_properties(item, item['PlaybackInfo']['Method'], self.server_id)

        playlist.add(item['PlaybackInfo']['Path'], listitem, index)
        index += 1

        if clear:
            xbmc.Player().play(playlist)

        for item in items[1:]:
            listitem = xbmcgui.ListItem()
            LOG.info("[ playlist/%s ]", item)
            path = "plugin://plugin.video.emby/?mode=play&id=%s&playlist=true" % item

            listitem.setPath(path)
            playlist.add(path, listitem, index)
            index += 1

    def set_listitem(self, item, listitem, db_id=None, seektime=None, intro=False):

        objects = Objects()
        API = api.API(item, self.server)

        if item['Type'] in ('MusicArtist', 'MusicAlbum', 'Audio'):

            obj = objects.map(item, 'BrowseAudio')
            obj['DbId'] = db_id
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'ArtworkMusic'), True)
            self.listitem_music(obj, listitem, item)

        elif item['Type'] in ('Photo', 'PhotoAlbum'):

            obj = objects.map(item, 'BrowsePhoto')
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'Artwork'))
            self.listitem_photo(obj, listitem, item)

        elif item['Type'] in ('TvChannel'):

            obj = objects.map(item, 'BrowseChannel')
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'Artwork'))
            self.listitem_channel(obj, listitem, item)

        else:
            obj = objects.map(item, 'BrowseVideo')
            obj['DbId'] = db_id
            obj['Artwork'] = API.get_all_artwork(objects.map(item, 'ArtworkParent'), True)

            if intro:
                obj['Artwork']['Primary'] = "&KodiCinemaMode=true"

            self.listitem_video(obj, listitem, item, seektime)

            if 'PlaybackInfo' in item:

                if seektime:
                    item['PlaybackInfo']['CurrentPosition'] = obj['Resume']

                if 'SubtitleUrl' in item['PlaybackInfo']:

                    LOG.info("[ subtitles ] %s", item['PlaybackInfo']['SubtitleUrl'])
                    listitem.setSubtitles([item['PlaybackInfo']['SubtitleUrl']])

        listitem.setContentLookup(False)

    def listitem_video(self, obj, listitem, item, seektime=None):

        ''' Set listitem for video content. That also include streams.
        '''
        API = api.API(item, self.server)
        is_video = obj['MediaType'] in ('Video', 'Audio') # audiobook

        obj['Genres'] = " / ".join(obj['Genres'] or [])
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Studios'] = " / ".join(obj['Studios'])
        obj['Mpaa'] = API.get_mpaa(obj['Mpaa'])
        obj['People'] = obj['People'] or []
        obj['Countries'] = " / ".join(obj['Countries'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['ShortPlot'] = API.get_overview(obj['ShortPlot'])
        obj['DateAdded'] = obj['DateAdded'].split('.')[0].replace('T', " ")
        obj['Rating'] = obj['Rating'] or 0
        obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['DateAdded'].split('T')[0].split('-')))
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Overlay'] = 7 if obj['Played'] else 6
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby/icon.png"
        obj['Artwork']['Thumb'] = obj['Artwork']['Thumb'] or "special://home/addons/plugin.video.emby/fanart.jpg"
        obj['Artwork']['Backdrop'] = obj['Artwork']['Backdrop'] or ["special://home/addons/plugin.video.emby/fanart.jpg"]
        obj['ChildCount'] = obj['ChildCount'] or 0
        obj['RecursiveCount'] = obj['RecursiveCount'] or 0
        obj['Unwatched'] = obj['Unwatched'] or 0

        if obj['Premiere']:
            obj['Premiere'] = obj['Premiere'].split('T')[0]

        if obj['DatePlayed']:
            obj['DatePlayed'] = obj['DatePlayed'].split('.')[0].replace('T', " ")

        metadata = {
            'title': obj['Title'],
            'originaltitle': obj['Title'],
            'sorttitle': obj['SortTitle'],
            'country': obj['Countries'],
            'genre': obj['Genres'],
            'year': obj['Year'],
            'rating': obj['Rating'],
            'playcount': obj['PlayCount'],
            'overlay': obj['Overlay'],
            'director': obj['Directors'],
            'mpaa': obj['Mpaa'],
            'plot': obj['Plot'],
            'plotoutline': obj['ShortPlot'],
            'studio': obj['Studios'],
            'tagline': obj['Tagline'],
            'writer': obj['Writers'],
            'premiered': obj['Premiere'],
            'aired': obj['Premiere'],
            'votes': obj['Votes'],
            'dateadded': obj['DateAdded'],
            'date': obj['FileDate'],
            'dbid': obj['DbId']
        }
        listitem.setCast(API.get_actors())
        listitem.setIconImage(obj['Artwork']['Thumb'])
        listitem.setThumbnailImage(obj['Artwork']['Primary'])
        self.set_artwork(obj['Artwork'], listitem, obj['Type'])

        if obj['Artwork']['Primary']:
            listitem.setThumbnailImage(obj['Artwork']['Primary'])

        if not obj['Artwork']['Backdrop']:
            listitem.setArt({'fanart': obj['Artwork']['Primary']})

        if obj['Premiere']:
            metadata['premieredate'] = obj['Premiere']
            metadata['date'] = obj['Premiere']


        if obj['Type'] == 'Episode':
            metadata.update({
                'mediatype': "episode",
                'tvshowtitle': obj['SeriesName'],
                'season': obj['Season'] or 0,
                'sortseason': obj['Season'] or 0,
                'episode': obj['Index'] or 0,
                'sortepisode': obj['Index'] or 0,
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime']
            })

        elif obj['Type'] == 'Season':
            metadata.update({
                'mediatype': "season",
                'tvshowtitle': obj['SeriesName'],
                'season': obj['Index'] or 0,
                'sortseason': obj['Index'] or 0
            })
            listitem.setProperty('NumEpisodes', str(obj['RecursiveCount']))
            listitem.setProperty('WatchedEpisodes', str(obj['RecursiveCount'] - obj['Unwatched']))
            listitem.setProperty('UnWatchedEpisodes', str(obj['Unwatched']))
            listitem.setProperty('IsFolder', 'true')

        elif obj['Type'] == 'Series':
            metadata.update({
                'mediatype': "tvshow",
                'tvshowtitle': obj['Title']
            })
            listitem.setProperty('TotalSeasons', str(obj['ChildCount']))
            listitem.setProperty('TotalEpisodes', str(obj['RecursiveCount']))
            listitem.setProperty('WatchedEpisodes', str(obj['RecursiveCount'] - obj['Unwatched']))
            listitem.setProperty('UnWatchedEpisodes', str(obj['Unwatched']))
            listitem.setProperty('IsFolder', 'true')

        elif obj['Type'] == 'Movie':
            metadata.update({
                'mediatype': "movie",
                'imdbnumber': obj['UniqueId'],
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime']
            })

        elif obj['Type'] == 'MusicVideo':
            metadata.update({
                'mediatype': "musicvideo",
                'album': obj['Album'],
                'artist': obj['Artists'] or [],
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime']
            })
        
        elif obj['Type'] == 'BoxSet':
            metadata['mediatype'] = "set"
            listitem.setProperty('IsFolder', 'true')
        else:
            metadata.update({
                'mediatype': "video",
                'lastplayed': obj['DatePlayed'],
                'duration': obj['Runtime']
            })


        if is_video:

            listitem.setProperty('totaltime', str(obj['Runtime']))
            listitem.setProperty('IsPlayable', 'true')
            listitem.setProperty('IsFolder', 'false')

            if obj['Resume'] and seektime != False:
                listitem.setProperty('resumetime', str(obj['Resume']))
                listitem.setProperty('StartPercent', str(((obj['Resume']/obj['Runtime']) * 100) - 0.40))
            else:
                listitem.setProperty('resumetime', '0')

            for track in obj['Streams']['video']:
                listitem.addStreamInfo('video', {
                    'duration': obj['Runtime'],
                    'aspect': track['aspect'],
                    'codec': track['codec'],
                    'width': track['width'],
                    'height': track['height']
                })

            for track in obj['Streams']['audio']:
                listitem.addStreamInfo('audio', {'codec': track['codec'], 'channels': track['channels']})

            for track in obj['Streams']['subtitle']:
                listitem.addStreamInfo('subtitle', {'language': track})

        listitem.setLabel(obj['Title'])
        listitem.setInfo('video', metadata)
        listitem.setContentLookup(False)

    def listitem_channel(self, obj, listitem, item):

        ''' Set listitem for channel content.
        '''
        API = api.API(item, self.server)

        obj['Title'] = "%s - %s" % (obj['Title'], obj['ProgramName'])
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Overlay'] = 7 if obj['Played'] else 6
        obj['Artwork']['Primary'] = obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby/icon.png"
        obj['Artwork']['Thumb'] = obj['Artwork']['Thumb'] or "special://home/addons/plugin.video.emby/fanart.jpg"
        obj['Artwork']['Backdrop'] = obj['Artwork']['Backdrop'] or ["special://home/addons/plugin.video.emby/fanart.jpg"]


        metadata = {
            'title': obj['Title'],
            'originaltitle': obj['Title'],
            'playcount': obj['PlayCount'],
            'overlay': obj['Overlay']
        }
        listitem.setIconImage(obj['Artwork']['Thumb'])
        listitem.setThumbnailImage(obj['Artwork']['Primary'])
        self.set_artwork(obj['Artwork'], listitem, obj['Type'])

        if obj['Artwork']['Primary']:
            listitem.setThumbnailImage(obj['Artwork']['Primary'])

        if not obj['Artwork']['Backdrop']:
            listitem.setArt({'fanart': obj['Artwork']['Primary']})

        listitem.setProperty('totaltime', str(obj['Runtime']))
        listitem.setProperty('IsPlayable', 'true')
        listitem.setProperty('IsFolder', 'false')

        listitem.setLabel(obj['Title'])
        listitem.setInfo('video', metadata)
        listitem.setContentLookup(False)

    def listitem_music(self, obj, listitem, item):
        API = api.API(item, self.server)

        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount']) or 0
        obj['Rating'] = obj['Rating'] or 0

        if not obj['Played']:
            obj['DatePlayed'] = None
        elif obj['FileDate'] or obj['DatePlayed']:
            obj['DatePlayed'] = (obj['DatePlayed'] or obj['FileDate']).split('.')[0].replace('T', " ")

        obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['FileDate'].split('T')[0].split('-')))

        metadata = {
            'title': obj['Title'],
            'genre': obj['Genre'],
            'year': obj['Year'],
            'album': obj['Album'],
            'artist': obj['Artists'],
            'rating': obj['Rating'],
            'comment': obj['Comment'],
            'date': obj['FileDate']
        }
        self.set_artwork(obj['Artwork'], listitem, obj['Type'])

        if obj['Type'] == 'Audio':
            metadata.update({
                'mediatype': "song",
                'tracknumber': obj['Index'],
                'discnumber': obj['Disc'],
                'duration': obj['Runtime'],
                'playcount': obj['PlayCount'],
                'lastplayed': obj['DatePlayed'],
                'musicbrainztrackid': obj['UniqueId']
            })
            listitem.setProperty('IsPlayable', 'true')
            listitem.setProperty('IsFolder', 'false')

        elif obj['Type'] == 'Album':
            metadata.update({
                'mediatype': "album",
                'musicbrainzalbumid': obj['UniqueId']
            })

        elif obj['Type'] in ('Artist', 'MusicArtist'):
            metadata.update({
                'mediatype': "artist",
                'musicbrainzartistid': obj['UniqueId']
            })
        else:
            metadata['mediatype'] = "music"

        listitem.setLabel(obj['Title'])
        listitem.setInfo('music', metadata)
        listitem.setContentLookup(False)

    def listitem_photo(self, obj, listitem, item):
        API = api.API(item, self.server)

        obj['Overview'] = API.get_overview(obj['Overview'])
        obj['FileDate'] = "%s.%s.%s" % tuple(reversed(obj['FileDate'].split('T')[0].split('-')))

        metadata = {
            'title': obj['Title']
        }
        listitem.setProperty('path', obj['Artwork']['Primary'])
        listitem.setThumbnailImage(obj['Artwork']['Primary'])
        listitem.setIconImage(obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby/icon.png")
        listitem.setArt({'fanart': obj['Artwork']['Primary'] or "special://home/addons/plugin.video.emby/fanart.jpg"})

        if obj['Type'] == 'Photo':
            metadata.update({
                'picturepath': obj['Artwork']['Primary'],
                'date': obj['FileDate'],
                'exif:width': str(obj.get('Width', 0)),
                'exif:height': str(obj.get('Height', 0)),
                'size': obj['Size'],
                'exif:cameramake': obj['CameraMake'],
                'exif:cameramodel': obj['CameraModel'],
                'exif:exposuretime': str(obj['ExposureTime']),
                'exif:focallength': str(obj['FocalLength'])
            })
            listitem.setProperty('plot', obj['Overview'])
            listitem.setProperty('IsFolder', 'false')
        else:
            if obj['Artwork']['Backdrop']:
                listitem.setArt({'fanart': obj['Artwork']['Backdrop'][0]})

            listitem.setProperty('IsFolder', 'true')

        listitem.setProperty('IsPlayable', 'false')
        listitem.setLabel(obj['Title'])
        listitem.setInfo('pictures', metadata)
        listitem.setContentLookup(False)

    def set_artwork(self, artwork, listitem, media):

        if media == 'Episode':

            art = {
                'poster': "Series.Primary",
                'tvshow.poster': "Series.Primary",
                'clearart': "Art",
                'tvshow.clearart': "Art",
                'clearlogo': "Logo",
                'tvshow.clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'tvshow.landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }
        elif media in ('Artist', 'Audio', 'MusicAlbum'):

            art = {
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart': "Backdrop",
                'fanart_image': "Backdrop", # in case
                'thumb': "Primary"
            }
        else:
            art = {
                'poster': "Primary",
                'clearart': "Art",
                'clearlogo': "Logo",
                'discart': "Disc",
                'fanart_image': "Backdrop",
                'landscape': "Thumb",
                'thumb': "Primary",
                'fanart': "Backdrop"
            }

        for k_art, e_art in art.items():

            if e_art == "Backdrop":
                self._set_art(listitem, k_art, artwork[e_art][0] if artwork[e_art] else " ")
            else:
                self._set_art(listitem, k_art, artwork.get(e_art, " "))

    def _set_art(self, listitem, art, path):
        LOG.debug(" [ art/%s ] %s", art, path)

        if art in ('fanart_image', 'small_poster', 'tiny_poster',
                   'medium_landscape', 'medium_poster', 'small_fanartimage',
                   'medium_fanartimage', 'fanart_noindicators', 'discart',
                   'tvshow.poster'):
            
            listitem.setProperty(art, path)
        else:
            listitem.setArt({art: path})

    def resume_dialog(self, seektime):

        ''' Base resume dialog based on Kodi settings.
        '''
        LOG.info("Resume dialog called.")
        XML_PATH = (xbmcaddon.Addon('plugin.video.emby').getAddonInfo('path'), "default", "1080i")

        dialog = resume.ResumeDialog("script-emby-resume.xml", *XML_PATH)
        dialog.set_resume_point("Resume from %s" % str(timedelta(seconds=seektime)).split(".")[0])
        dialog.doModal()

        if dialog.is_selected():
            if not dialog.get_selected(): # Start from beginning selected.
                return False
        else: # User backed out
            LOG.info("User exited without a selection.")
            return

        return True

    def detect_widgets(self, item):

        kodi_version = xbmc.getInfoLabel('System.BuildVersion')

        if kodi_version and "Git:" in kodi_version and kodi_version.split('Git:')[1].split("-")[0] in ('20171119', 'a9a7a20'):
            LOG.info("Build does not require workaround for widgets?")

            return False

        if (not xbmc.getCondVisibility('Window.IsMedia') and
            ((item['Type'] == 'Audio' and not xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(music),1)')) or
            not xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(video),1)'))):

            return True

        return False


class PlaylistWorker(threading.Thread):

    def __init__(self, server_id, items, *args):

        self.server_id = server_id
        self.items = items
        self.args = args
        threading.Thread.__init__(self)

    def run(self):
        Actions(self.server_id).play_playlist(self.items, *self.args)


def on_update(data, server):
    
    ''' Only for manually marking as watched/unwatched
    '''
    try:
        kodi_id = data['item']['id']
        media = data['item']['type']
        playcount = int(data['playcount'])
        LOG.info(" [ update/%s ] kodi_id: %s media: %s", playcount, kodi_id, media)   
    except (KeyError, TypeError):
        LOG.debug("Invalid playstate update")

        return

    item = database.get_item(kodi_id, media)

    if item:

        if not window('emby.skip.%s.bool' % item[0]):
            server['api'].item_played(item[0], playcount)

        window('emby.skip.%s' % item[0], clear=True)

def on_play(data, server):

    ''' Setup progress for emby playback.
    '''
    player = xbmc.Player()

    try:
        kodi_id = None

        if player.isPlayingVideo():

            ''' Seems to misbehave when playback is not terminated prior to playing new content.
                The kodi id remains that of the previous title. Maybe onPlay happens before
                this information is updated. Added a failsafe further below.
            '''
            item = player.getVideoInfoTag()
            kodi_id = item.getDbId()
            media = item.getMediaType()

        if kodi_id is None or int(kodi_id) == -1 or 'item' in data and 'id' in data['item'] and data['item']['id'] != kodi_id:

            item = data['item']
            kodi_id = item['id']
            media = item['type']

        LOG.info(" [ play ] kodi_id: %s media: %s", kodi_id, media)             

    except (KeyError, TypeError):
        LOG.debug("Invalid playstate update")

        return

    if settings('useDirectPaths') == '1' or media == 'song':
        item = database.get_item(kodi_id, media)

        if item:

            try:
                file = player.getPlayingFile()
            except Exception as error:
                LOG.error(error)

                return

            item = server['api'].get_item(item[0])
            item['PlaybackInfo'] = {'Path': file}
            playutils.set_properties(item, 'DirectStream' if settings('useDirectPaths') == '0' else 'DirectPlay')

def special_listener():

    ''' Corner cases that needs to be listened to.
        This is run in a loop within monitor.py
    '''
    player = xbmc.Player()
    isPlaying = player.isPlaying()
    count = int(window('emby.external_count') or 0)

    if (not isPlaying and xbmc.getCondVisibility('Window.IsVisible(DialogContextMenu.xml)') and
        xbmc.getInfoLabel('Control.GetLabel(1002)') == xbmc.getLocalizedString(12021)):

        control = int(xbmcgui.Window(10106).getFocusId())

        if control == 1002: # Start from beginning

            LOG.info("Resume dialog: Start from beginning selected.")
            window('emby.resume.bool', False)
        else:
            LOG.info("Resume dialog: Resume selected.")
            window('emby.resume.bool', True)

    elif isPlaying and not window('emby.external_check'):
        time = player.getTime()

        if time > 1: # Not external player.

            window('emby.external_check', value="true")
            window('emby.external_count', value="0")
        elif count == 120:

            LOG.info("External player detected.")
            window('emby.external.bool', True)
            window('emby.external_check.bool', True)
            window('emby.external_count', value="0")

        elif time == 0:
            window('emby.external_count', value=str(count + 1))
