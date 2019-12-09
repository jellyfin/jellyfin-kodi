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
from helper import settings
import requests

##################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

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

        if self.queue.qsize() and len(self.threads) < 2:

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
                    s.content  # release the connection
                except Exception as error:
                    LOG.exception(error)

                self.queue.task_done()

                if xbmc.Monitor().abortRequested():
                    break
