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

import image_cache_thread
from utils import window, settings, dialog, language as lang, kodiSQL, JSONRPC

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


    def __init__(self):

        self.enable_texture_cache = settings('enableTextureCache') == "true"
        self.image_cache_limit = int(settings('imageCacheLimit')) * 5
        log.debug("image cache thread count: %s", self.image_cache_limit)

        if not self.xbmc_port and self.enable_texture_cache:
            self._set_webserver_details()

        self.user_id = window('emby_currUser')
        self.server = window('emby_server%s' % self.user_id)


    def _double_urlencode(self, text):

        text = self.single_urlencode(text)
        text = self.single_urlencode(text)

        return text

    @classmethod
    def single_urlencode(cls, text):
        # urlencode needs a utf- string
        text = urllib.urlencode({'blahblahblah': text.encode('utf-8')})
        text = text[13:]

        return text.decode('utf-8') #return the result again as unicode

    def _set_webserver_details(self):
        # Get the Kodi webserver details - used to set the texture cache
        get_setting_value = JSONRPC('Settings.GetSettingValue')

        web_query = {

            "setting": "services.webserver"
        }
        result = get_setting_value.execute(web_query)
        try:
            xbmc_webserver_enabled = result['result']['value']
        except (KeyError, TypeError):
            xbmc_webserver_enabled = False

        if not xbmc_webserver_enabled:
            # Enable the webserver, it is disabled
            set_setting_value = JSONRPC('Settings.SetSettingValue')

            web_port = {

                "setting": "services.webserverport",
                "value": 8080
            }
            set_setting_value.execute(web_port)
            self.xbmc_port = 8080

            web_user = {

                "setting": "services.webserver",
                "value": True
            }
            set_setting_value.execute(web_user)
            self.xbmc_username = "kodi"

        # Webserver already enabled
        web_port = {

            "setting": "services.webserverport"
        }
        result = get_setting_value.execute(web_port)
        try:
            self.xbmc_port = result['result']['value']
        except (TypeError, KeyError):
            pass

        web_user = {

            "setting": "services.webserverusername"
        }
        result = get_setting_value.execute(web_user)
        try:
            self.xbmc_username = result['result']['value']
        except (TypeError, KeyError):
            pass

        web_pass = {

            "setting": "services.webserverpassword"
        }
        result = get_setting_value.execute(web_pass)
        try:
            self.xbmc_password = result['result']['value']
        except (TypeError, KeyError):
            pass

    def texture_cache_sync(self):
        # This method will sync all Kodi artwork to textures13.db
        # and cache them locally. This takes diskspace!
        if not dialog(type_="yesno",
                      heading="{emby}",
                      line1=lang(33042)):
            return

        log.info("Doing Image Cache Sync")

        pdialog = xbmcgui.DialogProgress()
        pdialog.create(lang(29999), lang(33043))

        # ask to rest all existing or not
        if dialog(type_="yesno", heading="{emby}", line1=lang(33044)):
            log.info("Resetting all cache data first")
            self.delete_cache()

        # Cache all entries in video DB
        self._cache_all_video_entries(pdialog)
        # Cache all entries in music DB
        self._cache_all_music_entries(pdialog)

        pdialog.update(100, "%s %s" % (lang(33046), len(self.image_cache_threads)))
        log.info("Waiting for all threads to exit")

        while len(self.image_cache_threads):
            for thread in self.image_cache_threads:
                if thread.is_finished:
                    self.image_cache_threads.remove(thread)
            pdialog.update(100, "%s %s" % (lang(33046), len(self.image_cache_threads)))
            log.info("Waiting for all threads to exit: %s", len(self.image_cache_threads))
            xbmc.sleep(500)

        pdialog.close()

    def _cache_all_video_entries(self, pdialog):

        conn = kodiSQL('video')
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM art WHERE media_type != 'actor'") # dont include actors
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images", total)
        cursor.close()

        count = 0
        for url in result:

            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s (%s)" % (count, total, len(self.image_cache_threads))
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cache_texture(url[0])
            count += 1

    def _cache_all_music_entries(self, pdialog):

        conn = kodiSQL('music')
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images", total)
        cursor.close()

        count = 0
        for url in result:

            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s" % (count, total)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cache_texture(url[0])
            count += 1

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
        conn = kodiSQL('texture')
        cursor = conn.cursor()
        cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
        rows = cursor.fetchall()
        for row in rows:
            table_name = row[0]
            if table_name != "version":
                cursor.execute("DELETE FROM " + table_name)
        conn.commit()
        cursor.close()

    def _add_worker_image_thread(self, url):

        while True:
            # removed finished
            for thread in self.image_cache_threads:
                if thread.is_finished:
                    self.image_cache_threads.remove(thread)

            # add a new thread or wait and retry if we hit our limit
            if len(self.image_cache_threads) < self.image_cache_limit:

                new_thread = image_cache_thread.ImageCacheThread()
                new_thread.set_url(self._double_urlencode(url))
                new_thread.set_host(self.xbmc_host, self.xbmc_port)
                new_thread.set_auth(self.xbmc_username, self.xbmc_password)

                new_thread.start()
                self.image_cache_threads.append(new_thread)
                return
            else:
                log.info("Waiting for empty queue spot: %s", len(self.image_cache_threads))
                xbmc.sleep(50)

    def cache_texture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enable_texture_cache:
            log.debug("Processing: %s", url)

            if not self.image_cache_limit:

                url = self._double_urlencode(url)
                try: # Add image to texture cache by simply calling it at the http endpoint
                    requests.head(url=("http://%s:%s/image/image://%s"
                                       % (self.xbmc_host, self.xbmc_port, url)),
                                  auth=(self.xbmc_username, self.xbmc_password),
                                  timeout=(0.01, 0.01))
                except Exception: # We don't need the result
                    pass
            else:
                self._add_worker_image_thread(url)

    def add_artwork(self, artwork, kodi_id, media_type, cursor):
        # Kodi conversion table
        kodi_artwork = {

            'Primary': ["thumb", "poster"],
            'Banner': "banner",
            'Logo': "clearlogo",
            'Art': "clearart",
            'Thumb': "landscape",
            'Disc': "discart",
            'Backdrop': "fanart",
            'BoxRear': "poster"
        }
        # Artwork is a dictionary
        for artwork_type in artwork:

            if artwork_type == 'Backdrop':
                # Backdrop entry is a list
                # Process extra fanart for artwork downloader (fanart, fanart1, fanart2...)
                backdrops = artwork[artwork_type]
                backdrops_number = len(backdrops)

                query = ' '.join((

                    "SELECT url",
                    "FROM art",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND type LIKE ?"
                ))
                cursor.execute(query, (kodi_id, media_type, "fanart%",))
                rows = cursor.fetchall()

                if len(rows) > backdrops_number:
                    # More backdrops in database. Delete extra fanart.
                    query = ' '.join((

                        "DELETE FROM art",
                        "WHERE media_id = ?",
                        "AND media_type = ?",
                        "AND type LIKE ?"
                    ))
                    cursor.execute(query, (kodi_id, media_type, "fanart_",))

                # Process backdrops and extra fanart
                for index, backdrop in enumerate(backdrops):

                    self.add_update_art(image_url=backdrop,
                                        kodi_id=kodi_id,
                                        media_type=media_type,
                                        image_type=("fanart" if not index else "%s%s"
                                                    % ("fanart", index)),
                                        cursor=cursor)

            elif artwork_type == 'Primary':
                # Primary art is processed as thumb and poster for Kodi.
                for art_type in kodi_artwork[artwork_type]:
                    self.add_update_art(image_url=artwork[artwork_type],
                                        kodi_id=kodi_id,
                                        media_type=media_type,
                                        image_type=art_type,
                                        cursor=cursor)

            elif artwork_type in kodi_artwork:
                # Process the rest artwork type that Kodi can use
                self.add_update_art(image_url=artwork[artwork_type],
                                    kodi_id=kodi_id,
                                    media_type=media_type,
                                    image_type=kodi_artwork[artwork_type],
                                    cursor=cursor)

    def add_update_art(self, image_url, kodi_id, media_type, image_type, cursor):
        # Possible that the imageurl is an empty string
        if image_url:

            cache_image = False

            query = ' '.join((

                "SELECT url",
                "FROM art",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND type = ?"
            ))
            cursor.execute(query, (kodi_id, media_type, image_type,))
            try: # Update the artwork
                url = cursor.fetchone()[0]

            except TypeError: # Add the artwork
                cache_image = True
                log.debug("Adding Art Link for kodiId: %s (%s)", kodi_id, image_url)

                query = (
                    '''
                    INSERT INTO art(media_id, media_type, type, url)

                    VALUES (?, ?, ?, ?)
                    '''
                )
                cursor.execute(query, (kodi_id, media_type, image_type, image_url))

            else: # Only cache artwork if it changed
                if url != image_url:

                    cache_image = True

                    # Only for the main backdrop, poster
                    if (window('emby_initialScan') != "true" and
                            image_type in ("fanart", "poster")):
                        # Delete current entry before updating with the new one
                        self.delete_cached_artwork(url)

                    log.info("Updating Art url for %s kodiId: %s (%s) -> (%s)",
                             image_type, kodi_id, url, image_url)

                    query = ' '.join((

                        "UPDATE art",
                        "SET url = ?",
                        "WHERE media_id = ?",
                        "AND media_type = ?",
                        "AND type = ?"
                    ))
                    cursor.execute(query, (image_url, kodi_id, media_type, image_type))

            # Cache fanart and poster in Kodi texture cache
            if cache_image and image_type in ("fanart", "poster"):
                self.cache_texture(image_url)

    def delete_artwork(self, kodi_id, media_type, cursor):

        query = ' '.join((

            "SELECT url, type",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?"
        ))
        cursor.execute(query, (kodi_id, media_type,))
        rows = cursor.fetchall()
        for row in rows:

            url = row[0]
            image_type = row[1]
            if image_type in ("poster", "fanart"):
                self.delete_cached_artwork(url)

    @classmethod
    def delete_cached_artwork(cls, url):
        # Only necessary to remove and apply a new backdrop or poster
        conn = kodiSQL('texture')
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT cachedurl FROM texture WHERE url = ?", (url,))
            cached_url = cursor.fetchone()[0]

        except TypeError:
            log.info("Could not find cached url")

        except OperationalError:
            log.info("Database is locked. Skip deletion process.")

        else: # Delete thumbnail as well as the entry
            thumbnails = xbmc.translatePath("special://thumbnails/%s" % cached_url).decode('utf-8')
            log.info("Deleting cached thumbnail: %s", thumbnails)
            xbmcvfs.delete(thumbnails)

            try:
                cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
                conn.commit()
            except OperationalError:
                log.debug("Issue deleting url from cache. Skipping.")

        finally:
            cursor.close()

    def get_people_artwork(self, people):
        # append imageurl if existing
        for person in people:

            image = ""
            person_id = person['Id']

            if "PrimaryImageTag" in person:
                image = (
                    "%s/emby/Items/%s/Images/Primary?"
                    "MaxWidth=400&MaxHeight=400&Index=0&Tag=%s"
                    % (self.server, person_id, person['PrimaryImageTag']))

            person['imageurl'] = image

        return people

    def get_user_artwork(self, item_id, item_type):
        # Load user information set by UserClient
        return "%s/emby/Users/%s/Images/%s?Format=original" % (self.server, item_id, item_type)

    def get_all_artwork(self, item, parent_info=False):

        item_id = item['Id']
        artworks = item['ImageTags']
        backdrops = item.get('BackdropImageTags', [])

        max_height = 10000
        max_width = 10000
        custom_query = ""

        if settings('compressArt') == "true":
            custom_query = "&Quality=90"

        if settings('enableCoverArt') == "false":
            custom_query += "&EnableImageEnhancers=false"

        all_artwork = {

            'Primary': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }

        def get_backdrops(item_id, backdrops):

            for index, tag in enumerate(backdrops):
                artwork = ("%s/emby/Items/%s/Images/Backdrop/%s?"
                           "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                           % (self.server, item_id, index, max_width, max_height,
                              tag, custom_query))
                all_artwork['Backdrop'].append(artwork)

        def get_artwork(item_id, type_, tag):

            artwork = ("%s/emby/Items/%s/Images/%s/0?"
                       "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                       % (self.server, item_id, type_, max_width, max_height, tag, custom_query))
            all_artwork[type_] = artwork

        # Process backdrops
        get_backdrops(item_id, backdrops)

        # Process the rest of the artwork
        for artwork in artworks:
            # Filter backcover
            if artwork != "BoxRear":
                get_artwork(item_id, artwork, artworks[artwork])

        # Process parent items if the main item is missing artwork
        if parent_info:
            # Process parent backdrops
            if not all_artwork['Backdrop']:

                if 'ParentBackdropItemId' in item:
                    # If there is a parent_id, go through the parent backdrop list
                    get_backdrops(item['ParentBackdropItemId'], item['ParentBackdropImageTags'])

            # Process the rest of the artwork
            for parent_artwork in ('Logo', 'Art', 'Thumb'):

                if not all_artwork[parent_artwork]:

                    if 'Parent%sItemId' % parent_artwork in item:
                        get_artwork(item['Parent%sItemId' % parent_artwork], parent_artwork,
                                    item['Parent%sImageTag' % parent_artwork])

            # Parent album works a bit differently
            if not all_artwork['Primary']:

                if 'AlbumId' in item and 'AlbumPrimaryImageTag' in item:
                    get_artwork(item['AlbumId'], 'Primary', item['AlbumPrimaryImageTag'])

        return all_artwork
