# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import requests
import os
import urllib
from sqlite3 import OperationalError

import xbmc
import xbmcgui
import xbmcvfs

import image_cache_thread
from utils import window, settings, language as lang, kodiSQL

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Artwork():

    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None

    imageCacheThreads = []
    imageCacheLimitThreads = 0


    def __init__(self):

        self.enableTextureCache = settings('enableTextureCache') == "true"
        self.imageCacheLimitThreads = int(settings('imageCacheLimit'))
        self.imageCacheLimitThreads = int(self.imageCacheLimitThreads * 5)
        log.info("Using Image Cache Thread Count: %s" % self.imageCacheLimitThreads)

        if not self.xbmc_port and self.enableTextureCache:
            self.setKodiWebServerDetails()

        self.userId = window('emby_currUser')
        self.server = window('emby_server%s' % self.userId)


    def double_urlencode(self, text):
        text = self.single_urlencode(text)
        text = self.single_urlencode(text)

        return text

    def single_urlencode(self, text):
        # urlencode needs a utf- string
        text = urllib.urlencode({'blahblahblah':text.encode("utf-8")}) 
        text = text[13:]

        return text.decode("utf-8") #return the result again as unicode

    def setKodiWebServerDetails(self):
        # Get the Kodi webserver details - used to set the texture cache
        web_query = {

            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.GetSettingValue",
            "params": {

                "setting": "services.webserver"
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(web_query))
        result = json.loads(result)
        try:
            xbmc_webserver_enabled = result['result']['value']
        except (KeyError, TypeError):
            xbmc_webserver_enabled = False

        if not xbmc_webserver_enabled:
            # Enable the webserver, it is disabled
            web_port = {

                "jsonrpc": "2.0",
                "id": 1,
                "method": "Settings.SetSettingValue",
                "params": {

                    "setting": "services.webserverport",
                    "value": 8080
                }
            }
            result = xbmc.executeJSONRPC(json.dumps(web_port))
            self.xbmc_port = 8080

            web_user = {

                "jsonrpc": "2.0",
                "id": 1,
                "method": "Settings.SetSettingValue",
                "params": {

                    "setting": "services.webserver",
                    "value": True
                }
            }
            result = xbmc.executeJSONRPC(json.dumps(web_user))
            self.xbmc_username = "kodi"


        # Webserver already enabled
        web_port = {

            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.GetSettingValue",
            "params": {

                "setting": "services.webserverport"
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(web_port))
        result = json.loads(result)
        try:
            self.xbmc_port = result['result']['value']
        except (TypeError, KeyError):
            pass

        web_user = {

            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.GetSettingValue",
            "params": {

                "setting": "services.webserverusername"
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(web_user))
        result = json.loads(result)
        try:
            self.xbmc_username = result['result']['value']
        except TypeError:
            pass

        web_pass = {

            "jsonrpc": "2.0",
            "id": 1,
            "method": "Settings.GetSettingValue",
            "params": {

                "setting": "services.webserverpassword"
            }
        }
        result = xbmc.executeJSONRPC(json.dumps(web_pass))
        result = json.loads(result)
        try:
            self.xbmc_password = result['result']['value']
        except TypeError:
            pass

    def fullTextureCacheSync(self):
        # This method will sync all Kodi artwork to textures13.db
        # and cache them locally. This takes diskspace!
        dialog = xbmcgui.Dialog()

        if not dialog.yesno(
                    heading=lang(29999),
                    line1=lang(33042)):
            return

        log.info("Doing Image Cache Sync")

        pdialog = xbmcgui.DialogProgress()
        pdialog.create(lang(29999), lang(33043))

        # ask to rest all existing or not
        if dialog.yesno(lang(29999), lang(33044)):
            log.info("Resetting all cache data first.")
            
            # Remove all existing textures first
            path = xbmc.translatePath('special://thumbnails/').decode('utf-8')
            if xbmcvfs.exists(path):
                allDirs, allFiles = xbmcvfs.listdir(path)
                for dir in allDirs:
                    allDirs, allFiles = xbmcvfs.listdir(path+dir)
                    for file in allFiles:
                        if os.path.supports_unicode_filenames:
                            path = os.path.join(path+dir.decode('utf-8'),file.decode('utf-8'))
                            xbmcvfs.delete(path)
                        else:
                            xbmcvfs.delete(os.path.join(path.encode('utf-8')+dir,file))

            # remove all existing data from texture DB
            connection = kodiSQL('texture')
            cursor = connection.cursor()
            cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
            rows = cursor.fetchall()
            for row in rows:
                tableName = row[0]
                if tableName != "version":
                    cursor.execute("DELETE FROM " + tableName)
            connection.commit()
            cursor.close()

        # Cache all entries in video DB
        connection = kodiSQL('video')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art WHERE media_type != 'actor'") # dont include actors
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images" % total)
        cursor.close()

        count = 0
        for url in result:
            
            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s (%s)" % (count, total, self.imageCacheThreads)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cacheTexture(url[0])
            count += 1
        
        # Cache all entries in music DB
        connection = kodiSQL('music')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        total = len(result)
        log.info("Image cache sync about to process %s images" % total)
        cursor.close()

        count = 0
        for url in result:
            
            if pdialog.iscanceled():
                break

            percentage = int((float(count) / float(total))*100)
            message = "%s of %s" % (count, total)
            pdialog.update(percentage, "%s %s" % (lang(33045), message))
            self.cacheTexture(url[0])
            count += 1
        
        pdialog.update(100, "%s %s" % (lang(33046), len(self.imageCacheThreads)))
        log.info("Waiting for all threads to exit")
        
        while len(self.imageCacheThreads):
            for thread in self.imageCacheThreads:
                if thread.is_finished:
                    self.imageCacheThreads.remove(thread)
            pdialog.update(100, "%s %s" % (lang(33046), len(self.imageCacheThreads)))
            log.info("Waiting for all threads to exit: %s" % len(self.imageCacheThreads))
            xbmc.sleep(500)

        pdialog.close()

    def addWorkerImageCacheThread(self, url):

        while True:
            # removed finished
            for thread in self.imageCacheThreads:
                if thread.is_finished:
                    self.imageCacheThreads.remove(thread)

            # add a new thread or wait and retry if we hit our limit
            if len(self.imageCacheThreads) < self.imageCacheLimitThreads:
                newThread = image_cache_thread.ImageCacheThread()
                newThread.set_url(self.double_urlencode(url))
                newThread.set_host(self.xbmc_host, self.xbmc_port)
                newThread.set_auth(self.xbmc_username, self.xbmc_password)
                newThread.start()
                self.imageCacheThreads.append(newThread)
                return
            else:
                log.info("Waiting for empty queue spot: %s" % len(self.imageCacheThreads))
                xbmc.sleep(50)

    def cacheTexture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enableTextureCache:
            log.debug("Processing: %s" % url)

            if not self.imageCacheLimitThreads:
                # Add image to texture cache by simply calling it at the http endpoint

                url = self.double_urlencode(url)
                try: # Extreme short timeouts so we will have a exception.
                    response = requests.head(
                                        url=("http://%s:%s/image/image://%s"
                                            % (self.xbmc_host, self.xbmc_port, url)),
                                        auth=(self.xbmc_username, self.xbmc_password),
                                        timeout=(0.01, 0.01))
                # We don't need the result
                except: pass

            else:
                self.addWorkerImageCacheThread(url)


    def addArtwork(self, artwork, kodiId, mediaType, cursor):
        # Kodi conversion table
        kodiart = {

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
        for art in artwork:

            if art == "Backdrop":
                # Backdrop entry is a list
                # Process extra fanart for artwork downloader (fanart, fanart1, fanart2...)
                backdrops = artwork[art]
                backdropsNumber = len(backdrops)

                query = ' '.join((

                    "SELECT url",
                    "FROM art",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND type LIKE ?"
                ))
                cursor.execute(query, (kodiId, mediaType, "fanart%",))
                rows = cursor.fetchall()

                if len(rows) > backdropsNumber:
                    # More backdrops in database. Delete extra fanart.
                    query = ' '.join((

                        "DELETE FROM art",
                        "WHERE media_id = ?",
                        "AND media_type = ?",
                        "AND type LIKE ?"
                    ))
                    cursor.execute(query, (kodiId, mediaType, "fanart_",))

                # Process backdrops and extra fanart
                index = ""
                for backdrop in backdrops:
                    self.addOrUpdateArt(
                        imageUrl=backdrop,
                        kodiId=kodiId,
                        mediaType=mediaType,
                        imageType="%s%s" % ("fanart", index),
                        cursor=cursor)

                    if backdropsNumber > 1:
                        try: # Will only fail on the first try, str to int.
                            index += 1
                        except TypeError:
                            index = 1

            elif art == "Primary":
                # Primary art is processed as thumb and poster for Kodi.
                for artType in kodiart[art]:
                    self.addOrUpdateArt(
                        imageUrl=artwork[art],
                        kodiId=kodiId,
                        mediaType=mediaType,
                        imageType=artType,
                        cursor=cursor)

            elif kodiart.get(art):
                # Process the rest artwork type that Kodi can use
                self.addOrUpdateArt(
                    imageUrl=artwork[art],
                    kodiId=kodiId,
                    mediaType=mediaType,
                    imageType=kodiart[art],
                    cursor=cursor)

    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):
        # Possible that the imageurl is an empty string
        if imageUrl:
            cacheimage = False

            query = ' '.join((

                "SELECT url",
                "FROM art",
                "WHERE media_id = ?",
                "AND media_type = ?",
                "AND type = ?"
            ))
            cursor.execute(query, (kodiId, mediaType, imageType,))
            try: # Update the artwork
                url = cursor.fetchone()[0]

            except TypeError: # Add the artwork
                cacheimage = True
                log.debug("Adding Art Link for kodiId: %s (%s)" % (kodiId, imageUrl))

                query = (
                    '''
                    INSERT INTO art(media_id, media_type, type, url)

                    VALUES (?, ?, ?, ?)
                    '''
                )
                cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))

            else: # Only cache artwork if it changed
                if url != imageUrl:
                    cacheimage = True

                    # Only for the main backdrop, poster
                    if (window('emby_initialScan') != "true" and
                            imageType in ("fanart", "poster")):
                        # Delete current entry before updating with the new one
                        self.deleteCachedArtwork(url)

                    log.info("Updating Art url for %s kodiId: %s (%s) -> (%s)"
                        % (imageType, kodiId, url, imageUrl))

                    query = ' '.join((

                        "UPDATE art",
                        "SET url = ?",
                        "WHERE media_id = ?",
                        "AND media_type = ?",
                        "AND type = ?"
                    ))
                    cursor.execute(query, (imageUrl, kodiId, mediaType, imageType))

            # Cache fanart and poster in Kodi texture cache
            if cacheimage and imageType in ("fanart", "poster"):
                self.cacheTexture(imageUrl)

    def deleteArtwork(self, kodiId, mediaType, cursor):

        query = ' '.join((

            "SELECT url, type",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?"
        ))
        cursor.execute(query, (kodiId, mediaType,))
        rows = cursor.fetchall()
        for row in rows:

            url = row[0]
            imageType = row[1]
            if imageType in ("poster", "fanart"):
                self.deleteCachedArtwork(url)

    def deleteCachedArtwork(self, url):
        # Only necessary to remove and apply a new backdrop or poster
        connection = kodiSQL('texture')
        cursor = connection.cursor()

        try:
            cursor.execute("SELECT cachedurl FROM texture WHERE url = ?", (url,))
            cachedurl = cursor.fetchone()[0]

        except TypeError:
            log.info("Could not find cached url.")

        except OperationalError:
            log.info("Database is locked. Skip deletion process.")

        else: # Delete thumbnail as well as the entry
            thumbnails = xbmc.translatePath("special://thumbnails/%s" % cachedurl).decode('utf-8')
            log.info("Deleting cached thumbnail: %s" % thumbnails)
            xbmcvfs.delete(thumbnails)

            try:
                cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
                connection.commit()
            except OperationalError:
                log.debug("Issue deleting url from cache. Skipping.")

        finally:
            cursor.close()

    def getPeopleArtwork(self, people):
        # append imageurl if existing
        for person in people:

            personId = person['Id']
            tag = person.get('PrimaryImageTag')

            image = ""
            if tag:
                image = (
                    "%s/emby/Items/%s/Images/Primary?"
                    "MaxWidth=400&MaxHeight=400&Index=0&Tag=%s"
                    % (self.server, personId, tag))

            person['imageurl'] = image

        return people

    def getUserArtwork(self, itemId, itemType):
        # Load user information set by UserClient
        image = ("%s/emby/Users/%s/Images/%s?Format=original"
                    % (self.server, itemId, itemType))
        return image

    def getAllArtwork(self, item, parentInfo=False):

        itemid = item['Id']
        artworks = item['ImageTags']
        backdrops = item.get('BackdropImageTags', [])

        maxHeight = 10000
        maxWidth = 10000
        customquery = ""

        if settings('compressArt') == "true":
            customquery = "&Quality=90"

        if settings('enableCoverArt') == "false":
            customquery += "&EnableImageEnhancers=false"

        allartworks = {

            'Primary': "",
            'Art': "",
            'Banner': "",
            'Logo': "",
            'Thumb': "",
            'Disc': "",
            'Backdrop': []
        }

        # Process backdrops
        for index, tag in enumerate(backdrops):
            artwork = (
                "%s/emby/Items/%s/Images/Backdrop/%s?"
                "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                % (self.server, itemid, index, maxWidth, maxHeight, tag, customquery))
            allartworks['Backdrop'].append(artwork)

        # Process the rest of the artwork
        for art in artworks:
            # Filter backcover
            if art != "BoxRear":
                tag = artworks[art]
                artwork = (
                    "%s/emby/Items/%s/Images/%s/0?"
                    "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                    % (self.server, itemid, art, maxWidth, maxHeight, tag, customquery))
                allartworks[art] = artwork

        # Process parent items if the main item is missing artwork
        if parentInfo:

            # Process parent backdrops
            if not allartworks['Backdrop']:

                parentId = item.get('ParentBackdropItemId')
                if parentId:
                    # If there is a parentId, go through the parent backdrop list
                    parentbackdrops = item['ParentBackdropImageTags']

                    for index, tag in enumerate(parentbackdrops):
                        artwork = (
                            "%s/emby/Items/%s/Images/Backdrop/%s?"
                            "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                            % (self.server, parentId, index, maxWidth, maxHeight, tag, customquery))
                        allartworks['Backdrop'].append(artwork)

            # Process the rest of the artwork
            parentartwork = ['Logo', 'Art', 'Thumb']
            for parentart in parentartwork:

                if not allartworks[parentart]:

                    parentId = item.get('Parent%sItemId' % parentart)
                    if parentId:

                        parentTag = item['Parent%sImageTag' % parentart]
                        artwork = (
                            "%s/emby/Items/%s/Images/%s/0?"
                            "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                            % (self.server, parentId, parentart,
                                maxWidth, maxHeight, parentTag, customquery))
                        allartworks[parentart] = artwork

            # Parent album works a bit differently
            if not allartworks['Primary']:

                parentId = item.get('AlbumId')
                if parentId and item.get('AlbumPrimaryImageTag'):

                    parentTag = item['AlbumPrimaryImageTag']
                    artwork = (
                        "%s/emby/Items/%s/Images/Primary/0?"
                        "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                        % (self.server, parentId, maxWidth, maxHeight, parentTag, customquery))
                    allartworks['Primary'] = artwork

        return allartworks