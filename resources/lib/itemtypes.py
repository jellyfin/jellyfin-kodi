# -*- coding: utf-8 -*-

##################################################################################################

import logging

import read_embyserver as embyserver
from objects import Movies, MusicVideos, TVShows, Music
from utils import settings, kodiSQL

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Items(object):


    def __init__(self, embycursor, kodicursor):

        self.embycursor = embycursor
        self.kodicursor = kodicursor

        self.emby = embyserver.Read_EmbyServer()
        self.music_enabled = settings('enableMusic') == "true"


    def itemsbyId(self, items, process, pdialog=None):
        # Process items by itemid. Process can be added, update, userdata, remove
        embycursor = self.embycursor
        kodicursor = self.kodicursor

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

        #log.info("Processing %s: %s", process, items)
        if pdialog:
            pdialog.update(heading="Processing %s: %s items" % (process, total))

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
                if self.music_enabled:
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
                items_process.add_all(itemtype, itemlist)
            elif process == "remove":
                items_process.remove_all(itemtype, itemlist)
            else:
                process_items = self.emby.getFullItems(itemlist)
                items_process.process_all(itemtype, process, process_items, total)


            if musicconn is not None:
                # close connection for special types
                log.info("updating music database")
                musicconn.commit()
                musiccursor.close()

        return (True, update_videolibrary)
