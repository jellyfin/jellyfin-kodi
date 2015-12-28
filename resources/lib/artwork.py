# -*- coding: utf-8 -*-

#################################################################################################

import json
import requests
import os
import urllib

import xbmc
import xbmcvfs

import utils
import clientinfo

#################################################################################################


class Artwork():   
    
    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None
    

    def __init__(self):
        
        self.clientinfo = clientinfo.ClientInfo()
        self.addonName = self.clientinfo.getAddonName()

        self.enableTextureCache = utils.settings('enableTextureCache') == "true"
        if not self.xbmc_port and self.enableTextureCache:
            self.setKodiWebServerDetails()

        self.userId = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userId)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)
    

    def double_urlencode(self, text):
        text = self.single_urlencode(text)
        text = self.single_urlencode(text)
        
        return text

    def single_urlencode(self, text):
        text = urllib.urlencode({'blahblahblah':text})
        text = text[13:]

        return text

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
        except TypeError:
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
        except TypeError:
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
    
    def FullTextureCacheSync(self):
        # This method will sync all Kodi artwork to textures13.db
        # and cache them locally. This takes diskspace!

        # Remove all existing textures first
        path = xbmc.translatePath("special://thumbnails/").decode('utf-8')
        if xbmcvfs.exists(path):
            allDirs, allFiles = xbmcvfs.listdir(path)
            for dir in allDirs:
                allDirs, allFiles = xbmcvfs.listdir(path+dir)
                for file in allFiles:
                    xbmcvfs.delete(os.path.join(path+dir,file))
        
        textureconnection = utils.KodiSQL('texture')
        texturecursor = textureconnection.cursor()
        texturecursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
        rows = texturecursor.fetchall()
        for row in rows:
            tableName = row[0]
            if(tableName != "version"):
                texturecursor.execute("DELETE FROM " + tableName)
        textureconnection.commit()
        texturecursor.close()

        
        # Cache all entries in video DB
        connection = utils.KodiSQL('video')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        for url in result:
            self.CacheTexture(url[0])
        cursor.close()    
        
        # Cache all entries in music DB
        connection = utils.KodiSQL('music')
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        for url in result:
            self.CacheTexture(url[0])
        cursor.close()

    def CacheTexture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enableTextureCache:
            self.logMsg("Processing: %s" % url, 2)

            # Add image to texture cache by simply calling it at the http endpoint
            url = self.double_urlencode(url)
            try: # Extreme short timeouts so we will have a exception.
                response = requests.head(
                                    url=(
                                        "http://%s:%s/image/image://%s"
                                        % (self.xbmc_host, self.xbmc_port, url)),
                                    auth=(self.xbmc_username, self.xbmc_password),
                                    timeout=(0.01, 0.01))
            # We don't need the result
            except: pass
    
    
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
                self.logMsg("Adding Art Link for kodiId: %s (%s)" % (kodiId, imageUrl), 2)
                
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
                    if (utils.window('emby_initialScan') != "true" and
                            imageType in ("fanart", "poster")):
                        # Delete current entry before updating with the new one
                        self.deleteCachedArtwork(url)
                    
                    self.logMsg(
                        "Updating Art url for %s kodiId: %s (%s) -> (%s)"
                        % (imageType, kodiId, url, imageUrl), 1)

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
                self.CacheTexture(imageUrl)

    def deleteArtwork(self, kodiid, mediatype, cursor):

        query = ' '.join((

            "SELECT url, type",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = ?"
        ))
        cursor.execute(query, (kodiid, mediatype,))
        rows = cursor.fetchall()
        for row in rows:

            url = row[0]
            imagetype = row[1]
            if imagetype in ("poster", "fanart"):
                self.deleteCachedArtwork(url)

    def deleteCachedArtwork(self, url):
        # Only necessary to remove and apply a new backdrop or poster
        connection = utils.kodiSQL('texture')
        cursor = connection.cursor()

        cursor.execute("SELECT cachedurl FROM texture WHERE url = ?", (url,))
        try:
            cachedurl = cursor.fetchone()[0]
        
        except TypeError:
            self.logMsg("Could not find cached url.", 1)
        
        else: # Delete thumbnail as well as the entry
            thumbnails = xbmc.translatePath("special://thumbnails/%s" % cachedurl).decode('utf-8')
            self.logMsg("Deleting cached thumbnail: %s" % thumbnails, 1)
            xbmcvfs.delete(thumbnails)
            
            try:
                cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
                connection.commit()
            except:
                self.logMsg("Issue deleting url from cache. Skipping.", 2)
        
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

    def getUserArtwork(self, itemid, itemtype):
        # Load user information set by UserClient
        image = ("%s/emby/Users/%s/Images/%s?Format=original"
                    % (self.server, itemid, itemtype))
        return image

    def getAllArtwork(self, item, parentInfo=False):

        server = self.server

        id = item['Id']
        artworks = item['ImageTags']
        backdrops = item['BackdropImageTags']

        maxHeight = 10000
        maxWidth = 10000
        customquery = ""

        if utils.settings('compressArt') == "true":
            customquery = "&Quality=90"

        if utils.settings('enableCoverArt') == "false":
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
        backdropIndex = 0
        for backdroptag in backdrops:
            artwork = (
                "%s/emby/Items/%s/Images/Backdrop/%s?"
                "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                % (server, id, backdropIndex,
                    maxWidth, maxHeight, backdroptag, customquery))
            allartworks['Backdrop'].append(artwork)
            backdropIndex += 1

        # Process the rest of the artwork
        for art in artworks:
            # Filter backcover
            if art != "BoxRear":
                tag = artworks[art]
                artwork = (
                    "%s/emby/Items/%s/Images/%s/0?"
                    "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                    % (server, id, art, maxWidth, maxHeight, tag, customquery))
                allartworks[art] = artwork

        # Process parent items if the main item is missing artwork
        if parentInfo:
            
            # Process parent backdrops
            if not allartworks['Backdrop']:
                
                parentId = item.get('ParentBackdropItemId')
                if parentId:
                    # If there is a parentId, go through the parent backdrop list
                    parentbackdrops = item['ParentBackdropImageTags']

                    backdropIndex = 0
                    for parentbackdroptag in parentbackdrops:
                        artwork = (
                            "%s/emby/Items/%s/Images/Backdrop/%s?"
                            "MaxWidth=%s&MaxHeight=%s&Format=original&Tag=%s%s"
                            % (server, parentId, backdropIndex,
                                maxWidth, maxHeight, parentbackdroptag, customquery))
                        allartworks['Backdrop'].append(artwork)
                        backdropIndex += 1

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
                            % (server, parentId, parentart,
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
                        % (server, parentId, maxWidth, maxHeight, parentTag, customquery))
                    allartworks['Primary'] = artwork

        return allartworks