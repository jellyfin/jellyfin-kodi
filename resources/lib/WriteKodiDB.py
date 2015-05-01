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
        people = API().getPeople(MBitem)

        #### The movie details #########
        runtime = int(timeInfo.get('Duration'))*60
        plot = utils.convertEncoding(API().getOverview(MBitem))
        title = utils.convertEncoding(MBitem["Name"])
        sorttitle = utils.convertEncoding(MBitem["SortName"])
        year = MBitem.get("ProductionYear")
        rating = MBitem.get("CommunityRating")
        mpaa = MBitem.get("OfficialRating")
        genres = MBitem.get("Genres")
        genre = " / ".join(genres)
        studios = API().getStudios(MBitem)
        studio = " / ".join(studios)
        writer = " / ".join(people.get("Writer"))
        director = " / ".join(people.get("Director"))
        
        imdb = None
        if MBitem.get("ProviderIds"):
            if MBitem.get("ProviderIds").get("Imdb"):
                imdb = MBitem.get("ProviderIds").get("Imdb")

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
                trailerUrl = "plugin://plugin.video.emby/?id=%s&mode=play" % trailerItem[0][u'Id']
        
        if MBitem.get("DateCreated") != None:
            dateadded = MBitem["DateCreated"].replace("T"," ")
            dateadded = dateadded.replace(".0000000Z","")
        else:
            dateadded = None
        
        playcount = None
        if userData.get("PlayCount") == "1":
            playcount = 1
            
        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### NOTE THAT LASTPLAYED AND PLAYCOUNT ARE STORED AT THE FILE ENTRY
        path = "plugin://plugin.video.emby/"
        filename = "plugin://plugin.video.emby/?id=%s&mode=play" % MBitem["Id"]
        
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
            pathsql="insert into movie(idMovie, idFile, c00, c01, c02, c05, c06, c07, c09, c10, c11, c12, c14, c15, c16, c18, c19, embyId) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (movieid, fileid, title, plot, shortplot, rating, writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio, trailerUrl, MBitem["Id"]))
            
            #add the viewtag
            self.AddTagToMedia(movieid, viewTag, "movie", cursor)
            
        #### UPDATE THE MOVIE #####
        else:
            pathsql="update movie SET c00 = ?, c01 = ?, c02 = ?, c05 = ?, c06 = ?, c07 = ?, c09 = ? c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?, c16 = ?, c18 = ?, c19 = ?, embyId= ? WHERE idMovie = ?"
            cursor.execute(pathsql, (title, plot, shortplot, rating, writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio, trailerUrl, MBitem["Id"], movieid))
        
        #update or insert actors
        self.AddPeopleToMedia(movieid,MBitem.get("People"),"movie", connection, cursor)
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), movieid, "movie", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), movieid, "movie", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), movieid, "movie", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), movieid, "movie", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), movieid, "movie", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), movieid, "movie", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), movieid, "movie", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), movieid, "movie", "fanart", cursor)
        
        #update genres
        self.AddGenresToMedia(movieid, genres, "movie", cursor)
        
        #update studios
        self.AddStudiosToMedia(movieid, studios, "movie", cursor)
        
        #commit changes and return the id
        connection.commit()
        return movieid

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
        
        genres = MBitem.get("Genres")
        genre = " / ".join(genres)
        studios = API().getStudios(MBitem)
        studio = " / ".join(studios)
        mpaa = MBitem.get("OfficialRating")
        
        if MBitem.get("DateCreated") != None:
            dateadded = MBitem["DateCreated"].replace("T"," ")
            dateadded = dateadded.replace(".0000000Z","")
        else:
            dateadded = None
        
        if MBitem.get("PremiereDate") != None: 
             premieredatelist = (MBitem.get("PremiereDate")).split("T") 
             premieredate = premieredatelist[0] 
        else:
            premieredate = None
        
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
            pathsql="insert into tvshow(idShow, c00, c01, c04, c05, c08, c09, c13, c14, c15, embyId) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (showid, title, plot, rating, premieredate, genre, title, mpaa, studio, sorttitle, MBitem["Id"]))
            
            #link the path
            pathsql="insert into tvshowlinkpath(idShow,idPath) values(?, ?)"
            cursor.execute(pathsql, (showid,pathid))
            
            #add the viewtag
            self.AddTagToMedia(showid, viewTag, "tvshow", cursor)
        
        #### UPDATE THE TV SHOW #############
        else:
            pathsql="UPDATE tvshow SET (c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?, c13 = ?, c14 = ?, c15 = ?, embyId = ? WHERE idShow = ?"
            cursor.execute(pathsql, title, plot, rating, premieredate, title, genre, mpaa, studio, sorttitle, MBitem["Id"], showid)
            
        #update or insert people
        self.AddPeopleToMedia(showid,MBitem.get("People"),"tvshow", connection, cursor)
        
        #update genres
        self.AddGenresToMedia(showid, genres, "tvshow", cursor)
        
        #update studios
        self.AddStudiosToMedia(showid, studios, "tvshow", cursor)
        
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
        people = API().getPeople(MBitem)

        ###### episode properties ################
        episode = 0
        if MBitem.get("IndexNumber") != None:
            episode = int(MBitem.get("IndexNumber"))

        runtime = int(timeInfo.get('Duration'))*60
        plot = utils.convertEncoding(API().getOverview(MBitem))
        title = utils.convertEncoding(MBitem["Name"])
        rating = MBitem.get("CommunityRating")
        writer = " / ".join(people.get("Writer"))
        director = " / ".join(people.get("Director"))
        
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
            pathsql = "INSERT into episode(idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14, idShow, c15, c16, embyId) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (episodeid, fileid, title, plot, rating, writer, premieredate, runtime, director, season, episode, title, showid, "-1", "-1", MBitem["Id"]))
        
        # UPDATE THE EPISODE IN KODI (for now, we just send in all data)
        else:
            pathsql = "UPDATE episode SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, embyId = ? WHERE idEpisode = ?"
            cursor.execute(pathsql, title, plot, rating, writer, premieredate, runtime, director, season, episode, title, MBitem["Id"], episodeid)
        
        #update or insert actors
        self.AddPeopleToMedia(episodeid,MBitem.get("People"),"episode", connection, cursor)
        
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
        
    def AddPeopleToMedia(self, id, people, mediatype, connection, cursor):
        downloadUtils = DownloadUtils()
        
        kodiVersion = 14
        if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
            kodiVersion = 15
        
        if(people != None):
            for person in people:              
                
                Name = person.get("Name")
                
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
                    utils.logMsg("AddPeopleToMedia", "Processing : " + person.get("Name"))
                    cursor.execute(peoplesql, (actorid,Name,Thumb))
                
                #### ACTORS ######
                if(person.get("Type") == "Actor"):
                    
                    Role = person.get("Role")
                    if kodiVersion == 15:
                        # Kodi Isengard database #
                        peoplesql="INSERT OR REPLACE into actor_link(actor_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(peoplesql, (actorid, id, mediatype))
                    else:
                        # Kodi Gotham or Helix database #
                        if mediatype == "movie":
                            peoplesql="INSERT OR REPLACE into actorlinkmovie(idActor, idMovie, strRole, iOrder) values(?, ?, ?, ?)"
                            cursor.execute(peoplesql, (actorid,id,Role,None))
                        if mediatype == "tvshow":
                            peoplesql="INSERT OR REPLACE into actorlinktvshow(idActor, idShow, strRole, iOrder) values(?, ?, ?, ?)"
                            cursor.execute(peoplesql, (actorid,id,Role,None))
                        if mediatype == "episode":
                            peoplesql="INSERT OR REPLACE into actorlinkepisode(idActor, idEpisode, strRole, iOrder) values(?, ?, ?, ?)"
                            cursor.execute(peoplesql, (actorid,id,Role,None))         
                        
                #### DIRECTORS ######
                if(person.get("Type") == "Director"):
                    
                    if kodiVersion == 15:
                        # Kodi Isengard database #
                        peoplesql="INSERT OR REPLACE into director_link(actor_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(peoplesql, (actorid, id, mediatype))
                    else:
                        # Kodi Gotham or Helix database #
                        if mediatype == "movie":
                            peoplesql="INSERT OR REPLACE into directorlinkmovie(idDirector, idMovie) values(?, ?)"
                        if mediatype == "tvshow":
                            peoplesql="INSERT OR REPLACE into directorlinktvshow(idDirector, idShow) values(?, ?)"
                        if mediatype == "musicvideo":
                            peoplesql="INSERT OR REPLACE into directorlinkmusicvideo(idDirector, idMVideo) values(?, ?)"
                        if mediatype == "episode":
                            peoplesql="INSERT OR REPLACE into directorlinkepisode(idDirector, idEpisode) values(?, ?)"
                        cursor.execute(peoplesql, (actorid,id))
                        
                #### WRITERS ######
                if(person.get("Type") == "Writing" or person.get("Type") == "Writer"):
                    
                    if kodiVersion == 15:
                        # Kodi Isengard database #
                        peoplesql="INSERT OR REPLACE into writer_link(actor_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(peoplesql, (actorid, id, mediatype))
                    else:
                        # Kodi Gotham or Helix database #
                        if mediatype == "movie":
                            peoplesql="INSERT OR REPLACE into writerlinkmovie(idWriter, idMovie) values(?, ?)"
                            cursor.execute(peoplesql, (actorid,id))
                        if mediatype == "episode":
                            peoplesql="INSERT OR REPLACE into writerlinkepisode(idWriter, idEpisode) values(?, ?)"
                            cursor.execute(peoplesql, (actorid,id))
                        

    def AddGenresToMedia(self, id, genres, mediatype, cursor):

        if genres:
            
            kodiVersion = 14
            if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
                kodiVersion = 15
            
            for genre in genres:

                if kodiVersion == 15:
                    genre_id = None
                    cursor.execute("SELECT genre_id as genre_id FROM genre WHERE name = ?",(genre,))
                    result = cursor.fetchone()
                    if result != None:
                        genre_id = result[0]
                    #create genre
                    if genre_id == None:
                        cursor.execute("select coalesce(max(genre_id),0) as genre_id from genre")
                        genre_id = cursor.fetchone()[0]
                        genre_id = genre_id + 1
                        sql="insert into genre(genre_id, name) values(?, ?)"
                        cursor.execute(sql, (genre_id,genre))
                    
                    #assign genre to item    
                    utils.logMsg("AddGenresToMedia", "Processing : " + genre)
                    sql="INSERT OR REPLACE into genre_link(genre_id, media_id, media_type) values(?, ?, ?)"
                    cursor.execute(sql, (genre_id, id, mediatype))
                
                else:
                    idGenre = None
                    cursor.execute("SELECT idGenre as idGenre FROM genre WHERE strGenre = ?",(genre,))
                    result = cursor.fetchone()
                    if result != None:
                        idGenre = result[0]
                    #create genre
                    if idGenre == None:
                        cursor.execute("select coalesce(max(idGenre),0) as idGenre from genre")
                        idGenre = cursor.fetchone()[0]
                        idGenre = idGenre + 1
                        sql="insert into genre(idGenre, strGenre) values(?, ?)"
                        cursor.execute(sql, (idGenre,genre))

                    #assign genre to item    
                    utils.logMsg("AddGenresToMedia", "Processing : " + genre)
                    if mediatype == "movie":
                        sql="INSERT OR REPLACE into genrelinkmovie(idGenre, idMovie) values(?, ?)"
                    if mediatype == "tvshow":
                        sql="INSERT OR REPLACE into genrelinktvshow(idGenre, idShow) values(?, ?)"
                    if mediatype == "episode":
                        sql="INSERT OR REPLACE into genrelinkepisode(idGenre, idEpisode) values(?, ?)"
                    cursor.execute(sql, (idGenre,id))
    
    def AddStudiosToMedia(self, id, studios, mediatype, cursor):

        if studios:
            
            kodiVersion = 14
            if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
                kodiVersion = 15
            
            for studio in studios:

                if kodiVersion == 15:
                    studio_id = None
                    cursor.execute("SELECT studio_id as studio_id FROM studio WHERE name = ?",(studio,))
                    result = cursor.fetchone()
                    if result != None:
                        studio_id = result[0]
                    #create studio
                    if studio_id == None:
                        cursor.execute("select coalesce(max(studio_id),0) as studio_id from studio")
                        studio_id = cursor.fetchone()[0]
                        studio_id = studio_id + 1
                        sql="insert into studio(studio_id, name) values(?, ?)"
                        cursor.execute(sql, (studio_id,studio))
                    
                    #assign studio to item    
                    utils.logMsg("AddstudiosToMedia", "Processing : " + studio)
                    sql="INSERT OR REPLACE into studio_link(studio_id, media_id, media_type) values(?, ?, ?)"
                    cursor.execute(sql, (studio_id, id, mediatype))
                
                else:
                    idstudio = None
                    cursor.execute("SELECT idstudio as idstudio FROM studio WHERE strstudio = ?",(studio,))
                    result = cursor.fetchone()
                    if result != None:
                        idstudio = result[0]
                    #create studio
                    if idstudio == None:
                        cursor.execute("select coalesce(max(idstudio),0) as idstudio from studio")
                        idstudio = cursor.fetchone()[0]
                        idstudio = idstudio + 1
                        sql="insert into studio(idstudio, strstudio) values(?, ?)"
                        cursor.execute(sql, (idstudio,studio))

                    #assign studio to item    
                    utils.logMsg("AddstudiosToMedia", "Processing : " + studio)
                    if mediatype == "movie":
                        sql="INSERT OR REPLACE into studiolinkmovie(idstudio, idMovie) values(?, ?)"
                    if mediatype == "tvshow":
                        sql="INSERT OR REPLACE into studiolinktvshow(idstudio, idShow) values(?, ?)"
                    if mediatype == "episode":
                        sql="INSERT OR REPLACE into studiolinkepisode(idstudio, idEpisode) values(?, ?)"
                    cursor.execute(sql, (idstudio,id))
        
    def AddTagToMedia(self, id, tag, mediatype, cursor):

        if tag:
            
            kodiVersion = 14
            if xbmc.getInfoLabel("System.BuildVersion").startswith("15"):
                kodiVersion = 15
            
            if kodiVersion == 15:
                tag_id = None
                cursor.execute("SELECT tag_id as tag_id FROM tag WHERE name = ?",(tag,))
                result = cursor.fetchone()
                if result != None:
                    tag_id = result[0]
                #create tag
                if tag_id == None:
                    cursor.execute("select coalesce(max(tag_id),0) as tag_id from tag")
                    tag_id = cursor.fetchone()[0]
                    tag_id = tag_id + 1
                    sql="insert into tag(tag_id, name) values(?, ?)"
                    cursor.execute(sql, (tag_id,tag))
                
                #assign tag to item    
                utils.logMsg("AddTagToMedia", "Processing : " + tag)
                sql="INSERT OR REPLACE into tag_link(tag_id, media_id, media_type) values(?, ?, ?)"
                cursor.execute(sql, (tag_id, id, mediatype))
            
            else:
                idTag = None
                cursor.execute("SELECT idTag as idTag FROM tag WHERE strTag = ?",(tag,))
                result = cursor.fetchone()
                if result != None:
                    idTag = result[0]
                #create idTag
                if idTag == None:
                    cursor.execute("select coalesce(max(idTag),0) as idTag from tag")
                    idTag = cursor.fetchone()[0]
                    idTag = idTag + 1
                    sql="insert into tag(idTag, strTag) values(?, ?)"
                    cursor.execute(sql, (idTag,tag))

                #assign tag to item    
                utils.logMsg("AddTagToMedia", "Processing : " + tag)
                sql="INSERT OR REPLACE into taglinks(idTag, idMedia, media_type) values(?, ?, ?)"
                cursor.execute(sql, (idTag, id, mediatype))
       
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
            