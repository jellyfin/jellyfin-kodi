#################################################################################################
# TextureCache
#################################################################################################


import xbmc, xbmcaddon, xbmcvfs
import json
import requests
import urllib
import os

import Utils as utils

class TextureCache():   
       
   
    xbmc_host = 'localhost'
    xbmc_port = None
    xbmc_username = None
    xbmc_password = None
    enableTextureCache = False
    
    def __init__(self):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        self.enableTextureCache = addon.getSetting("enableTextureCache") == "true"
        
        if (not self.xbmc_port and self.enableTextureCache == True):
            self.setKodiWebServerDetails()
            
    def double_urlencode(self, text):
        text = self.single_urlencode(text)
        text = self.single_urlencode(text)
        return text

    def single_urlencode(self, text):
        blah = urllib.urlencode({'blahblahblah':text})
        blah = blah[13:]

        return blah
    
    def FullTextureCacheSync(self):
        #this method can be called from the plugin to sync all Kodi textures to the texture cache.
        #Warning: this means that every image will be cached locally, this takes diskspace!
        
        #remove all existing textures first
        path = "special://thumbnails/"
        if xbmcvfs.exists(path):
            allDirs, allFiles = xbmcvfs.listdir(path)
            for dir in allDirs:
                allDirs, allFiles = xbmcvfs.listdir(path+dir)
                for file in allFiles:
                    xbmcvfs.delete(os.path.join(path+dir,file))
        
        textureconnection = utils.KodiSQL("texture")
        texturecursor = textureconnection.cursor()
        texturecursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
        rows = texturecursor.fetchall()
        for row in rows:
            tableName = row[0]
            if(tableName != "version"):
                texturecursor.execute("DELETE FROM " + tableName)
        textureconnection.commit()
        texturecursor.close()

        
        #cache all entries in video DB
        connection = utils.KodiSQL("video")
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        for url in result:
            self.CacheTexture(url[0])
        cursor.close()    
        
        #cache all entries in music DB
        connection = utils.KodiSQL("music")
        cursor = connection.cursor()
        cursor.execute("SELECT url FROM art")
        result = cursor.fetchall()
        for url in result:
            self.CacheTexture(url[0])
        
        cursor.close()
    
    
    def CacheTexture(self,url):
        #cache a single image url to the texture cache
        if url and self.enableTextureCache == True:
            
            utils.logMsg("cache texture for URL", "Processing : " + url)
            # add image to texture cache by simply calling it at the http endpoint
            url = self.double_urlencode(url)
            try:
                response = requests.head('http://' + self.xbmc_host + ':' + str(self.xbmc_port) + '/image/image://' + url, auth=(self.xbmc_username, self.xbmc_password),timeout=(0.01, 0.01))
            except:
                #extreme short timeouts so we will have a exception, but we don't need the result so pass
                pass
           
      
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