# -*- coding: utf-8 -*-

#################################################################################################

import logging
import urllib
import Queue
import threading

import xbmc
import xbmcvfs

import queries as QU
import queries_texture as QUTEX
from helper import window, settings
from libraries import requests

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Artwork(object):

    def __init__(self, cursor):

        self.cursor = cursor
        self.enable_cache = settings('enableTextureCache.bool')
        self.queue = Queue.Queue()
        self.threads = []
        self.kodi = {
            'username': settings('webServerUser'),
            'password': settings('webServerPass'),
            'host': "localhost",
            'port': settings('webServerPort')
        }


    def update(self, image_url, kodi_id, media, image):

        ''' Update artwork in the video database.
            Only cache artwork if it changed for the main backdrop, poster.
            Delete current entry before updating with the new one.
            Cache fanart and poster in Kodi texture cache.
        '''
        if not image_url or image == 'poster' and media in ('song', 'artist', 'album'):
            return

        cache = False

        try:
            self.cursor.execute(QU.get_art, (kodi_id, media, image,))
            url = self.cursor.fetchone()[0]
        except TypeError:

            cache = True
            LOG.debug("ADD to kodi_id %s art: %s", kodi_id, image_url)
            self.cursor.execute(QU.add_art, (kodi_id, media, image, image_url))
        else:
            if url != image_url:
                cache = True

                if image in ('fanart', 'poster'):
                    self.delete_cache(url)

                LOG.info("UPDATE to kodi_id %s art: %s", kodi_id, image_url)
                self.cursor.execute(QU.update_art, (image_url, kodi_id, media, image))

        if cache and image in ('fanart', 'poster'):
            self.cache(image_url)

    def add(self, artwork, *args):

        ''' Add all artworks.
        '''
        KODI = {
            'Primary': ['thumb', 'poster'],
            'Banner': "banner",
            'Logo': "clearlogo",
            'Art': "clearart",
            'Thumb': "landscape",
            'Disc': "discart",
            'Backdrop': "fanart"
        }

        for art in KODI:

            if art == 'Backdrop':
                self.cursor.execute(QU.get_backdrops, args + ("fanart%",))

                if len(self.cursor.fetchall()) > len(artwork['Backdrop']):
                    self.cursor.execute(QU.delete_backdrops, args + ("fanart_",))

                for index, backdrop in enumerate(artwork['Backdrop']):

                    if index:
                        self.update(*(backdrop,) + args + ("%s%s" % ("fanart", index),))
                    else:
                        self.update(*(backdrop,) + args + ("fanart",))

            elif art == 'Primary':
                for kodi_image in KODI['Primary']:
                    self.update(*(artwork['Primary'],) + args + (kodi_image,))

            elif artwork.get(art):
                self.update(*(artwork[art],) + args + (KODI[art],))

    def delete(self, *args):

        ''' Delete artwork from kodi database and remove cache for backdrop/posters.
        '''
        self.cursor.execute(QU.get_art_url, args)

        for row in self.cursor.fetchall():
            if row[1] in ('poster', 'fanart'):
                self.delete_cache(row[0])

    def cache(self, url):

        ''' Cache a single image to texture cache.
        '''
        if not url or not self.enable_cache:
            return

        url = self.double_urlencode(url)
        self.queue.put(url)
        self.add_worker()

    def double_urlencode(self, text):

        text = self.single_urlencode(text)
        text = self.single_urlencode(text)

        return text

    def single_urlencode(self, text):
        
        ''' urlencode needs a utf-string.
            return the result as unicode
        '''
        text = urllib.urlencode({'blahblahblah': text.encode('utf-8')})
        text = text[13:]

        return text.decode('utf-8')

    def add_worker(self):

        for thread in self.threads:
            if thread.is_done:
                self.threads.remove(thread)

        if self.queue.qsize() and len(self.threads) < 3:

            new_thread = GetArtworkWorker(self.kodi, self.queue)
            new_thread.start()
            LOG.info("-->[ q:artwork/%s ]", id(new_thread))
            self.threads.append(new_thread)

    def delete_cache(self, url):

        ''' Delete cached artwork.
        '''
        from database import Database

        with Database('texture') as texturedb:

            try:
                texturedb.cursor.execute(QUTEX.get_cache, (url,))
                cached = texturedb.cursor.fetchone()[0]
            except TypeError:
                LOG.debug("Could not find cached url: %s", url)
            else:
                thumbnails = xbmc.translatePath("special://thumbnails/%s" % cached).decode('utf-8')
                xbmcvfs.delete(thumbnails)
                texturedb.cursor.execute(QUTEX.delete_cache, (url,))
                LOG.info("DELETE cached %s", cached)


