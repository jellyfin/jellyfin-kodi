# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import requests
import os
import shutil
import sys
from datetime import timedelta

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

import api
import artwork
import downloadutils
import playutils as putils
import playlist
import read_embyserver as embyserver
import shutil
import embydb_functions as embydb
from database import DatabaseConn
from dialogs import resume
from utils import window, settings, language as lang

#################################################################################################

log = logging.getLogger("EMBY."+__name__)
KODI_V = int(xbmc.getInfoLabel('System.BuildVersion')[:2])

#################################################################################################


class PlaybackUtils(object):


    def __init__(self, item=None, item_id=None):

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()

        self.item = item or self.emby.getItem(item_id)
        self.API = api.API(self.item)

        self.server = window('emby_server%s' % window('emby_currUser'))

        self.stack = []

        if self.item['Type'] == "Audio":
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        else:
            self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

    def _detect_widgets(self):

        kodi_version = xbmc.getInfoLabel('System.BuildVersion')

        if KODI_V == 18:
            return False

        elif kodi_version and "Git:" in kodi_version and kodi_version.split('Git:')[1].split("-")[0] == '20171119':
            #TODO: To be reviewed once Leia is out.
            log.info("Build does not require workaround for widgets?")
            return False
        '''         
        if not xbmc.getCondVisibility('Window.IsMedia'):
            log.info("Not Window.IsMedia")

        if self.item['Type'] == "Audio" and not xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(music),1)'):
            log.info("Audio and not playlist")

        if not xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(video),1)'):
            log.info("Not video playlist")
        '''

        if (not xbmc.getCondVisibility('Window.IsMedia') and
            ((self.item['Type'] == "Audio" and not xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(music),1)')) or
            not xbmc.getCondVisibility('Integer.IsGreater(Playlist.Length(video),1)'))):

            return True

        return False

    def play(self, item_id, dbid=None, force_transcode=False):

        listitem = xbmcgui.ListItem()

        log.info("Play called: %s", self.item['Name'])

        resume = window('emby.resume')
        window('emby.resume', clear=True)

        play_url = putils.PlayUtils(self.item, listitem).get_play_url(force_transcode)

        if not play_url:
            if play_url == False: # User backed-out of menu
                self.playlist.clear()
            return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)

        if force_transcode:
            
            seektime = self.API.get_userdata()['Resume']
            if seektime:
                resume = self.resume_dialog(seektime)
                if resume is None:
                    return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, listitem)
                elif not resume:
                    seektime = 0
        else:
            seektime = self.API.adjust_resume(self.API.get_userdata()['Resume']) if resume == "true" else 0

        if force_transcode:
            log.info("Clear the playlist.")
            self.playlist.clear()

        self.set_playlist(play_url, item_id, listitem, seektime, dbid)

        ##### SETUP PLAYBACK

        ''' To get everything to work together, play the first item in the stack with setResolvedUrl,
            add the rest to the regular playlist.
        '''

        index = max(self.playlist.getposition(), 0) + 1 # Can return -1
        force_play = False

        ''' Krypton 17.6 broke StartOffset. Seems to be working in Leia.
            For now, set up using StartPercent and adjust a bit to compensate.
            TODO: Once Leia is fully supported, move back to StartOffset.
        '''

        if seektime:
            seektime_percent = ((seektime/self.API.get_runtime()) * 100) - 0.40
            log.info("seektime detected (percent): %s", seektime_percent)
            listitem.setProperty('StartPercent', str(seektime_percent))

        # Prevent manually mark as watched in Kodi monitor
        window('emby.skip.%s' % item_id, value="true")

        # Stack: [(url, listitem), (url, ...), ...]
        self.stack[0][1].setPath(self.stack[0][0])
        try:
            if self._detect_widgets():
                # widgets do not fill artwork correctly
                log.info("Detected widget.")
                raise IndexError

            xbmcplugin.setResolvedUrl(int(sys.argv[1]), True, self.stack[0][1])
            self.stack.pop(0) # remove the first item we just started.
        except IndexError:
            log.info("Playback activated via the context menu or widgets.")
            force_play = True

        for stack in self.stack:
            self.playlist.add(url=stack[0], listitem=stack[1], index=index)
            index += 1

        if force_play:
            if len(sys.argv) > 1: xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, self.stack[0][1])
            xbmc.Player().play(self.playlist, windowed=False)


    def set_playlist(self, play_url, item_id, listitem, seektime=None, db_id=None):

        ##### CHECK FOR INTROS

        if settings('enableCinema') == "true" and not seektime:
            self._set_intros(item_id)

        ##### ADD MAIN ITEM

        self.set_properties(play_url, listitem)
        self.set_listitem(listitem, db_id)
        self.stack.append([play_url, listitem])

        ##### ADD ADDITIONAL PARTS

        if self.item.get('PartCount'):
            self._set_additional_parts(item_id)

    def _set_intros(self, item_id):
        # if we have any play them when the movie/show is not being resumed
        intros = self.emby.get_intros(item_id)

        if intros['Items']:
            enabled = True

            if settings('askCinema') == "true":

                resp = xbmcgui.Dialog().yesno("Emby for Kodi", lang(33016))
                if not resp:
                    # User selected to not play trailers
                    enabled = False
                    log.info("Skip trailers.")

            if enabled:
                for intro in intros['Items']:

                    listitem = xbmcgui.ListItem()
                    url = putils.PlayUtils(intro, listitem).get_play_url()
                    log.info("Adding Intro: %s", url)

                    PlaybackUtils(intro).set_properties(url, listitem)
                    self.set_artwork(listitem, self.item['Type'])
                    self.set_listitem(listitem)

                    self.stack.append([url, listitem])

                window('emby.skip.%s' % self.item['Id'], value="true")

    def _set_additional_parts(self, item_id):

        parts = self.emby.get_additional_parts(item_id)

        for part in parts['Items']:

            listitem = xbmcgui.ListItem()
            url = putils.PlayUtils(part, listitem).get_play_url()
            log.info("Adding additional part: %s", url)

            # Set listitem and properties for each additional parts
            pb = PlaybackUtils(part)
            pb.set_properties(url, listitem)

            self.stack.append([url, listitem])

    def set_listitem(self, listitem, dbid=None):

        people = self.API.get_people()
        mediatype = self.item['Type']

        metadata = {
            'title': self.item.get('Name', "Missing name"),
            'year': self.item.get('ProductionYear'),
            'plot': self.API.get_overview(),
            'director': people.get('Director'),
            'writer': people.get('Writer'),
            'mpaa': self.API.get_mpaa(),
            'genre': " / ".join(self.item['Genres']),
            'studio': " / ".join(self.API.get_studios()),
            'aired': self.API.get_premiere_date(),
            'rating': self.item.get('CommunityRating'),
            'votes': self.item.get('VoteCount'),
            'dbid': dbid or None
        }

        if mediatype == "Episode":
            # Only for tv shows
            metadata['mediatype'] = "episode"
            metadata['TVShowTitle'] = self.item.get('SeriesName', "")
            metadata['season'] = self.item.get('ParentIndexNumber', -1)
            metadata['episode'] = self.item.get('IndexNumber', -1)

        elif mediatype == "Movie":
            metadata['mediatype'] = "movie"

        elif mediatype == "MusicVideo":
            metadata['mediatype'] = "musicvideo"

        elif mediatype == "Audio":
            metadata['mediatype'] = "song"

        else:
            metadata['mediatype'] = "video"

        listitem.setProperty('IsPlayable', 'true')
        listitem.setProperty('IsFolder', 'false')
        listitem.setLabel(metadata['title'])
        listitem.setInfo('music' if mediatype == "Audio" else 'video', infoLabels=metadata)

    def set_properties(self, url, listitem):

        # Set all properties necessary for plugin path playback

        item_id = self.item['Id']
        item_type = self.item['Type']

        info = window('emby_%s.play.json' % url)
        window('emby_%s.play.json' % url, clear=True)

        window('emby_%s.json' % url, {

            'url': url,
            'runtime': str(self.item.get('RunTimeTicks')),
            'type': item_type,
            'id': item_id,
            'mediasource_id': info.get('mediasource_id', item_id),
            'refreshid': self.item.get('SeriesId') if item_type == "Episode" else item_id,
            'playmethod': info['playmethod'],
            'playsession_id': info['playsession_id']
        })

        self.set_artwork(listitem, item_type)
        listitem.setCast(self.API.get_actors())

    def set_artwork(self, listitem, item_type):

        all_artwork = self.artwork.get_all_artwork(self.item, parent_info=True)
        # Set artwork for listitem
        if item_type == "Episode":
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
                'thumb': "Primary"
            }

        for k_art, e_art in art.items():

            if e_art == "Backdrop":
                self._set_art(listitem, k_art, all_artwork[e_art][0] if all_artwork[e_art] else " ")
            else:
                self._set_art(listitem, k_art, all_artwork.get(e_art, " "))

    def _set_art(self, listitem, art, path):

        if art in ('fanart_image', 'small_poster', 'tiny_poster',
                   'medium_landscape', 'medium_poster', 'small_fanartimage',
                   'medium_fanartimage', 'fanart_noindicators'):
            
            listitem.setProperty(art, path)
        else:
            listitem.setArt({art: path})

    def resume_dialog(self, seektime):

        log.info("Resume dialog called.")
        XML_PATH = (xbmcaddon.Addon('plugin.video.emby').getAddonInfo('path'), "default", "1080i")

        dialog = resume.ResumeDialog("script-emby-resume.xml", *XML_PATH)
        dialog.set_resume_point("Resume from %s" % str(timedelta(seconds=seektime)).split(".")[0])
        dialog.doModal()

        if dialog.is_selected():
            if not dialog.get_selected(): # Start from beginning selected.
                return False
        else: # User backed out
            log.info("User exited without a selection.")
            return

        return True

    def play_all(self, item_ids, seektime=None, **kwargs):

        self.playlist.clear()
        started = False

        for item_id in item_ids:

            listitem = xbmcgui.ListItem()
            db_id = None

            item = self.emby.getItem(item_id)
            play_url = putils.PlayUtils(item, listitem, **kwargs if item_ids.index(item_id) == 0 else {}).get_play_url()

            if not play_url:
                log.info("Failed to retrieve playurl")
                continue

            log.info("Playurl: %s", play_url)

            with DatabaseConn('emby') as cursor:
                item_db = embydb.Embydb_Functions(cursor).getItem_byId(item_id)
                db_id = item_db[0] if item_db else None

            pbutils = PlaybackUtils(item)

            if item_ids.index(item_id) == 0 and seektime:
                seektime = seektime / 10000000.0 if seektime else None
                log.info("Seektime detected: %s", self.API.adjust_resume(seektime))
                listitem.setProperty('startoffset', str(self.API.adjust_resume(seektime)))
                
            pbutils.set_playlist(play_url, item_id, listitem, seektime if item_ids.index(item_id) == 0 else None, db_id)

            index = max(pbutils.playlist.getposition(), 0) + 1 # Can return -1
            for stack in pbutils.stack:
                pbutils.playlist.add(url=stack[0], listitem=stack[1], index=index)
                index += 1

            if not started:
                started = True

                item = window('emby_%s.json' % play_url)
                item['forcedaudio'] = kwargs.get('AudioStreamIndex')
                item['forcedsubs'] = kwargs.get('SubtitleStreamIndex')
                window('emby_%s.json' % play_url, value=item)

                player = xbmc.Player()
                player.play(pbutils.playlist)

        return True
