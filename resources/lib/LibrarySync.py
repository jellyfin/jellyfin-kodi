#################################################################################################
# LibrarySync
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
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
                    if kodiItem['playcount'] != int(userData.get("PlayCount")):
                        xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "playcount": %i}, "id": 1 }' %(kodiItem['movieid'], int(userData.get("PlayCount"))))
            
            
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
        
        #TODO: only update the info if something is actually changed
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = downloadUtils.getArtwork(MBitem, "Primary")
        
        utils.logMsg("Updating item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
        #update artwork
        self.updateArtWork(KodiItem,"poster", downloadUtils.getArtwork(MBitem, "poster"))
        self.updateArtWork(KodiItem,"clearlogo", downloadUtils.getArtwork(MBitem, "Logo"))
        self.updateArtWork(KodiItem,"banner", downloadUtils.getArtwork(MBitem, "Banner"))
        self.updateArtWork(KodiItem,"landscape", downloadUtils.getArtwork(MBitem, "Thumb"))
        self.updateArtWork(KodiItem,"discart", downloadUtils.getArtwork(MBitem, "Disc"))
        self.updateArtWork(KodiItem,"fanart", downloadUtils.getArtwork(MBitem, "Backdrop"))
        
        #update duration
        duration = (int(timeInfo.get('Duration'))*60)
        if KodiItem['runtime'] != duration:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "runtime": %s}, "id": 1 }' %(KodiItem['movieid'], duration))
               
        #update year
        if KodiItem['year'] != MBitem.get("ProductionYear") and MBitem.get("ProductionYear") != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "year": %s}, "id": 1 }' %(KodiItem['movieid'], MBitem.get("ProductionYear")))
        
        #update strm file - TODO: only update strm when path has changed
        self.createSTRM(MBitem["Id"])
        
        #update nfo file - needed for testing
        nfoFile = os.path.join(movieLibrary,MBitem["Id"],MBitem["Id"] + ".nfo")
        if not xbmcvfs.exists(nfoFile):
            self.createNFO(MBitem)
        
        #update playcounts
        if KodiItem['playcount'] != int(userData.get("PlayCount")):
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "playcount": %i}, "id": 1 }' %(KodiItem['movieid'], int(userData.get("PlayCount"))))         
    
    
    def updateArtWork(self,KodiItem,artWorkName,artworkValue):
        if KodiItem['art'].has_key(artWorkName):
            if KodiItem['art'][artWorkName] != artworkValue and artworkValue != None:
                xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "art": { "%s": "%s" }}, "id": 1 }' %(KodiItem['movieid'], artWorkName, artworkValue))
                
    
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
    
    def getKodiMovie(self, id):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties" : ["art", "rating", "thumbnail", "runtime", "year", "plot", "playcount", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movie = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']
                movie = movies[0]

        return movie
