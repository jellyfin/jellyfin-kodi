# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging

import xbmc
import xbmcgui
import xbmcplugin

import playutils
import playbackutils
import embydb_functions as embydb
import read_embyserver as embyserver
from utils import window, settings, language as lang, kodiSQL

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Playlist():


    def __init__(self):

        self.userid = window('emby_currUser')
        self.server = window('emby_server%s' % self.userid)

        self.emby = embyserver.Read_EmbyServer()


    def playAll(self, itemids, startat):

        embyconn = kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)

        player = xbmc.Player()
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
        playlist.clear()

        log.info("---*** PLAY ALL ***---")
        log.info("Items: %s and start at: %s" % (itemids, startat))

        started = False
        window('emby_customplaylist', value="true")

        if startat != 0:
            # Seek to the starting position
            window('emby_customplaylist.seektime', str(startat))

        for itemid in itemids:
            embydb_item = emby_db.getItem_byId(itemid)
            try:
                dbid = embydb_item[0]
                mediatype = embydb_item[4]
            except TypeError:
                # Item is not found in our database, add item manually
                log.info("Item was not found in the database, manually adding item.")
                item = self.emby.getItem(itemid)
                self.addtoPlaylist_xbmc(playlist, item)
            else:
                # Add to playlist
                self.addtoPlaylist(dbid, mediatype)

            log.info("Adding %s to playlist." % itemid)

            if not started:
                started = True
                player.play(playlist)

        self.verifyPlaylist()
        embycursor.close()

    def modifyPlaylist(self, itemids):

        embyconn = kodiSQL('emby')
        embycursor = embyconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)

        log.info("---*** ADD TO PLAYLIST ***---")
        log.info("Items: %s" % itemids)

        player = xbmc.Player()
        playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        for itemid in itemids:
            embydb_item = emby_db.getItem_byId(itemid)
            try:
                dbid = embydb_item[0]
                mediatype = embydb_item[4]
            except TypeError:
                # Item is not found in our database, add item manually
                item = self.emby.getItem(itemid)
                self.addtoPlaylist_xbmc(playlist, item)
            else:
                # Add to playlist
                self.addtoPlaylist(dbid, mediatype)

            log.info("Adding %s to playlist." % itemid)

        self.verifyPlaylist()
        embycursor.close()
        return playlist
    
    def addtoPlaylist(self, dbid=None, mediatype=None, url=None):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Add",
            'params': {

                'playlistid': 1
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % mediatype: int(dbid)}
        else:
            pl['params']['item'] = {'file': url}

        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

    def addtoPlaylist_xbmc(self, playlist, item):

        playurl = playutils.PlayUtils(item).getPlayUrl()
        if not playurl:
            # Playurl failed
            log.info("Failed to retrieve playurl.")
            return

        log.info("Playurl: %s" % playurl)
        listitem = xbmcgui.ListItem()
        playbackutils.PlaybackUtils(item).setProperties(playurl, listitem)

        playlist.add(playurl, listitem)

    def insertintoPlaylist(self, position, dbid=None, mediatype=None, url=None):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Insert",
            'params': {

                'playlistid': 1,
                'position': position
            }
        }
        if dbid is not None:
            pl['params']['item'] = {'%sid' % mediatype: int(dbid)}
        else:
            pl['params']['item'] = {'file': url}

        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

    def verifyPlaylist(self):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.GetItems",
            'params': {

                'playlistid': 1
            }
        }
        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))

    def removefromPlaylist(self, position):

        pl = {

            'jsonrpc': "2.0",
            'id': 1,
            'method': "Playlist.Remove",
            'params': {

                'playlistid': 1,
                'position': position
            }
        }
        log.debug(xbmc.executeJSONRPC(json.dumps(pl)))