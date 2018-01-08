# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcgui

import playutils
import playbackutils
import embydb_functions as embydb
import read_embyserver as embyserver
from utils import window, JSONRPC
from database import DatabaseConn

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Playlist(object):


    def __init__(self):
        self.emby = embyserver.Read_EmbyServer()


    def play_all(self, item_ids, start_at):

        with DatabaseConn('emby') as cursor:
            emby_db = embydb.Embydb_Functions(cursor)

            player = xbmc.Player()
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            playlist.clear()

            log.info("---*** PLAY ALL ***---")
            log.info("Items: %s and start at: %s", item_ids, start_at)

            started = False
            window('emby_customplaylist', value="true")

            if start_at:
                # Seek to the starting position
                window('emby_customplaylist.seektime', str(start_at))

            for item_id in item_ids:

                log.info("Adding %s to playlist", item_id)
                item = emby_db.getItem_byId(item_id)
                try:
                    db_id = item[0]
                    media_type = item[4]

                except TypeError:
                    # Item is not found in our database, add item manually
                    log.info("Item was not found in the database, manually adding item")
                    item = self.emby.getItem(item_id)
                    self.add_to_xbmc_playlist(playlist, item)

                else: # Add to playlist
                    self.add_to_playlist(db_id, media_type)

                if not started:
                    started = True
                    player.play(playlist)

            self.verify_playlist()

    def modify_playlist(self, item_ids):

        with DatabaseConn('emby') as cursor:
            emby_db = embydb.Embydb_Functions(cursor)

            log.info("---*** ADD TO PLAYLIST ***---")
            log.info("Items: %s", item_ids)

            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

            for item_id in item_ids:

                log.info("Adding %s to playlist", item_id)
                item = emby_db.getItem_byId(item_id)
                try:
                    db_id = item[0]
                    media_type = item[4]

                except TypeError:
                    # Item is not found in our database, add item manually
                    item = self.emby.getItem(item_id)
                    self.add_to_xbmc_playlist(playlist, item)

                else: # Add to playlist
                    self.add_to_playlist(db_id, media_type)

            self.verify_playlist()
            
        return playlist

    @classmethod
    def add_to_xbmc_playlist(cls, playlist, item):

        playurl = playutils.PlayUtils(item).getPlayUrl()
        if not playurl:
            log.info("Failed to retrieve playurl")
            return

        log.info("Playurl: %s", playurl)

        listitem = xbmcgui.ListItem()
        playbackutils.PlaybackUtils(item).setProperties(playurl, listitem)
        playlist.add(playurl, listitem)

    @classmethod
    def add_to_playlist(cls, db_id=None, media_type=None, url=None):

        params = {

            'playlistid': 1
        }
        if db_id is not None:
            params['item'] = {'%sid' % media_type: int(db_id)}
        else:
            params['item'] = {'file': url}

        log.debug(JSONRPC('Playlist.Add').execute(params))

    @classmethod
    def insert_to_playlist(cls, position, db_id=None, media_type=None, url=None):

        params = {

            'playlistid': 1,
            'position': position
        }
        if db_id is not None:
            params['item'] = {'%sid' % media_type: int(db_id)}
        else:
            params['item'] = {'file': url}

        log.debug(JSONRPC('Playlist.Insert').execute(params))

    @classmethod
    def verify_playlist(cls):
        log.info(JSONRPC('Playlist.GetItems').execute({'playlistid': 1}))

    @classmethod
    def remove_from_playlist(cls, position):

        params = {

            'playlistid': 1,
            'position': position
        }
        log.debug(JSONRPC('Playlist.Remove').execute(params))




'''
# -*- coding: utf-8 -*-

#################################################################################################

import logging

import xbmc
import xbmcgui

import playutils
import playbackutils
import embydb_functions as embydb
import read_embyserver as embyserver
from utils import window, JSONRPC
from database import DatabaseConn

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Playlist(object):


    def __init__(self):

        self.emby = embyserver.Read_EmbyServer()
        self.playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)


    def play_all(self, item_ids, start_at, **kwargs):

        with DatabaseConn('emby') as cursor:
            emby_db = embydb.Embydb_Functions(cursor)

            player = xbmc.Player()
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
            playlist.clear()

            log.info("---*** PLAY ALL ***---")
            log.info("Items: %s and start at: %s", item_ids, start_at)

            started = False
            window('emby_customplaylist', value="true")

            if start_at:
                # Seek to the starting position
                window('emby_customplaylist.seektime', str(start_at))

            for item_id in item_ids:

                log.info("Adding %s to playlist", item_id)
                item = emby_db.getItem_byId(item_id)
                try:
                    db_id = item[0]
                    media_type = item[4]

                except TypeError:
                    # Item is not found in our database, add item manually
                    log.info("Item was not found in the database, manually adding item")
                    item = self.emby.getItem(item_id)
                    self.add_to_xbmc_playlist(playlist, item, **kwargs)

                else: # Add to playlist
                    #self.add_to_playlist(db_id, media_type)
                    item = self.emby.getItem(item_id)
                    self.add_to_xbmc_playlist(playlist, item, db_id, **kwargs)

                if not started:
                    started = True
                    player.play(playlist)

            self.verify_playlist()

    def modify_playlist(self, item_ids):

        with DatabaseConn('emby') as cursor:
            emby_db = embydb.Embydb_Functions(cursor)

            log.info("---*** ADD TO PLAYLIST ***---")
            log.info("Items: %s", item_ids)

            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

            for item_id in item_ids:

                log.info("Adding %s to playlist", item_id)
                item = emby_db.getItem_byId(item_id)
                try:
                    db_id = item[0]
                    media_type = item[4]

                except TypeError:
                    # Item is not found in our database, add item manually
                    item = self.emby.getItem(item_id)
                    self.add_to_xbmc_playlist(playlist, item)

                else: # Add to playlist
                    self.add_to_playlist(db_id, media_type)

            self.verify_playlist()
            
        return playlist

    @classmethod
    def add_to_xbmc_playlist(cls, playlist, item, db_id, **kwargs):

        listitem = xbmcgui.ListItem()

        play_url = playutils.PlayUtils(item, listitem, **kwargs).get_play_url()
        if not play_url:
            log.info("Failed to retrieve playurl")
            return

        log.info("Playurl: %s", play_url)

        #playbackutils.PlaybackUtils(item).set_playlist(play_url, item['Id'], listitem, seektime=None, db_id):
        #playbackutils.PlaybackUtils(item).set_properties(playurl, listitem)
        #playlist.add(playurl, listitem)

    @classmethod
    def add_to_playlist(cls, db_id, media_type):

        params = {

            'playlistid': 1,
            'item': {
                '%sid' % media_type: int(db_id)
            }
        }
        log.info(JSONRPC('Playlist.Add').execute(params))

    @classmethod
    def insert_to_playlist(cls, position, db_id=None, media_type=None, url=None):

        params = {

            'playlistid': 1,
            'position': position
        }
        if db_id is not None:
            params['item'] = {'%sid' % media_type: int(db_id)}
        else:
            params['item'] = {'file': url}

        log.debug(JSONRPC('Playlist.Insert').execute(params))

    @classmethod
    def verify_playlist(cls):
        log.info(JSONRPC('Playlist.GetItems').execute({'playlistid': 1}))

    @classmethod
    def remove_from_playlist(cls, position):

        params = {

            'playlistid': 1,
            'position': position
        }
        log.debug(JSONRPC('Playlist.Remove').execute(params))
'''