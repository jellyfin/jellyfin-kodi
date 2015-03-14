#################################################################################################
# LibrarySync
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import sqlite3
import threading
import urllib
from datetime import datetime, timedelta, time
import urllib2
import os

from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

from API import API
import Utils as utils
from DownloadUtils import DownloadUtils
downloadUtils = DownloadUtils()

addon       = xbmcaddon.Addon(id='plugin.video.mb3sync')
addondir   = xbmc.translatePath( addon.getAddonInfo('profile') )
dataPath = os.path.join(addondir,"library")
movieLibrary        = os.path.join(dataPath,'movies')
tvLibrary           = os.path.join(dataPath,'tvshows')

WINDOW = xbmcgui.Window( 10000 )
port = addon.getSetting('port')
host = addon.getSetting('ipaddress')
server = host + ":" + port
userid = downloadUtils.getUserId()


class LibrarySync():   
        
    def syncDatabase(self):
               
        WINDOW.setProperty("librarysync", "busy")       
        updateNeeded = False    
        
        allMovies = list()
        for item in self.getMovies(True):
            if not item.get('IsFolder'):
                kodiItem = self.getKodiMovie(item["Id"])
                allMovies.append(item["Id"])
                if kodiItem == None:
                    self.addMovieToKodiLibrary(item)
                    updateNeeded = True
                else:
                    self.updateMovieToKodiLibrary(item, kodiItem)
                
        cleanNeeded = False
        # process deletes
        allLocaldirs, filesMovies = xbmcvfs.listdir(movieLibrary)
        allMB3Movies = set(allMovies)
        for dir in allLocaldirs:
            if not dir in allMB3Movies:
                self.deleteMovieFromKodiLibrary(dir)
                cleanneeded = True
        
        if cleanNeeded:
            xbmc.executebuiltin("CleanLibrary(video)")
        
        if updateNeeded:
            xbmc.executebuiltin("UpdateLibrary(video)")
        
        WINDOW.clearProperty("librarysync")
                              
    def updatePlayCounts(self):
        #update all playcounts from MB3 to Kodi library
        
        WINDOW.setProperty("librarysync", "busy")

        for item in self.getMovies(False):
            if not item.get('IsFolder'):
                kodiItem = self.getKodiMovie(item["Id"])
                userData=API().getUserData(item)
                timeInfo = API().getTimeInfo(item)
                if kodiItem != None:
                    if kodiItem['playcount'] != int(userData.get("PlayCount")):
                        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "playcount": %i}, "id": 1 }' %(kodiItem['movieid'], int(userData.get("PlayCount"))))
                    
                    kodiresume = int(round(kodiItem['resume'].get("position")))
                    resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                    total = int(round(float(timeInfo.get("TotalTime"))))*60
                    if kodiresume != resume:
                        print "kodiresume -->" + str(kodiresume)
                        print "mb3_resume -->" + str(resume)
                        print "total -->" + str(total)
                        self.setKodiResumePoint(kodiItem['movieid'],resume,total)
            
        WINDOW.clearProperty("librarysync")
    
    def getMovies(self, fullinfo = False):
        result = None
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/Items?&SortBy=SortName&Fields=Path,Genres,Studios,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Movie&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/Items?&SortBy=SortName&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Movie&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        if jsonData != None:
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
    
    def updatePlayCountFromKodi(self, id, playcount=0):
        #when user marks item watched from kodi interface update this to MB3
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovieDetails", "params": { "movieid": ' + str(id) + ', "properties" : ["playcount", "file"] }, "id": "1"}')
        if json_response != None:
            jsonobject = json.loads(json_response.decode('utf-8','replace'))  
            movie = None
            if(jsonobject.has_key('result')):
                result = jsonobject['result']
                if(result.has_key('moviedetails')):
                    moviedetails = result['moviedetails']
                    filename = moviedetails.get("file").rpartition('\\')[2]
                    mb3Id = filename.replace(".strm","")

                    watchedurl = 'http://' + host + ':' + port + '/mediabrowser/Users/' + userid + '/PlayedItems/' + mb3Id
                    print "watchedurl -->" + watchedurl
                    if playcount != 0:
                        downloadUtils.downloadUrl(watchedurl, postBody="", type="POST")
                    else:
                        downloadUtils.downloadUrl(watchedurl, type="DELETE")
        
    def updateMovieToKodiLibrary( self, MBitem, KodiItem ):
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = downloadUtils.getArtwork(MBitem, "Primary")
        
        utils.logMsg("Updating item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
        #update artwork
        self.updateArtWork(KodiItem,"poster", downloadUtils.getArtwork(MBitem, "poster"),"movie")
        self.updateArtWork(KodiItem,"clearlogo", downloadUtils.getArtwork(MBitem, "Logo"),"movie")
        self.updateArtWork(KodiItem,"banner", downloadUtils.getArtwork(MBitem, "Banner"),"movie")
        self.updateArtWork(KodiItem,"landscape", downloadUtils.getArtwork(MBitem, "Thumb"),"movie")
        self.updateArtWork(KodiItem,"discart", downloadUtils.getArtwork(MBitem, "Disc"),"movie")
        self.updateArtWork(KodiItem,"fanart", downloadUtils.getArtwork(MBitem, "Backdrop"),"movie")
        
        #update common properties
        duration = (int(timeInfo.get('Duration'))*60)
        self.updateProperty(KodiItem,"runtime",duration,"movie")
        self.updateProperty(KodiItem,"year",MBitem.get("ProductionYear"),"movie")
        self.updateProperty(KodiItem,"writer",MBitem.get("Writer"),"movie")
        self.updateProperty(KodiItem,"mpaa",MBitem.get("OfficialRating"),"movie")
        self.updateProperty(KodiItem,"rating",MBitem.get("CommunityRating"),"movie")

        #trailer link
        trailerUrl = None
        if MBitem.get("LocalTrailerCount") != None and MBitem.get("LocalTrailerCount") > 0:
            itemTrailerUrl = "http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + MBitem.get("Id") + "/LocalTrailers?format=json"
            jsonData = downloadUtils.downloadUrl(itemTrailerUrl, suppress=True, popup=0 ) 
            trailerItem = json.loads(jsonData)
            trailerUrl = "plugin://plugin.video.mb3sync/?id=" + trailerItem[0].get("Id") + '&mode=play'
            self.updateProperty(KodiItem,"trailer",trailerUrl,"movie")
        
       
        #update genre
        if KodiItem['genre'] != MBitem.get("Genres") and MBitem.get("Genres") != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "genre": %s}, "id": 1 }' %(KodiItem['movieid'], "\"{koekoek,pannekoek} \""))
        
        
        #update strm file - TODO: only update strm when path has changed
        self.createSTRM(MBitem["Id"])
        
        #update nfo file - needed for testing
        nfoFile = os.path.join(movieLibrary,MBitem["Id"],MBitem["Id"] + ".nfo")
        if not xbmcvfs.exists(nfoFile):
            self.createNFO(MBitem)
        
        #update playcounts
        if KodiItem['playcount'] != int(userData.get("PlayCount")):
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "playcount": %i}, "id": 1 }' %(KodiItem['movieid'], int(userData.get("PlayCount"))))         
    

    # adds or updates artwork to the given Kodi file in database
    def updateArtWork(self,KodiItem,artWorkName,artworkValue, fileType="movie"):
        if fileType == "tvshow":
            method = "VideoLibrary.SetTVShowDetails"
        elif fileType == "episode":
            method = "VideoLibrary.SetEpisodeDetails"
        elif fileType == "musicvideo":
            method = "VideoLibrary.SetMusicVideoDetails"
        else:
            method = "VideoLibrary.SetMovieDetails"

        if KodiItem['art'].has_key(artWorkName):
            curValue = urllib.unquote(KodiItem['art'][artWorkName]).decode('utf8')
            if not artworkValue in curValue:
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "%s", "params": { "movieid": %i, "art": { "%s": "%s" }}, "id": 1 }' %(method,KodiItem['movieid'], artWorkName, artworkValue))
        elif artworkValue != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "%s", "params": { "movieid": %i, "art": { "%s": "%s" }}, "id": 1 }' %(method,KodiItem['movieid'], artWorkName, artworkValue))
    
    # adds or updates the given property on the videofile in Kodi database
    def updateProperty(self,KodiItem,propertyName,propertyValue,fileType="movie"):
        if fileType == "tvshow":
            method = "VideoLibrary.SetTVShowDetails"
        elif fileType == "episode":
            method = "VideoLibrary.SetEpisodeDetails"
        elif fileType == "musicvideo":
            method = "VideoLibrary.SetMusicVideoDetails"
        else:
            method = "VideoLibrary.SetMovieDetails"

        if not propertyValue in KodiItem[propertyName]:
            if type(propertyValue) is int:
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "%s", "params": { "movieid": %i, "%s": %i}, "id": 1 }' %(method,KodiItem['movieid'], propertyName, propertyValue))
            else:
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "%s", "params": { "movieid": %i, "%s": "%s"}, "id": 1 }' %(method,KodiItem['movieid'], propertyName, propertyValue))

    
    def createSTRM(self,id):
        
        itemPath = os.path.join(movieLibrary,id)
        if not xbmcvfs.exists(itemPath):
            xbmcvfs.mkdir(itemPath)
        
        strmFile = os.path.join(itemPath,id + ".strm")
        text_file = open(strmFile, "w")
        
        playUrl = "plugin://plugin.video.mb3sync/?id=" + id + '&mode=play'

        text_file.writelines(playUrl)
        text_file.close()
    
    def createNFO(self,item):
        timeInfo = API().getTimeInfo(item)
        userData=API().getUserData(item)
        people = API().getPeople(item)
        mediaStreams=API().getMediaStreams(item)
        
        #todo: change path if type is not movie
        itemPath = os.path.join(movieLibrary,item["Id"])
        nfoFile = os.path.join(itemPath,item["Id"] + ".nfo")
        
        root = Element("movie")
        SubElement(root, "id").text = item["Id"]
        SubElement(root, "tag").text = "all mediabrowser movies" # TODO --> use tags to assign user view 
        SubElement(root, "thumb").text = downloadUtils.getArtwork(item, "poster")
        SubElement(root, "fanart").text = downloadUtils.getArtwork(item, "Backdrop")
        SubElement(root, "title").text = item["Name"].encode('utf-8').decode('utf-8')
        SubElement(root, "originaltitle").text = item["Name"].encode('utf-8').decode('utf-8')
        
        SubElement(root, "year").text = str(item.get("ProductionYear"))
        SubElement(root, "runtime").text = str(timeInfo.get('Duration'))
        
        fileinfo = SubElement(root, "fileinfo")
        streamdetails = SubElement(fileinfo, "streamdetails")
        video = SubElement(streamdetails, "video")
        SubElement(video, "duration").text = str(mediaStreams.get('totaltime'))
        SubElement(video, "aspect").text = mediaStreams.get('aspectratio')
        SubElement(video, "codec").text = mediaStreams.get('videocodec')
        SubElement(video, "width").text = str(mediaStreams.get('width'))
        SubElement(video, "height").text = str(mediaStreams.get('height'))
        audio = SubElement(streamdetails, "audio")
        SubElement(audio, "codec").text = mediaStreams.get('audiocodec')
        SubElement(audio, "channels").text = mediaStreams.get('channels')
       
        SubElement(root, "plot").text = API().getOverview(item).decode('utf-8')

        art = SubElement(root, "art")
        SubElement(art, "poster").text = downloadUtils.getArtwork(item, "poster")
        SubElement(art, "fanart").text = downloadUtils.getArtwork(item, "Backdrop")
        SubElement(art, "landscape").text = downloadUtils.getArtwork(item, "Thumb")
        SubElement(art, "clearlogo").text = downloadUtils.getArtwork(item, "Logo")
        SubElement(art, "discart").text = downloadUtils.getArtwork(item, "Disc")
        SubElement(art, "banner").text = downloadUtils.getArtwork(item, "Banner")
        
        ET.ElementTree(root).write(nfoFile, encoding="utf-8", xml_declaration=True)
    
    def addMovieToKodiLibrary( self, item ):
        itemPath = os.path.join(movieLibrary,item["Id"])
        strmFile = os.path.join(itemPath,item["Id"] + ".strm")

        utils.logMsg("Adding item to Kodi Library",item["Id"] + " - " + item["Name"])
        
        #create path if not exists
        if not xbmcvfs.exists(itemPath):
            xbmcvfs.mkdir(itemPath)
            
        #create nfo file
        self.createNFO(item)
        
        # create strm file
        self.createSTRM(item["Id"])
            
    def deleteMovieFromKodiLibrary(self, id ):
        kodiItem = self.getKodiMovie(id)
        utils.logMsg("deleting movie from Kodi library",id)
        if kodiItem != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveMovie", "params": { "movieid": %i}, "id": 1 }' %(kodiItem["movieid"]))
        
        path = os.path.join(movieLibrary,id)
        xbmcvfs.rmdir(path)
    
    def setKodiResumePoint(self, id, resume_seconds, total_seconds):
        #use sqlite to set the resume point while json api doesn't support this yet
        #todo --> submit PR to kodi team to get this added to the jsonrpc api
        dbPath = xbmc.translatePath("special://userdata/Database/MyVideos90.db")
        connection = sqlite3.connect(dbPath)
        cursor = connection.cursor( )
        
        #cursor.execute("SELECT idBookmark FROM bookmark WHERE idFile = ?", (id,))
        #bmid=cursor.fetchone()[0]
        #if bmid != None:
            #cursor.execute("delete FROM bookmark WHERE idBookmark = ?", (bmid,))
        
        cursor.execute("delete FROM bookmark WHERE idFile = ?", (id,))
        cursor.execute("select coalesce(max(idBookmark),0) as bookmarkId from bookmark")
        bookmarkId =  cursor.fetchone()[0]
        bookmarkId = bookmarkId + 1
        bookmarksql="insert into bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, playerState, type) values(?, ?, ?, ?, ?, ?, ?, ?)"
        cursor.execute(bookmarksql, (bookmarkId,id,resume_seconds,total_seconds,None,"DVDPlayer",None,1))
        connection.commit()
        cursor.close()
    
    def getKodiMovie(self, id):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties" : ["art", "rating", "thumbnail", "resume", "runtime", "year", "genre", "cast", "trailer", "country", "studio", "set", "mpaa", "tagline", "plotoutline","plot", "writer", "playcount", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movie = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']
                movie = movies[0]

        return movie