class GetArtworkWorker(threading.Thread):

    is_done = False

    def __init__(self, kodi, queue):

        self.kodi = kodi
        self.queue = queue
        threading.Thread.__init__(self)

    def run(self):

        ''' Prepare the request. Request removes the urlencode which is required in this case.
            Use a session allows to use a pool of connections.
        '''
        with requests.Session() as s:
            while True:

                try:
                    url = self.queue.get(timeout=2)
                except Queue.Empty:

                    self.is_done = True
                    LOG.info("--<[ q:artwork/%s ]", id(self))

                    return

                try:
                    req = requests.Request(method='HEAD',
                                           url="http://%s:%s/image/image://%s" % (self.kodi['host'], self.kodi['port'], url),
                                           auth=(self.kodi['username'], self.kodi['password']))
                    prep = req.prepare()
                    prep.url = "http://%s:%s/image/image://%s" % (self.kodi['host'], self.kodi['port'], url)
                    s.send(prep, timeout=(0.01, 0.01))
                    s.content # release the connection
                except Exception:
                    pass

                self.queue.task_done()

                if xbmc.Monitor().abortRequested():
                    break




"""

# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import urllib
from sqlite3 import OperationalError

import xbmc
import xbmcgui
import xbmcvfs
import requests

import resources.lib.image_cache_thread as image_cache_thread
from resources.lib.helper import _, window, settings, JSONRPC
from resources.lib.database import Database
from __objs__ import QU

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Artwork(object):

    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None

    image_cache_threads = []
    image_cache_limit = 0


    def __init__(self, server):

        self.server = server
        self.enable_texture_cache = settings('enableTextureCache') == "true"
        self.image_cache_limit = int(settings('imageCacheLimit')) * 5
        log.debug("image cache thread count: %s", self.image_cache_limit)

        if not self.xbmc_port and self.enable_texture_cache:
            self._set_webserver_details()


    def texture_cache_sync(self):
        # This method will sync all Kodi artwork to textures13.db
        # and cache them locally. This takes diskspace!
        if not dialog(type_="yesno",
                      heading="{emby}",
                      line1=_(33042)):
            return

        log.info("Doing Image Cache Sync")

        pdialog = xbmcgui.DialogProgress()
        pdialog.create(_(29999), _(33043))

        # ask to rest all existing or not
        if dialog(type_="yesno", heading="{emby}", line1=_(33044)):
            log.info("Resetting all cache data first")
            self.delete_cache()

        # Cache all entries in video DB
        self._cache_all_video_entries(pdialog)
        # Cache all entries in music DB
        self._cache_all_music_entries(pdialog)

        pdialog.update(100, "%s %s" % (_(33046), len(self.image_cache_threads)))
        log.info("Waiting for all threads to exit")

        while len(self.image_cache_threads):
            for thread in self.image_cache_threads:
                if thread.is_finished:
                    self.image_cache_threads.remove(thread)
            pdialog.update(100, "%s %s" % (_(33046), len(self.image_cache_threads)))
            log.info("Waiting for all threads to exit: %s", len(self.image_cache_threads))
            xbmc.sleep(500)

        pdialog.close()

    @classmethod
    def delete_cache(cls):
        # Remove all existing textures first
        path = xbmc.translatePath('special://thumbnails/').decode('utf-8')
        if xbmcvfs.exists(path):
            dirs, ignore_files = xbmcvfs.listdir(path)
            for directory in dirs:
                ignore_dirs, files = xbmcvfs.listdir(path + directory)
                for file_ in files:

                    if os.path.supports_unicode_filenames:
                        filename = os.path.join(path + directory.decode('utf-8'),
                                                file_.decode('utf-8'))
                    else:
                        filename = os.path.join(path.encode('utf-8') + directory, file_)

                    xbmcvfs.delete(filename)
                    log.debug("deleted: %s", filename)

        # remove all existing data from texture DB
        with DatabaseConn('texture') as cursor_texture:
            cursor_texture.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
            rows = cursor_texture.fetchall()
            for row in rows:
                table_name = row[0]
                if table_name != "version":
                    cursor_texture.execute("DELETE FROM " + table_name)

    def _cache_all_video_entries(self, pdialog):

        with Database('video') as cursor_video:

            cursor_video.execute("SELECT url FROM art WHERE media_type != 'actor'") # dont include actors
            result = cursor_video.fetchall()
            total = len(result)
            log.info("Image cache sync about to process %s images", total)
            cursor_video.close()

            count = 0
            for url in result:

                if pdialog.iscanceled():
                    break

                percentage = int((float(count) / float(total))*100)
                message = "%s of %s (%s)" % (count, total, len(self.image_cache_threads))
                pdialog.update(percentage, "%s %s" % (_(33045), message))
                self.cache_texture(url[0])
                count += 1

    def _cache_all_music_entries(self, pdialog):

        with Database('music') as cursor_music:
        
            cursor_music.execute("SELECT url FROM art")
            result = cursor_music.fetchall()
            total = len(result)
            
            log.info("Image cache sync about to process %s images", total)

            count = 0
            for url in result:

                if pdialog.iscanceled():
                    break

                percentage = int((float(count) / float(total))*100)
                message = "%s of %s" % (count, total)
                pdialog.update(percentage, "%s %s" % (_(33045), message))
                self.cache_texture(url[0])
                count += 1

"""

