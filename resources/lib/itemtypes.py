# -*- coding: utf-8 -*-

##################################################################################################

import logging
import urllib
from ntpath import dirname
from datetime import datetime

import xbmc
import xbmcgui
import xbmcvfs

import api
import artwork
import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver
import musicutils
from objects import Movies, MusicVideos, TVShows, Music
from utils import window, settings, language as lang, kodiSQL

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Items(object):


    def __init__(self, embycursor, kodicursor):

        self.embycursor = embycursor
        self.kodicursor = kodicursor

        self.doUtils = downloadutils.DownloadUtils()

        self.kodiversion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        self.directpath = settings('useDirectPaths') == "1"
        self.music_enabled = settings('enableMusic') == "true"
        self.contentmsg = settings('newContent') == "true"
        self.newvideo_time = int(settings('newvideotime'))*1000
        self.newmusic_time = int(settings('newmusictime'))*1000

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.emby_db = embydb.Embydb_Functions(embycursor)
        self.kodi_db = kodidb.Kodidb_Functions(kodicursor)


    def itemsbyId(self, items, process, pdialog=None):
        # Process items by itemid. Process can be added, update, userdata, remove
        emby = self.emby
        embycursor = self.embycursor
        kodicursor = self.kodicursor
        music_enabled = self.music_enabled
        
        itemtypes = {

            'Movie': Movies,
            'BoxSet': Movies,
            'MusicVideo': MusicVideos,
            'Series': TVShows,
            'Season': TVShows,
            'Episode': TVShows,
            'MusicAlbum': Music,
            'MusicArtist': Music,
            'AlbumArtist': Music,
            'Audio': Music
        }

        update_videolibrary = False
        total = 0
        for item in items:
            total += len(items[item])

        if total == 0:
            return False

        log.info("Processing %s: %s" % (process, items))
        if pdialog:
            pdialog.update(heading="Processing %s: %s items" % (process, total))

        count = 0
        for itemtype in items:

            # Safety check
            if not itemtypes.get(itemtype):
                # We don't process this type of item
                continue

            itemlist = items[itemtype]
            if not itemlist:
                # The list to process is empty
                continue

            musicconn = None

            if itemtype in ('MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                if music_enabled:
                    musicconn = kodiSQL('music')
                    musiccursor = musicconn.cursor()
                    items_process = itemtypes[itemtype](embycursor, musiccursor, pdialog)
                else:
                    # Music is not enabled, do not proceed with itemtype
                    continue
            else:
                update_videolibrary = True
                items_process = itemtypes[itemtype](embycursor, kodicursor, pdialog)


            if process == "added":
                processItems = itemlist
                items_process.add_all(itemtype, itemlist)
            elif process == "remove":
                items_process.remove_all(itemtype, itemlist)
            else:
                processItems = emby.getFullItems(itemlist)
                items_process.process_all(itemtype, process, processItems, total)


            if musicconn is not None:
                # close connection for special types
                log.info("Updating music database.")
                musicconn.commit()
                musiccursor.close()

        return (True, update_videolibrary)