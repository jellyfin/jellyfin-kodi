#################################################################################################
# WriteKodiDB
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import urllib
import sqlite3
import os
from decimal import Decimal

from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ReadKodiDB import ReadKodiDB
from ReadEmbyDB import ReadEmbyDB
from API import API
import Utils as utils

sleepVal = 20

class WriteKodiDB():

    def updatePlayCountFromKodi(self, id, type, playcount=0):
        #when user marks item watched from kodi interface update this in MB3
        xbmc.sleep(sleepVal)
        utils.logMsg("Emby", "updatePlayCountFromKodi Called")
        
        mb3Id = ReadKodiDB().getEmbyIdByKodiId(id, type)

        if(mb3Id != None):
            addon = xbmcaddon.Addon(id='plugin.video.emby')   
            
            downloadUtils = DownloadUtils()       
        
            watchedurl = "{server}/mediabrowser/Users/{UserId}/PlayedItems/%s" % mb3Id
            utils.logMsg("Emby","watchedurl -->" + watchedurl)
            if playcount != 0:
                downloadUtils.downloadUrl(watchedurl, postBody="", type="POST")
            else:
                downloadUtils.downloadUrl(watchedurl, type="DELETE")
        

    def updateMusicVideoToKodiLibrary_Batched(self, MBitem, KodiItem):
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        #downloadUtils = DownloadUtils()
        #userid = downloadUtils.getUserId()
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        params = list()
        
        self.getArtworkParam_Batched(KodiItem, MBitem, params)

        #update common properties
        if KodiItem["runtime"] == None:
            self.getPropertyParam_Batched(KodiItem, "runtime", (int(timeInfo.get('Duration'))*60), params)
        self.getPropertyParam_Batched(KodiItem, "year", MBitem.get("ProductionYear"), params)
        self.getPropertyParamArray_Batched(KodiItem, "director", people.get("Director"), params)
        self.getPropertyParamArray_Batched(KodiItem, "genre", MBitem.get("Genres"), params)
        self.getPropertyParamArray_Batched(KodiItem, "artist", MBitem.get("Artist"), params)
        self.getPropertyParamArray_Batched(KodiItem, "album", MBitem.get("Album"), params)
        self.getPropertyParam_Batched(KodiItem, "lastplayed", userData.get("LastPlayedDate"), params)

        if(studios != None):
            for x in range(0, len(studios)):
                studios[x] = studios[x].replace("/", "&")
            self.getPropertyParamArray_Batched(KodiItem, "studio", studios, params)

        changes = False
        # if there were movies changes then send the update via JSONRPC
        if(len(params) > 0):
            changes |= True
            utils.logMsg("UpdateMovieParams", str(params), level = 2)
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, %s}, "id": 1 }'
            paramString = ""
            paramLen = len(params)
            for x in range(0, paramLen):
                param = params[x]
                paramString += param
                if(x < paramLen-1):
                    paramString += ", "
            jsoncommand = jsoncommand %(KodiItem['musicvideoid'], paramString)
            utils.logMsg("executeJSONRPC : ", jsoncommand, level = 2)
            xbmc.sleep(sleepVal)
            result = xbmc.executeJSONRPC(jsoncommand.encode("utf-8"))
        
        if(changes):
            utils.logMsg("Updated musicvideo to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"], level=0)
                   
                  
    def updateEpisodeToKodiLibrary( self, MBitem, KodiItem, connection, cursor ):       
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        
        timeInfo = API().getTimeInfo(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        userData=API().getUserData(MBitem)
        
        changes = False

        #update/check all artwork
        changes |= self.updateArtWork(KodiItem,MBitem)
        
        addOrUpdateEpisodeToKodiLibrary(MBitem, connection, cursor)

        #add actors
        changes |= self.AddActorsToMedia(KodiItem,MBitem.get("People"),"episode", connection, cursor)
        
        if changes:
            utils.logMsg("Updated item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
    
        return changes
        
    def getArtworkParam_Batched(self, KodiItem, MBitem, params):

        
        item_type=str(MBitem.get("Type"))
        
        '''
        if item_type == "Series":
            id = KodiItem['tvshowid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "art": %s}, "id": 1 }'
        elif item_type == "Episode":
            # episodes don't have any artwork - they derrive this from the tv show
            return False
        elif item_type == "MusicVideo":
            id = KodiItem['musicvideoid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { musicvideoid": %i, "art": %s}, "id": 1 }'
        elif item_type == "Movie":
            id = KodiItem['movieid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "art": %s}, "id": 1 }'
        '''
        
        #update artwork
        changes = False
        
        artwork = {}
        artwork["poster"] = API().getArtwork(MBitem, "Primary")
        
        if(item_type != "Episode"):        
            artwork["banner"] = API().getArtwork(MBitem, "Banner")
            artwork["clearlogo"] = API().getArtwork(MBitem, "Logo")
            artwork["clearart"] = API().getArtwork(MBitem, "Art")
            artwork["landscape"] = API().getArtwork(MBitem, "Thumb")
            artwork["discart"] = API().getArtwork(MBitem, "Disc")
            artwork["fanart"] = API().getArtwork(MBitem, "Backdrop")
        
        for art in artwork:
            if artwork.get(art) != "":
                if KodiItem["art"].has_key(art):
                    curValue = urllib.unquote(KodiItem['art'][art]).decode('utf8')
                    if not artwork.get(art) in curValue:
                        KodiItem["art"][art] = artwork.get(art)
                        changes = True
                else:
                    KodiItem["art"][art] = artwork.get(art)
                    changes = True
        
        if len(KodiItem["art"]) == 0:
            changes = False
        
        if changes:
            json_array = json.dumps(KodiItem["art"])
            params.append("\"art\": " + json_array)
            #result = xbmc.executeJSONRPC(jsoncommand %(id, json_array))
        return changes
        
    # adds or updates artwork to the given Kodi file in database
    def updateArtWork(self,KodiItem,MBitem):
        item_type=str(MBitem.get("Type"))
        
        if item_type == "Series":
            id = KodiItem['tvshowid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "art": %s}, "id": 1 }'
        elif item_type == "Episode":
            id = KodiItem['episodeid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "art": %s}, "id": 1 }'
        elif item_type == "MusicVideo":
            id = KodiItem['musicvideoid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { musicvideoid": %i, "art": %s}, "id": 1 }'
        elif item_type == "Movie":
            id = KodiItem['movieid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "art": %s}, "id": 1 }'

        #update artwork
        changes = False
        
        artwork = {}
        artwork["thumb"] = API().getArtwork(MBitem, "Primary")
        
        if(item_type != "Episode"):
            artwork["poster"] = API().getArtwork(MBitem, "Primary")
            artwork["banner"] = API().getArtwork(MBitem, "Banner")
            artwork["clearlogo"] = API().getArtwork(MBitem, "Logo")
            artwork["clearart"] = API().getArtwork(MBitem, "Art")
            artwork["landscape"] = API().getArtwork(MBitem, "Thumb")
            artwork["discart"] = API().getArtwork(MBitem, "Disc")
            artwork["fanart"] = API().getArtwork(MBitem, "Backdrop")
        
        for art in artwork:
            if artwork.get(art) != "":
                if KodiItem["art"].has_key(art):
                    curValue = urllib.unquote(KodiItem['art'][art]).decode('utf8')
                    if not artwork.get(art) in curValue:
                        KodiItem["art"][art] = artwork.get(art)
                        changes = True
                else:
                    KodiItem["art"][art] = artwork.get(art)
                    changes = True
        
        if len(KodiItem["art"]) == 0:
            changes = False
        
        if changes:
            json_array = json.dumps(KodiItem["art"])
            result = xbmc.executeJSONRPC(jsoncommand %(id, json_array))
        return changes
    
    def getPropertyParam_Batched(self,KodiItem, propertyName, propertyValue, params, forced = False):
    
        '''
        if fileType == "tvshow":
            id = KodiItem['tvshowid']
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": %i}, "id": 1 }'
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": "%s"}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']  
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": %i}, "id": 1 }'            
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": "%s"}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": %i}, "id": 1 }'
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": "%s"}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": %i}, "id": 1 }'
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": "%s"}, "id": 1 }'
        '''
        
        changes = False
        if ((propertyValue != KodiItem[propertyName]) or forced):
            if propertyValue != None:
                if type(propertyValue) is int:
                    #xbmc.sleep(sleepVal)
                    utils.logMsg("Emby","updating property..." + str(propertyName))
                    utils.logMsg("Emby","kodi value:" + str(KodiItem[propertyName]) + " MB value: " + str(propertyValue))
                    params.append("\"" + propertyName + "\": " + str(propertyValue))
                    #xbmc.executeJSONRPC(jsoncommand_i %(id, propertyName, propertyValue))
                    changes = True
                elif type(propertyValue) is Decimal:
                    #extra compare decimals as int (rounded)
                    if int(propertyValue) != int(KodiItem[propertyName]):
                        utils.logMsg("Emby","updating property..." + str(propertyName))
                        utils.logMsg("Emby","kodi value:" + str(KodiItem[propertyName]) + " MB value: " + str(propertyValue))
                        params.append("\"" + propertyName + "\": " + str(propertyValue))
                        changes = True
                else:
                    #xbmc.sleep(sleepVal)
                    propValue = json.dumps(propertyValue)
                    utils.logMsg("Emby","updating property..." + str(propertyName))
                    utils.logMsg("Emby","kodi value:" + KodiItem[propertyName] + " MB value: " + propValue)
                    params.append("\"" + propertyName + "\": " + propValue)
                    #xbmc.executeJSONRPC(jsoncommand_s %(id, propertyName, propertyValue.encode('utf-8')))
                    changes = True
                    
        return changes
        
    # adds or updates the given property on the videofile in Kodi database
    def updateProperty(self,KodiItem,propertyName,propertyValue,fileType,forced=False):
        if fileType == "tvshow":
            id = KodiItem['tvshowid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']  
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": %s}, "id": 1 }'            
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": %s}, "id": 1 }'
        
        changes = False
        if ((propertyValue != KodiItem[propertyName]) or forced):
            if propertyValue != None:
                if type(propertyValue) is int:
                    xbmc.sleep(sleepVal)
                    utils.logMsg("Emby","updating property..." + str(propertyName))
                    utils.logMsg("Emby","kodi value:" + str(KodiItem[propertyName]) + " MB value: " + str(propertyValue))
                    xbmc.executeJSONRPC(jsoncommand %(id, propertyName, propertyValue))
                    changes = True
                elif type(propertyValue) is Decimal:
                    #extra compare decimals as int (rounded)
                    if int(propertyValue) != int(KodiItem[propertyName]):
                        xbmc.sleep(sleepVal)
                        utils.logMsg("Emby","updating property..." + str(propertyName))
                        utils.logMsg("Emby","kodi value:" + str(KodiItem[propertyName]) + " MB value: " + str(propertyValue))
                        xbmc.executeJSONRPC(jsoncommand %(id, propertyName, propertyValue))
                        changes = True
                else:
                    xbmc.sleep(sleepVal)
                    propValue = json.dumps(propertyValue)
                    utils.logMsg("Emby","updating property..." + str(propertyName))
                    utils.logMsg("Emby","kodi value:" + KodiItem[propertyName] + " MB value: " + propValue)
                    xbmc.executeJSONRPC(jsoncommand %(id, propertyName, propValue))
                    changes = True
                    
        return changes

    def getPropertyParamArray_Batched(self, KodiItem, propertyName, propertyCollection, params):
        '''
        if fileType == "tvshow":
            id = KodiItem['tvshowid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": %s}, "id": 1 }'
        '''
        
        pendingChanges = False
        if propertyCollection != None:   
            currentvalues = set(KodiItem[propertyName])
            for item in propertyCollection:
                if not item in currentvalues:
                    pendingChanges = True
                    json_array = json.dumps(propertyCollection)
            
            if pendingChanges:
                #xbmc.sleep(sleepVal)
                utils.logMsg("Emby","updating propertyarray... Name:" + str(propertyName) + " Current:" + str(currentvalues) + " New:" + str(json_array))
                params.append("\"" + propertyName + "\": " + json_array)
                #xbmc.executeJSONRPC(jsoncommand %(id,propertyName,json_array))

        return pendingChanges        
        
    # adds or updates the property-array on the videofile in Kodi database
    def updatePropertyArray(self,KodiItem,propertyName,propertyCollection,fileType):
        if fileType == "tvshow":
            id = KodiItem['tvshowid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": %s}, "id": 1 }'

        pendingChanges = False
        if (propertyCollection != None and KodiItem.get(propertyName) != None):   
            currentvalues = set(KodiItem[propertyName])
            for item in propertyCollection:
                if not item in currentvalues:
                    pendingChanges = True
                    json_array = json.dumps(propertyCollection)
            
            if pendingChanges:
                xbmc.sleep(sleepVal)
                utils.logMsg("Emby","updating propertyarray... Name:" + str(propertyName) + " Current:" + str(currentvalues) + " New:" + str(json_array))
                xbmc.executeJSONRPC(jsoncommand %(id,propertyName,json_array))

        return pendingChanges
    
    def addOrUpdateMovieToKodiLibrary( self, embyId ,connection, cursor, viewTag):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        downloadUtils = DownloadUtils()
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT idMovie FROM movie WHERE embyId = ?",(MBitem["Id"],))
        result = cursor.fetchone()
        if result != None:
            movieid = result[0]
        else:
            movieid = None
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)

        #### The movie details #########
        runtime = int(timeInfo.get('Duration'))*60
        plot = utils.convertEncoding(API().getOverview(MBitem))
        title = utils.convertEncoding(MBitem["Name"])
        sorttitle = utils.convertEncoding(MBitem["SortName"])
        year = MBitem.get("ProductionYear")
        rating = MBitem.get("CommunityRating")

        if MBitem.get("ShortOverview") != None:
            shortplot = utils.convertEncoding(MBitem.get("ShortOverview"))
        else:
            shortplot = None
        
        trailerUrl = None
        if MBitem.get("LocalTrailerCount") != None and MBitem.get("LocalTrailerCount") > 0:
            itemTrailerUrl = "%s/mediabrowser/Users/%s/Items/%s/LocalTrailers?format=json" % (server, userid, MBitem.get("Id"))
            jsonData = downloadUtils.downloadUrl(itemTrailerUrl)
            if(jsonData != ""):
                trailerItem = jsonData
                trailerUrl = "plugin://plugin.video.emby/mode=play?id=" + trailerItem[0][u'Id']
        
        if MBitem.get("DateCreated") != None:
            dateadded = MBitem["DateCreated"].replace("T"," ")
            dateadded = dateadded.replace(".0000000Z","")
        else:
            dateadded = None
        
        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### NOTE THAT LASTPLAYED AND PLAYCOUNT ARE STORED AT THE FILE ENTRY
        path = "plugin://plugin.video.emby/movies/"
        filename = "plugin://plugin.video.emby/movies/?id=" + MBitem["Id"] + "&mode=play"
        
        #create the path
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?",(path,))
        result = cursor.fetchone()
        if result != None:
            pathid = result[0]        
        else:
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0]
            pathid = pathid + 1
            pathsql = "insert into path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (pathid,path,"movies","metadata.local",1))
        
        playcount = None
        if userData.get("PlayCount") == "1":
            playcount = 1
            
        #create the file if not exists
        cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?",(filename,pathid,))
        result = cursor.fetchone()
        if result != None:
            fileid = result[0]
        if result == None:
            cursor.execute("select coalesce(max(idFile),0) as fileid from files")
            fileid = cursor.fetchone()[0]
            fileid = fileid + 1
            pathsql="insert into files(idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (fileid,pathid,filename,playcount,userData.get("LastPlayedDate"),dateadded))

        
        ##### ADD THE MOVIE ############
        if movieid == None:          
            #create the movie
            cursor.execute("select coalesce(max(idMovie),0) as movieid from movie")
            movieid = cursor.fetchone()[0]
            movieid = movieid + 1
            pathsql="insert into movie(idMovie, idFile, c00, c01, c02, c05, c07, c10, c11, c16, c19, embyId) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (movieid, fileid, title, plot, shortplot, rating, year, sorttitle, runtime, title, trailerUrl, MBitem["Id"]))
        
        #### UPDATE THE MOVIE #####
        else:
            pathsql="update movie SET c00 = ?, c01 = ?, c02 = ?, c05 = ?, c07 = ?, c10 = ?, c11 = ?, c16 = ?, c19 = ?, embyId= ? WHERE idMovie = ?"
            cursor.execute(pathsql, (title, plot, shortplot, rating, year, sorttitle, runtime, title, trailerUrl, MBitem["Id"], movieid))
        
        #update or insert actors
        self.AddActorsToMedia(movieid,MBitem.get("People"),"movie", connection, cursor)
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), movieid, "movie", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), movieid, "movie", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), movieid, "movie", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), movieid, "movie", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), movieid, "movie", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), movieid, "movie", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), movieid, "movie", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), movieid, "movie", "fanart", cursor)
        
        #commit changes and return the id
        connection.commit()
        return movieid

    def addMusicVideoToKodiLibrary( self, MBitem, connection, cursor  ):

        #adds a musicvideo to Kodi by directly inserting it to connectionthe DB while there is no addMusicVideo available on the json API
        #TODO: PR at Kodi team for a addMusicVideo endpoint on their API
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        
        playurl = PlayUtils().getPlayUrl(server, MBitem["Id"], MBitem)
        playurl = utils.convertEncoding(playurl)
        
        if MBitem.get("DateCreated") != None:
            dateadded = MBitem["DateCreated"].replace("T"," ")
            dateadded = dateadded.replace(".0000000Z","")
        else:
            dateadded = None

        path = "plugin://plugin.video.emby/musicvideos/"
        filename = "plugin://plugin.video.emby/musicvideos/?mode=play&id=" + MBitem["Id"]
                    
        #create the path
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?",(path,))
        result = cursor.fetchone()
        if result != None:
            pathid = result[0]        
        else:
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0]
            pathid = pathid + 1
            pathsql = "insert into path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (pathid,path,"movies","metadata.local",1))
        
        playcount = None
        if userData.get("PlayCount") == "1":
            playcount = 1
            
        #create the file if not exists
        cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ?",(filename,))
        result = cursor.fetchone()
        if result != None:
            fileid = result[0]
        if result == None:
            cursor.execute("select coalesce(max(idFile),0) as fileid from files")
            fileid = cursor.fetchone()[0]
            fileid = fileid + 1
            pathsql="insert into files(idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (fileid,pathid,filename,playcount,userData.get("LastPlayedDate"),dateadded))
        
        runtime = int(timeInfo.get('Duration'))*60
        plot = utils.convertEncoding(API().getOverview(MBitem))
        title = utils.convertEncoding(MBitem["Name"])
                
        #create the musicvideo
        cursor.execute("select coalesce(max(idMVideo),0) as musicvideoid from musicvideo")
        musicvideoid = cursor.fetchone()[0]
        musicvideoid = musicvideoid + 1
        pathsql="insert into musicvideo(idMVideo, idFile, c00, c04, c08, c23) values(?, ?, ?, ?, ?, ?)"
        cursor.execute(pathsql, (musicvideoid, fileid, title, runtime, plot, MBitem["Id"]))
        
        try:
            connection.commit()
            utils.logMsg("Emby","Added musicvideo to Kodi Library",MBitem["Id"] + " - " + MBitem["Name"])
        except:
            utils.logMsg("Emby","Error adding musicvideo to Kodi Library",MBitem["Id"] + " - " + MBitem["Name"])
            actionPerformed = False
    
    def addOrUpdateEpisodeToKodiLibrary(self, embyId, showid, connection, cursor):
        
        # If the episode already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        cursor.execute("SELECT idEpisode FROM episode WHERE embyId = ?",(MBitem["Id"],))
        result = cursor.fetchone()
        if result != None:
            utils.logMsg("Emby", "Episode already exists in DB : " + MBitem["Id"] + " - " + MBitem["Name"], 2)
            episodeid = result[0]
        else:
            episodeid = None
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)

        ###### episode properties ################
        episode = 0
        if MBitem.get("IndexNumber") != None:
            episode = int(MBitem.get("IndexNumber"))

        runtime = int(timeInfo.get('Duration'))*60
        plot = utils.convertEncoding(API().getOverview(MBitem))
        title = utils.convertEncoding(MBitem["Name"])
        rating = MBitem.get("CommunityRating")
        if MBitem.get("PremiereDate") != None:
            premieredatelist = (MBitem.get("PremiereDate")).split("T")
            premieredate = premieredatelist[0]
        else:
            premieredate = None
        
        if MBitem.get("DateCreated") != None:
            dateadded = MBitem["DateCreated"].replace("T"," ")
            dateadded = dateadded.split(".")[0]
        else:
            dateadded = None
        
        if userData.get("LastPlayedDate") != None:
            lastplayed = userData.get("LastPlayedDate")
        else:
            lastplayed = None
        
        playcount = None
        if userData.get("PlayCount") == "1":
            playcount = 1
        
        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### NOTE THAT LASTPLAYED AND PLAYCOUNT ARE STORED AT THE FILE ENTRY        
        path = "plugin://plugin.video.emby/tvshows/" + MBitem["SeriesId"] + "/"
        filename = "plugin://plugin.video.emby/tvshows/" + MBitem["SeriesId"] + "/?id=" + MBitem["Id"] + "&mode=play"
        
        #create the new path - return id if already exists  
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?",(path,))
        result = cursor.fetchone()
        if result != None:
            pathid = result[0]
        if result == None:
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0]
            pathid = pathid + 1
            pathsql="insert into path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (pathid,path,None,None,1))

        #create the file if not exists
        cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?",(filename,pathid,))
        result = cursor.fetchone()
        if result != None:
            fileid = result[0]
        if result == None:
            cursor.execute("select coalesce(max(idFile),0) as fileid from files")
            fileid = cursor.fetchone()[0]
            fileid = fileid + 1
            sql="INSERT OR REPLACE into files(idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(sql, (fileid,pathid,filename,playcount,lastplayed,dateadded))
        
        # safety check: check season first
        season = 0
        if MBitem.get("ParentIndexNumber") != None:
            season = int(MBitem.get("ParentIndexNumber"))
        else:
            utils.logMsg("Emby","SKIP adding episode to Kodi Library, no ParentIndexNumber - ID: " + MBitem["Id"] + " - " + MBitem["Name"])
            return False
            
        cursor.execute("SELECT idSeason FROM seasons WHERE idShow = ? and season = ?",(showid, season))
        result = cursor.fetchone()        
        if(result == None):
            #update seasons first
            self.updateSeasons(MBitem["SeriesId"], showid, connection, cursor)
                
        # ADD EPISODE TO KODI
        if episodeid == None:
            
            #create the episode
            cursor.execute("select coalesce(max(idEpisode),0) as episodeid from episode")
            episodeid = cursor.fetchone()[0]
            episodeid = episodeid + 1
            pathsql = "INSERT into episode(idEpisode, idFile, c00, c01, c03, c05, c09, c12, c13, c14, idShow, c15, c16, embyId) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (episodeid, fileid, title, plot, rating, premieredate, runtime, season, episode, title, showid, "-1", "-1", MBitem["Id"]))
        
        # UPDATE THE EPISODE IN KODI (for now, we just send in all data)
        else:
            pathsql = "UPDATE episode SET c00 = ?, c01 = ?, c03 = ?, c05 = ?, c09 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, embyId = ? WHERE idEpisode = ?"
            cursor.execute(pathsql, title, plot, rating, premieredate, runtime, season, episode, title, MBitem["Id"], episodeid)
        
        #update or insert actors
        self.AddActorsToMedia(episodeid,MBitem.get("People"),"episode", connection, cursor)
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), episodeid, "episode", "thumb", cursor)
        
        try:
            connection.commit()
            utils.logMsg("Emby","Added or updated episode to Kodi Library - ID: " + MBitem["Id"] + " - " + MBitem["Name"])
        except:
            utils.logMsg("Emby","Error adding/updating episode to Kodi Library - ID: " + MBitem["Id"] + " - " + MBitem["Name"])
            actionPerformed = False
    
    def deleteMovieFromKodiLibrary(self, id, connection, cursor ):
        utils.logMsg("deleting movie from Kodi library --> ",id)
        cursor.execute("DELETE FROM movie WHERE embyId = ?", (id,))
        connection.commit()
 
    def deleteMusicVideoFromKodiLibrary(self, id ):
        utils.logMsg("deleting musicvideo from Kodi library",id)
        kodiItem = ReadKodiDB().getKodiMusicVideo(id)
        if kodiItem != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveMusicVideo", "params": { "musicvideoid": %i}, "id": 1 }' %(kodiItem["musicvideoid"]))
         
    def deleteEpisodeFromKodiLibrary(self, id, connection, cursor ):
        utils.logMsg("deleting episode from Kodi library --> ",id)
        cursor.execute("DELETE FROM episode WHERE embyId = ?", (id,))
        connection.commit()
               
    def addOrUpdateTvShowToKodiLibrary( self, embyId, connection, cursor, viewTag ):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT idMovie FROM movie WHERE embyId = ?",(MBitem["Id"],))
        result = cursor.fetchone()
        if result != None:
            showid = result[0]
        else:
            showid = None
        
        #### TV SHOW DETAILS #########
        
        if MBitem.get("DateCreated") != None:
            dateadded = MBitem["DateCreated"].replace("T"," ")
            dateadded = dateadded.replace(".0000000Z","")
        else:
            dateadded = None
        
        path = "plugin://plugin.video.emby/tvshows/" + MBitem["Id"] + "/"
        
            
        #### ADD THE TV SHOW TO KODI ############## 
        if showid == None:
            #create toplevel path as monitored source - needed for things like actors and stuff to work (no clue why)
            toplevelpath = "plugin://plugin.video.emby/tvshows/"
            cursor.execute("SELECT idPath as tlpathid FROM path WHERE strPath = ?",(toplevelpath,))
            result = cursor.fetchone()
            if result == None:
                cursor.execute("select coalesce(max(idPath),0) as tlpathid from path")
                tlpathid = cursor.fetchone()[0]
                tlpathid = tlpathid + 1
                pathsql="insert into path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
                cursor.execute(pathsql, (tlpathid,toplevelpath,"tvshows","metadata.local",1))
            else:
                tlpathid = result[0]
            
            #create the tv show path
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0]
            pathid = pathid + 1
            pathsql="insert into path(idPath, strPath, strContent, strScraper, noUpdate, idParentPath) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (pathid,path,None,None,1,tlpathid))
            
            runtime = int(timeInfo.get('Duration'))*60
            plot = utils.convertEncoding(API().getOverview(MBitem))
            title = utils.convertEncoding(MBitem["Name"])
            sorttitle = utils.convertEncoding(MBitem["SortName"])
            rating = MBitem.get("CommunityRating")
                
            #create the tvshow
            cursor.execute("select coalesce(max(idShow),0) as showid from tvshow")
            showid = cursor.fetchone()[0]
            showid = pathid + 1
            pathsql="insert into tvshow(idShow, c00, c01, c04, c09, c15, embyId) values(?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (showid, title, plot, rating, title, sorttitle, MBitem["Id"]))
            
            #link the path
            pathsql="insert into tvshowlinkpath(idShow,idPath) values(?, ?)"
            cursor.execute(pathsql, (showid,pathid))
        
        #### UPDATE THE TV SHOW #############
        else:
            pathsql="UPDATE tvshow SET (c00 = ?, c01 = ?, c04 = ?, c09 = ?, c15 = ?, embyId = ? WHERE idShow = ?"
            cursor.execute(pathsql, title, plot, rating, title, sorttitle, MBitem["Id"], showid)
            
        #update or insert actors
        self.AddActorsToMedia(showid,MBitem.get("People"),"tvshow", connection, cursor)
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), showid, "tvshow", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), showid, "tvshow", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), showid, "tvshow", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), showid, "tvshow", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), showid, "tvshow", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), showid, "tvshow", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), showid, "tvshow", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), showid, "tvshow", "fanart", cursor)
        
        #update season details
        self.updateSeasons(MBitem["Id"], showid, connection, cursor)
        
        #commit changes and return the id
        connection.commit()
        return showid
        
    def deleteTVShowFromKodiLibrary(self, id, connection, cursor):
        utils.logMsg("deleting tvshow from Kodi library --> ",id)
        cursor.execute("DELETE FROM tvshow WHERE embyId = ?", (id,))
        connection.commit()
    
    def updateSeasons(self,embyTvShowId, kodiTvShowId, connection, cursor):
        
        seasonData = ReadEmbyDB().getTVShowSeasons(embyTvShowId)
        if seasonData != None:
            for season in seasonData:
                seasonNum = season.get("IndexNumber")
                if seasonNum != None and seasonNum >= 0 and seasonNum <= 1000:
                    cursor.execute("SELECT idSeason as seasonid FROM seasons WHERE idShow = ? and season = ?",(kodiTvShowId, seasonNum))
                    result = cursor.fetchone()
                    if result == None:
                        #create the season
                        cursor.execute("select coalesce(max(idSeason),0) as seasonid from seasons")
                        seasonid = cursor.fetchone()[0]
                        seasonid = seasonid + 1
                        cursor.execute("INSERT into seasons(idSeason, idShow, season) values(?, ?, ?)", (seasonid, kodiTvShowId, seasonNum))
                    else:
                        seasonid = result[0]
                        
                    #update artwork
                    imageUrl = API().getArtwork(season, "Thumb")
                    self.addOrUpdateArt(imageUrl, seasonid, "season", "landscape", cursor)
                    
                    imageUrl = API().getArtwork(season, "Primary")
                    self.addOrUpdateArt(imageUrl, seasonid, "season", "poster", cursor)
                    
                    imageUrl = API().getArtwork(season, "Banner")
                    self.addOrUpdateArt(imageUrl, seasonid, "season", "banner", cursor)                    
                    
        
    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):
        updateDone = False
        if imageUrl:
            cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodiId, mediaType, imageType))
            result = cursor.fetchone()
            if(result == None):
                utils.logMsg("ArtworkSync", "Adding Art Link for kodiId: " + str(kodiId) + " (" + imageUrl + ")")
                cursor.execute("INSERT INTO art(media_id, media_type, type, url) values(?, ?, ?, ?)", (kodiId, mediaType, imageType, imageUrl))
            else:
                url = result[0];
                if(url != imageUrl):
                    utils.logMsg("ArtworkSync", "Updating Art Link for kodiId: " + str(kodiId) + " (" + url + ") -> (" + imageUrl + ")")
                    cursor.execute("UPDATE art set url = ? WHERE media_id = ? AND media_type = ? AND type = ?", (imageUrl, kodiId, mediaType, imageType))

        
    def setKodiResumePoint(self, id, resume_seconds, total_seconds, fileType):
        #use sqlite to set the resume point while json api doesn't support this yet
        #todo --> submit PR to kodi team to get this added to the jsonrpc api
        
        utils.logMsg("Emby","setting resume point in kodi db..." + fileType + ": " + str(id))
        xbmc.sleep(sleepVal)
        connection = utils.KodiSQL()
        cursor = connection.cursor( )
        
        if fileType == "episode":
            cursor.execute("SELECT idFile as fileidid FROM episode WHERE idEpisode = ?",(id,))
            result = cursor.fetchone()
            fileid = result[0]
        if fileType == "movie":
            cursor.execute("SELECT idFile as fileidid FROM movie WHERE idMovie = ?",(id,))
            result = cursor.fetchone()
            fileid = result[0]       
        
        cursor.execute("delete FROM bookmark WHERE idFile = ?", (fileid,))
        cursor.execute("select coalesce(max(idBookmark),0) as bookmarkId from bookmark")
        bookmarkId =  cursor.fetchone()[0]
        bookmarkId = bookmarkId + 1
        bookmarksql="insert into bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, playerState, type) values(?, ?, ?, ?, ?, ?, ?, ?)"
        cursor.execute(bookmarksql, (bookmarkId,fileid,resume_seconds,total_seconds,None,"DVDPlayer",None,1))
        connection.commit()
        cursor.close()
        
    '''
    # removed for now as setting c15 and c16 to -1 looks like it just shows specials in the special folder only 
    def setSpecialAirsDetails(self, MBitem, KodiItem, connection, cursor):
        
        changes = False
        
        cursor.execute("SELECT c15, c16 FROM episode WHERE idEpisode = ?",(KodiItem["episodeid"],))
        result = cursor.fetchone()
        if(result != None):
        
            c15 = -1
            c16 = -1
            
            if(result[0] != None and result[0] != "" and result[0] != "None"):
                c15 = int(result[0])
            if(result[1] != None and result[1] != "" and result[1] != "None"):
                c16 = int(result[1])

            airsBeforeSeasonNumber = MBitem.get("AirsBeforeSeasonNumber")
            airsBeforeEpisodeNumber = MBitem.get("AirsBeforeEpisodeNumber")
            #AirsAfterSeasonNumber
            
            if(airsBeforeSeasonNumber == None):
                airsBeforeSeasonNumber = 0
                
            if(airsBeforeEpisodeNumber == None):
                airsBeforeEpisodeNumber = 0
            
            if(airsBeforeSeasonNumber != None and airsBeforeEpisodeNumber != None):
                if(airsBeforeSeasonNumber != c15 or airsBeforeEpisodeNumber != c16):
                    utils.logMsg("Emby","Special_Airs_Info Kodi: " + str(c15) + " " + str(c16))
                    utils.logMsg("Emby","Special_Airs_Info Emby : " + str(airsBeforeSeasonNumber) + " " + str(airsBeforeEpisodeNumber))
                    sql = "UPDATE episode set c15 = ?, c16 = ? WHERE idEpisode = ?"
                    cursor.execute(sql, (airsBeforeSeasonNumber, airsBeforeEpisodeNumber, KodiItem["episodeid"]))
                    connection.commit()
                    changes = True
                
        return changes
    '''

    def AddActorsToMedia(self, id, people, mediatype, connection, cursor):
        downloadUtils = DownloadUtils()
        
        kodiVersion = 14
        if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
            kodiVersion = 15
        
        if(people != None):
            for person in people:              
                if(person.get("Type") == "Actor"):
                    utils.logMsg("AddActorsToMedia", "Processing : " + person.get("Name"))
                    Name = person.get("Name")
                    Role = person.get("Role")
                    actorid = None
                    Thumb = downloadUtils.imageUrl(person.get("Id"), "Primary", 0, 400, 400)
                    if kodiVersion == 15:
                        # Kodi Isengard database #
                        if Thumb != None:
                            Thumb = "<thumb>" + Thumb + "</thumb>"
                        cursor.execute("SELECT actor_id as actorid FROM actor WHERE name = ?",(Name,))
                    else:
                        # Kodi Gotham or Helix database #
                        cursor.execute("SELECT idActor as actorid FROM actors WHERE strActor = ?",(Name,))
                    result = cursor.fetchone()
                    if result != None:
                        actorid = result[0]
                    if actorid == None:
                        if kodiVersion == 15:
                            # Kodi Isengard database #
                            cursor.execute("select coalesce(max(actor_id),0) as actorid from actor")
                            actorid = cursor.fetchone()[0]
                            actorid = actorid + 1
                            peoplesql="insert into actor(actor_id, name, art_urls) values(?, ?, ?)"
                        else:
                            # Kodi Gotham or Helix database #
                            cursor.execute("select coalesce(max(idActor),0) as actorid from actors")
                            actorid = cursor.fetchone()[0]
                            actorid = actorid + 1
                            peoplesql="insert into actors(idActor, strActor, strThumb) values(?, ?, ?)"
                        cursor.execute(peoplesql, (actorid,Name,Thumb))
                    
                    if kodiVersion == 15:
                        # Kodi Isengard database #
                        peoplesql="INSERT OR REPLACE into actor_link(actor_id, media_id, media_type, role, cast_order) values(?, ?, ?, ?, ?)"
                        cursor.execute(peoplesql, (actorid, id, mediatype, Role, None))
                    else:
                        # Kodi Gotham or Helix database #
                        if mediatype == "movie":
                            peoplesql="INSERT OR REPLACE into actorlinkmovie(idActor, idMovie, strRole, iOrder) values(?, ?, ?, ?)"
                        if mediatype == "tvshow":
                            peoplesql="INSERT OR REPLACE into actorlinktvshow(idActor, idShow, strRole, iOrder) values(?, ?, ?, ?)"
                        if mediatype == "episode":
                            peoplesql="INSERT OR REPLACE into actorlinkepisode(idActor, idEpisode, strRole, iOrder) values(?, ?, ?, ?)"
                        cursor.execute(peoplesql, (actorid,id,Role,None))

 
    def addBoxsetToKodiLibrary(self, boxset, connection, cursor):
        
        strSet = boxset["Name"]
        # check if exists
        cursor.execute("SELECT idSet FROM sets WHERE strSet = ?", (strSet,))
        result = cursor.fetchone()
        setid = None
        if result != None:
            setid = result[0]
            currentsetartsql =  "SELECT type, url FROM art where media_type = ? and media_id = ? and url != ''"
            cursor.execute(currentsetartsql, ("set", setid))
            existing_type_map = {}
            rows = cursor.fetchall()
            for row in rows:
                existing_type_map[row[0] ] = row[1]
          
            artwork = {}
            artwork["poster"] = API().getArtwork(boxset, "Primary")
            artwork["banner"] = API().getArtwork(boxset, "Banner")
            artwork["clearlogo"] = API().getArtwork(boxset, "Logo")
            artwork["clearart"] = API().getArtwork(boxset, "Art")
            artwork["landscape"] = API().getArtwork(boxset, "Thumb")
            artwork["discart"] = API().getArtwork(boxset, "Disc")
            artwork["fanart"] = API().getArtwork(boxset, "Backdrop")
           
            art_types = ['poster','fanart','landscape','clearlogo','clearart','banner','discart']
            for update_type in art_types:
                if ( update_type in existing_type_map ):
                    if ( existing_type_map[update_type] != artwork[update_type] ) and artwork[update_type] != '':
                        setupdateartsql = "UPDATE art SET url = ? where media_type = ? and media_id = ? and type = ?"
                        cursor.execute(setupdateartsql,(artwork[update_type],"set",setid,update_type))
                elif artwork[update_type] != '':
                    setartsql = "INSERT INTO art(media_id, media_type, type, url) VALUES(?,?,?,?)"
                    cursor.execute(setartsql,(setid,"set",update_type,artwork[update_type]))
            
        if setid == None:
            # insert not exists
            setssql="INSERT INTO sets (idSet, strSet)  values(?, ?)"
            cursor.execute(setssql, (None,strSet))
            #if OK:
            result = cursor.fetchone()
            if result != None:
                setid = result[0]
        connection.commit()

        
        return True
    
    def updateBoxsetToKodiLibrary(self, boxsetmovie, boxset):
        strSet = boxset["Name"]
        kodiMovie = ReadKodiDB().getKodiMovie(boxsetmovie["Id"])
        if kodiMovie != None:
            WriteKodiDB().updateProperty(kodiMovie,"set",strSet,"movie",True)
            