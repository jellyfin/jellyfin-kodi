# -*- coding: utf-8 -*-

#################################################################################################

import json
import requests
import urllib
import os

import xbmc
import xbmcvfs

import Utils as utils
from ClientInformation import ClientInformation

#################################################################################################

class TextureCache():   
    
    addonName = ClientInformation().getAddonName()   
   
    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None
    enableTextureCache = utils.settings('enableTextureCache') == "true"
    
    def __init__(self):
        
        if not self.xbmc_port and self.enableTextureCache:
            self.setKodiWebServerDetails()

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))
            
    def double_urlencode(self, text):
        text = self.single_urlencode(text)
        text = self.single_urlencode(text)
        
        return text

    def single_urlencode(self, text):
        blah = urllib.urlencode({'blahblahblah':text})
        blah = blah[13:]

        return blah

    def setKodiWebServerDetails(self):
        # Get the Kodi webserver details - used to set the texture cache
        json_response = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.GetSettingValue","params":{"setting":"services.webserver"}, "id":1}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))
        if(jsonobject.has_key('result')): 
            xbmc_webserver_enabled = jsonobject["result"]["value"]
            
        if not xbmc_webserver_enabled:
            #enable the webserver if not enabled
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue","params":{"setting":"services.webserverport","value":8080}, "id":1}')
            self.xbmc_port = 8080
            xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.SetSettingValue","params":{"setting":"services.webserver","value":true}, "id":1}')
            self.xbmc_port = "kodi"

        json_response = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.GetSettingValue","params":{"setting":"services.webserverport"}, "id":1}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))
        if(jsonobject.has_key('result')): 
            self.xbmc_port = jsonobject["result"]["value"]
        
        json_response = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.GetSettingValue","params":{"setting":"services.webserverusername"}, "id":1}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))
        if(jsonobject.has_key('result')): 
            self.xbmc_username = jsonobject["result"]["value"]
        
        json_response = xbmc.executeJSONRPC('{"jsonrpc":"2.0", "id":1, "method":"Settings.GetSettingValue","params":{"setting":"services.webserverpassword"}, "id":1}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))
        if(jsonobject.has_key('result')): 
            self.xbmc_password = jsonobject["result"]["value"]
    
    def FullTextureCacheSync(self):
        #this method can be called from the plugin to sync all Kodi textures to the texture cache.
        #Warning: this means that every image will be cached locally, this takes diskspace!
        
        # Remove all existing textures first
        path = "special://thumbnails/"
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
                # Backdrop entry is a list, process extra fanart for artwork downloader (fanart, fanart1, fanart2, etc.)
                backdrops = artwork[art]
                backdropsNumber = len(backdrops)

                cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type LIKE ?", (kodiId, mediaType, "fanart%",))
                rows = cursor.fetchall()

                if len(rows) > backdropsNumber:
                    # More backdrops in database than what we are going to process. Delete extra fanart.
                    cursor.execute("DELETE FROM art WHERE media_id = ? AND media_type = ? AND type LIKE ?", (kodiId, mediaType, "fanart_",))

                index = ""
                for backdrop in backdrops:
                    self.addOrUpdateArt(backdrop, kodiId, mediaType, "%s%s" % ("fanart", index), cursor)
                    if backdropsNumber > 1:
                        try: # Will only fail on the first try, str to int.
                            index += 1
                        except TypeError:
                            index = 1
                
            elif art == "Primary":
                # Primary art is processed as thumb and poster for Kodi.
                for artType in kodiart[art]:
                    self.addOrUpdateArt(artwork[art], kodiId, mediaType, artType, cursor)
            
            elif kodiart.get(art): # For banner, logo, art, thumb, disc
                # Only process artwork type that Kodi can use
                self.addOrUpdateArt(artwork[art], kodiId, mediaType, kodiart[art], cursor)

    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):
        # Possible that the imageurl is an empty string
        if imageUrl:
            cacheimage = False

            cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodiId, mediaType, imageType,))
            try: # Update the artwork
                url = cursor.fetchone()[0]
            
            except: # Add the artwork
                cacheimage = True
                self.logMsg("Adding Art Link for kodiId: %s (%s)" % (kodiId, imageUrl), 2)
                query = "INSERT INTO art(media_id, media_type, type, url) values(?, ?, ?, ?)"
                cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))
            
            else: # Only cache artwork if it changed
                if url != imageUrl:
                    cacheimage = True
                    
                    # Only for the main backdrop, poster
                    if imageType in ("fanart", "poster"):
                        # Delete current entry before updating with the new one
                        self.deleteCachedArtwork(url)
                    
                    self.logMsg("Updating Art Link for kodiId: %s (%s) -> (%s)" % (kodiId, url, imageUrl), 1)
                    query = "UPDATE art set url = ? WHERE media_id = ? AND media_type = ? AND type = ?"
                    cursor.execute(query, (imageUrl, kodiId, mediaType, imageType))
                    
            # Cache fanart and poster in Kodi texture cache
            if cacheimage and imageType in ("fanart", "poster"):
                self.CacheTexture(imageUrl)

    def CacheTexture(self, url):
        # Cache a single image url to the texture cache
        if url and self.enableTextureCache:
            self.logMsg("Processing: %s" % url, 2)

            # Add image to texture cache by simply calling it at the http endpoint
            url = self.double_urlencode(url)
            try: # Extreme short timeouts so we will have a exception, but we don't need the result so pass
                response = requests.head('http://%s:%s/image/image://%s' % (self.xbmc_host, self.xbmc_port, url), auth=(self.xbmc_username, self.xbmc_password), timeout=(0.01, 0.01))
            except: pass

    def deleteCachedArtwork(self, url):
        # Only necessary to remove and apply a new backdrop or poster
        connection = utils.KodiSQL('texture')
        cursor = connection.cursor()

        cursor.execute("SELECT cachedurl FROM texture WHERE url = ?", (url,))
        try:
            cachedurl = cursor.fetchone()[0]
        
        except:
            self.logMsg("Could not find cached url.", 1)
        
        else: # Delete thumbnail as well as the entry
            thumbnails = xbmc.translatePath("special://thumbnails/%s" % cachedurl)
            self.logMsg("Deleting cached thumbnail: %s" % thumbnails, 1)
            xbmcvfs.delete(thumbnails)
            
            cursor.execute("DELETE FROM texture WHERE url = ?", (url,))
            connection.commit()
        
        finally:
            cursor.close()