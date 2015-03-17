#################################################################################################
# LibrarySync
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import sqlite3
import inspect
import threading
import urllib
from datetime import datetime, timedelta, time
import urllib2
import os

from API import API
import Utils as utils
from DownloadUtils import DownloadUtils
from ReadEmbyDB import ReadEmbyDB
from ReadKodiDB import ReadKodiDB
from CreateFiles import CreateFiles

addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')

sleepVal = 10
showProgress = True

processMovies = True
processTvShows = True


class LibrarySync():   
        
    def syncDatabase(self):
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None
        
        try:
        
            if(showProgress):
                pDialog = xbmcgui.DialogProgressBG()
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            updateNeeded = False    
            
            #process full movies sync
            if processMovies:
                allMovies = list()
                
                views = ReadEmbyDB().getCollections("movies")
                for view in views:
            
                    movieData = ReadEmbyDB().getMovies(view.get('id'), True)
                
                    if(self.ShouldStop()):
                        return True            
                
                    if(movieData == None):
                        return False
                
                    if(pDialog != None):
                        pDialog.update(0, "Sync DB : Processing " + view.get('title'))
                        total = len(movieData) + 1
                        count = 1
                    
                    for item in movieData:
                        xbmc.sleep(sleepVal)
                        if not item.get('IsFolder'):
                            kodiItem = ReadKodiDB().getKodiMovie(item["Id"])
                            allMovies.append(item["Id"])
                            progMessage = "Processing"
                            item['Tag'] = []
                            item['Tag'].append(view.get('title'))
                            if kodiItem == None:
                                self.addMovieToKodiLibrary(item)
                                updateNeeded = True
                                progMessage = "Adding"
                            else:
                                self.updateMovieToKodiLibrary(item, kodiItem)
                                progMessage = "Updating"
                        
                            if(self.ShouldStop()):
                                return True
                        
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(total)) * 100))
                                pDialog.update(percentage, message=progMessage + " Movie: " + str(count))
                                count += 1
                        
            #process full tv shows sync
            if processTvShows:
                allTVShows = list()
                allEpisodes = list()
                tvShowData = ReadEmbyDB().getTVShows(True)
                
                if(self.ShouldStop()):
                    return True            
                
                if (tvShowData == None):
                    return
                    
                if(pDialog != None):
                    pDialog.update(0, "Sync DB : Processing TV Shows")
                    total = len(tvShowData) + 1
                    count = 0
                    
                for item in tvShowData:
                    xbmc.sleep(sleepVal)
                    if item.get('IsFolder'):
                        kodiItem = ReadKodiDB().getKodiTVShow(item["Id"])
                        allTVShows.append(item["Id"])
                        progMessage = "Processing"
                        if kodiItem == None:
                            self.addTVShowToKodiLibrary(item)
                            updateNeeded = True
                            progMessage = "Adding"
                        else:
                            self.updateTVShowToKodiLibrary(item, kodiItem)
                            progMessage = "Updating"
                            
                        if(self.ShouldStop()):
                            return True
                            
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, message=progMessage + " Tv Show: " + str(count))
                            count += 1                        
                        
                
                #process episodes (will only be possible when tv show is scanned to library)   
                #TODO --> maybe pull full info only when needed ?
                allEpisodes = list()
                
                for tvshow in allTVShows:
                    
                    episodeData = ReadEmbyDB().getEpisodes(tvshow,True)
                    kodiEpisodes = ReadKodiDB().getKodiEpisodes(tvshow)
                    
                    if(self.ShouldStop()):
                        return True                
                    
                    if(pDialog != None):
                        pDialog.update(0, "Sync DB : Processing Episodes")
                        total = len(episodeData) + 1
                        count = 0         

                    #we have to compare the lists somehow
                    for item in episodeData:
                        xbmc.sleep(sleepVal)
                        comparestring1 = str(item.get("ParentIndexNumber")) + "-" + str(item.get("IndexNumber"))
                        matchFound = False
                        progMessage = "Processing"
                        if kodiEpisodes != None:
                            for KodiItem in kodiEpisodes:
                                
                                allEpisodes.append(KodiItem["episodeid"])
                                comparestring2 = str(KodiItem["season"]) + "-" + str(KodiItem["episode"])
                                if comparestring1 == comparestring2:
                                    #match found - update episode
                                    self.updateEpisodeToKodiLibrary(item,KodiItem,tvshow)
                                    matchFound = True
                                    progMessage = "Updating"

                        if not matchFound:
                            #no match so we have to create it
                            print "episode not found...creating it: "
                            self.addEpisodeToKodiLibrary(item,tvshow)
                            updateNeeded = True
                            progMessage = "Adding"
                            
                        if(self.ShouldStop()):
                            return True                        
                            
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, message=progMessage + " Episode: " + str(count))
                            count += 1    
                    
            
            
            if(pDialog != None):
                pDialog.update(0, message="Removing Deleted Items")
            
            if(self.ShouldStop()):
                return True            
            
            cleanNeeded = False
            
            # process deletes for movies
            if processMovies:
                allLocaldirs, filesMovies = xbmcvfs.listdir(movieLibrary)
                allMB3Movies = set(allMovies)
                for dir in allLocaldirs:
                    if not dir in allMB3Movies:
                        self.deleteMovieFromKodiLibrary(dir)
                        cleanneeded = True
                
                if(self.ShouldStop()):
                    return True            
            
            # process deletes for episodes
            if processTvShows:
                # TODO --> process deletes for episodes !!!
                allLocaldirs, filesTVShows = xbmcvfs.listdir(tvLibrary)
                allMB3TVShows = set(allTVShows)
                for dir in allLocaldirs:
                    if not dir in allMB3TVShows:
                        self.deleteTVShowFromKodiLibrary(dir)
                        cleanneeded = True
                    
            if(self.ShouldStop()):
                return True
                        
            if cleanNeeded:
                WINDOW.setProperty("cleanNeeded", "true")
            
            if updateNeeded:
                WINDOW.setProperty("updateNeeded", "true")
        
        finally:
            WINDOW.clearProperty("librarysync")
            if(pDialog != None):
                pDialog.close()
        
        return True
                              
    def updatePlayCounts(self):
        #update all playcounts from MB3 to Kodi library
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None
        
        try:
            if(showProgress):
                pDialog = xbmcgui.DialogProgressBG()
            if(pDialog != None):
                pDialog.create('Sync PlayCounts', 'Sync PlayCounts')        
        
            #process movies
            if processMovies:
                views = ReadEmbyDB().getCollections("movies")
                for view in views:
                    movieData = ReadEmbyDB().getMovies(view.get('id'),False)
                
                    if(self.ShouldStop()):
                        return True
                            
                    if(movieData == None):
                        return False    
                
                    if(pDialog != None):
                        pDialog.update(0, "Sync PlayCounts: Processing Movies")
                        totalCount = len(movieData) + 1
                        count = 1            
                
                    for item in movieData:
                        xbmc.sleep(sleepVal)
                        if not item.get('IsFolder'):
                            kodiItem = ReadKodiDB().getKodiMovie(item["Id"])
                            userData=API().getUserData(item)
                            timeInfo = API().getTimeInfo(item)
                            if kodiItem != None:
                                self.updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"movie")
                      
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    print "updating resumepoint for movie " + str(kodiItem['movieid'])
                                    self.setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
                                
                            if(self.ShouldStop()):
                                return True
                            
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(totalCount)) * 100))
                                pDialog.update(percentage, message="Updating Movie: " + str(count))
                                count += 1                              
                        
            #process Tv shows
            if processTvShows:
                tvshowData = ReadEmbyDB().getTVShows(False)
                
                if(self.ShouldStop()):
                    return True
                            
                if (tvshowData == None):
                    return False    
                
                for item in tvshowData:
                    xbmc.sleep(sleepVal)
                    episodeData = ReadEmbyDB().getEpisodes(item["Id"], False)
                    
                    if (episodeData != None):
                        if(pDialog != None):
                            pDialog.update(0, "Sync PlayCounts: Processing Episodes")
                            totalCount = len(episodeData) + 1
                            count = 1                  
                    
                        for episode in episodeData:
                            xbmc.sleep(sleepVal)
                            kodiItem = ReadKodiDB().getKodiEpisodeByMbItem(episode)
                            userData=API().getUserData(episode)
                            timeInfo = API().getTimeInfo(episode)
                            if kodiItem != None:
                                if kodiItem['playcount'] != int(userData.get("PlayCount")):
                                    self.updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode")
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    self.setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                                    
                            if(self.ShouldStop()):
                                return True
                            
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(totalCount)) * 100))
                                pDialog.update(percentage, message="Updating Episode: " + str(count))
                                count += 1       

        finally:
            WINDOW.clearProperty("librarysync")
            if(pDialog != None):
                pDialog.close()            
        
        return True
    
    def updatePlayCountFromKodi(self, id, playcount=0):
        #when user marks item watched from kodi interface update this to MB3
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()           
        
        print "updateplaycount called!"
        
        # TODO --> extend support for episodes
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

                    watchedurl = 'http://' + server + '/mediabrowser/Users/' + userid + '/PlayedItems/' + mb3Id
                    utils.logMsg("MB3 Sync","watchedurl -->" + watchedurl)
                    if playcount != 0:
                        downloadUtils.downloadUrl(watchedurl, postBody="", type="POST")
                    else:
                        downloadUtils.downloadUrl(watchedurl, type="DELETE")
        
    def updateMovieToKodiLibrary( self, MBitem, KodiItem ):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        changes = False
        
        #update artwork
        changes = self.updateArtWork(KodiItem,"poster", API().getArtwork(MBitem, "poster"),"movie")
        changes = self.updateArtWork(KodiItem,"clearlogo", API().getArtwork(MBitem, "Logo"),"movie")
        changes = self.updateArtWork(KodiItem,"clearart", API().getArtwork(MBitem, "Art"),"movie")
        changes = self.updateArtWork(KodiItem,"banner", API().getArtwork(MBitem, "Banner"),"movie")
        changes = self.updateArtWork(KodiItem,"landscape", API().getArtwork(MBitem, "Thumb"),"movie")
        changes = self.updateArtWork(KodiItem,"discart", API().getArtwork(MBitem, "Disc"),"movie")
        changes = self.updateArtWork(KodiItem,"fanart", API().getArtwork(MBitem, "Backdrop"),"movie")
        
        #update common properties
        duration = (int(timeInfo.get('Duration'))*60)
        changes = self.updateProperty(KodiItem,"runtime",duration,"movie")
        changes = self.updateProperty(KodiItem,"year",MBitem.get("ProductionYear"),"movie")
        changes = self.updateProperty(KodiItem,"mpaa",MBitem.get("OfficialRating"),"movie")
        
        changes = self.updatePropertyArray(KodiItem,"tag",MBitem.get("Tag"),"movie")
        
        if MBitem.get("CriticRating") != None:
            changes = self.updateProperty(KodiItem,"rating",int(MBitem.get("CriticRating"))/10,"movie")
        
        changes = self.updateProperty(KodiItem,"plotoutline",MBitem.get("ShortOverview"),"movie")
        changes = self.updateProperty(KodiItem,"set",MBitem.get("TmdbCollectionName"),"movie")
        changes = self.updateProperty(KodiItem,"sorttitle",MBitem.get("SortName"),"movie")
        
        if MBitem.get("ProviderIds") != None:
            if MBitem.get("ProviderIds").get("Imdb") != None:
                changes = self.updateProperty(KodiItem,"imdbnumber",MBitem.get("ProviderIds").get("Imdb"),"movie")
        
        # FIXME --> Taglines not returned by MB3 server !?
        if MBitem.get("TagLines") != None:
            changes = self.updateProperty(KodiItem,"tagline",MBitem.get("TagLines")[0],"movie")      
        
        changes = self.updatePropertyArray(KodiItem,"writer",people.get("Writer"),"movie")
        changes = self.updatePropertyArray(KodiItem,"director",people.get("Director"),"movie")
        changes = self.updatePropertyArray(KodiItem,"genre",MBitem.get("Genres"),"movie")
        changes = self.updatePropertyArray(KodiItem,"studio",studios,"movie")
        # FIXME --> ProductionLocations not returned by MB3 server !?
        self.updatePropertyArray(KodiItem,"country",MBitem.get("ProductionLocations"),"movie")
        
        #trailer link
        trailerUrl = None
        if MBitem.get("LocalTrailerCount") != None and MBitem.get("LocalTrailerCount") > 0:
            itemTrailerUrl = "http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + MBitem.get("Id") + "/LocalTrailers?format=json"
            jsonData = downloadUtils.downloadUrl(itemTrailerUrl, suppress=True, popup=0 )
            if(jsonData != ""):
                trailerItem = json.loads(jsonData)
                trailerUrl = "plugin://plugin.video.mb3sync/?id=" + trailerItem[0].get("Id") + '&mode=play'
                changes = self.updateProperty(KodiItem,"trailer",trailerUrl,"movie")
        
        #add actors
        self.AddActorsToMedia(KodiItem,MBitem.get("People"),"movie")
        
        CreateFiles().createSTRM(MBitem)
        CreateFiles().createNFO(MBitem)
        
        if changes:
            utils.logMsg("Updated item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
    def updateTVShowToKodiLibrary( self, MBitem, KodiItem ):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        changes = False
        
        #update artwork
        changes = self.updateArtWork(KodiItem,"poster", API().getArtwork(MBitem, "Primary"),"tvshow")
        changes = self.updateArtWork(KodiItem,"clearlogo", API().getArtwork(MBitem, "Logo"),"tvshow")
        changes = self.updateArtWork(KodiItem,"clearart", API().getArtwork(MBitem, "Art"),"tvshow")
        changes = self.updateArtWork(KodiItem,"banner", API().getArtwork(MBitem, "Banner"),"tvshow")
        changes = self.updateArtWork(KodiItem,"landscape", API().getArtwork(MBitem, "Thumb"),"tvshow")
        changes = self.updateArtWork(KodiItem,"discart", API().getArtwork(MBitem, "Disc"),"tvshow")
        changes = self.updateArtWork(KodiItem,"fanart", API().getArtwork(MBitem, "Backdrop"),"tvshow")
        
        #update common properties
        if MBitem.get("PremiereDate") != None:
            premieredatelist = (MBitem.get("PremiereDate")).split("T")
            premieredate = premieredatelist[0]
            changes = self.updateProperty(KodiItem,"premiered",premieredate,"tvshow")
        
        changes = self.updateProperty(KodiItem,"mpaa",MBitem.get("OfficialRating"),"tvshow")
        
        if MBitem.get("CriticRating") != None:
            changes = self.updateProperty(KodiItem,"rating",int(MBitem.get("CriticRating"))/10,"tvshow")
        
        changes = self.updateProperty(KodiItem,"sorttitle",MBitem.get("SortName"),"tvshow")
        
        if MBitem.get("ProviderIds") != None:
            if MBitem.get("ProviderIds").get("Imdb") != None:
                changes = self.updateProperty(KodiItem,"imdbnumber",MBitem.get("ProviderIds").get("Imdb"),"tvshow")
        

        changes = self.updatePropertyArray(KodiItem,"genre",MBitem.get("Genres"),"tvshow")
        changes = self.updatePropertyArray(KodiItem,"studio",studios,"tvshow")
        
        # FIXME --> ProductionLocations not returned by MB3 server !?
        changes = self.updatePropertyArray(KodiItem,"country",MBitem.get("ProductionLocations"),"tvshow")
        
        #add actors
        changes = self.AddActorsToMedia(KodiItem,MBitem.get("People"),"tvshow")
        
        CreateFiles().createNFO(MBitem)
        
        if changes:
            utils.logMsg("Updated item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
                    
    def updateEpisodeToKodiLibrary( self, MBitem, KodiItem, tvshowId ):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()
        
        timeInfo = API().getTimeInfo(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        userData=API().getUserData(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        changes = False

        # TODO --> set season poster instead of show poster ?
        changes = self.updateArtWork(KodiItem,"poster", API().getArtwork(MBitem, "tvshow.poster"),"episode")
        changes = self.updateArtWork(KodiItem,"fanart", API().getArtwork(MBitem, "Backdrop"),"episode")
        changes = self.updateArtWork(KodiItem,"clearlogo", API().getArtwork(MBitem, "Logo"),"episode")
        changes = self.updateArtWork(KodiItem,"clearart", API().getArtwork(MBitem, "Art"),"episode")
        changes = self.updateArtWork(KodiItem,"banner", API().getArtwork(MBitem, "Banner"),"episode")
        changes = self.updateArtWork(KodiItem,"landscape", API().getArtwork(MBitem, "Thumb"),"episode")
        changes = self.updateArtWork(KodiItem,"discart", API().getArtwork(MBitem, "Disc"),"episode")
        
        
        #update common properties
        duration = (int(timeInfo.get('Duration'))*60)
        changes = self.updateProperty(KodiItem,"runtime",duration,"episode")
        
        if MBitem.get("PremiereDate") != None:
            premieredatelist = (MBitem.get("PremiereDate")).split("T")
            premieredate = premieredatelist[0]
            premieretime = premieredatelist[1].split(".")[0]
            firstaired = premieredate + " " + premieretime
            # for Helix we use the whole time string, for kodi 15 we have to change to only the datestring
            # see: http://forum.kodi.tv/showthread.php?tid=218743
            if KodiItem["firstaired"] != premieredate:
                self.updateProperty(KodiItem,"firstaired",firstaired,"episode")
        
        if MBitem.get("CriticRating") != None:
            changes = self.updateProperty(KodiItem,"rating",int(MBitem.get("CriticRating"))/10,"episode")

        changes = self.updatePropertyArray(KodiItem,"writer",people.get("Writer"),"episode")

        #add actors
        changes = self.AddActorsToMedia(KodiItem,MBitem.get("People"),"episode")
        
        CreateFiles().createNFO(MBitem, tvshowId)
        CreateFiles().createSTRM(MBitem, tvshowId)
        
        if changes:
            utils.logMsg("Updated item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
    
    # adds or updates artwork to the given Kodi file in database
    def updateArtWork(self,KodiItem,artWorkName,artworkValue, fileType):
        if fileType == "tvshow":
            id = KodiItem['tvshowid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { musicvideoid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        
        changes = False
        if KodiItem['art'].has_key(artWorkName):
            curValue = urllib.unquote(KodiItem['art'][artWorkName]).decode('utf8')
            if not artworkValue in curValue:
                xbmc.sleep(sleepVal)
                utils.logMsg("MB3 Syncer","updating artwork..." + str(artworkValue) + " - " + str(curValue))
                xbmc.executeJSONRPC(jsoncommand %(id, artWorkName, artworkValue))
                changes = True
        elif artworkValue != None:
            xbmc.sleep(sleepVal)
            xbmc.executeJSONRPC(jsoncommand %(id, artWorkName, artworkValue))
            changes = True
            
        return changes
    
    # adds or updates the given property on the videofile in Kodi database
    def updateProperty(self,KodiItem,propertyName,propertyValue,fileType):
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
        
        changes = False
        if propertyValue != KodiItem[propertyName]:
            if propertyValue != None:
                if type(propertyValue) is int:
                    xbmc.sleep(sleepVal)
                    utils.logMsg("MB3 Sync","updating property..." + str(propertyName))
                    utils.logMsg("MB3 Sync","kodi value:" + str(KodiItem[propertyName]) + " MB value: " + str(propertyValue))
                    xbmc.executeJSONRPC(jsoncommand_i %(id, propertyName, propertyValue))
                    changes = True
                else:
                    xbmc.sleep(sleepVal)
                    utils.logMsg("MB3 Sync","updating property..." + str(propertyName))
                    utils.logMsg("MB3 Sync","kodi value:" + KodiItem[propertyName] + " MB value: " + propertyValue)
                    xbmc.executeJSONRPC(jsoncommand_s %(id, propertyName, propertyValue.encode('utf-8')))
                    changes = True
                    
        return changes

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
        if propertyCollection != None:
            currentvalues = set(KodiItem[propertyName])
            genrestring = ""
            for item in propertyCollection:
                if not item in currentvalues:
                    pendingChanges = True
                    json_array = json.dumps(propertyCollection)
            
            if pendingChanges:
                xbmc.sleep(sleepVal)
                utils.logMsg("MB3 Sync","updating propertyarray... Name:" + str(propertyName) + " Current:" + str(currentvalues) + " New:" + str(json_array))
                xbmc.executeJSONRPC(jsoncommand %(id,propertyName,json_array))

        return pendingChanges
    
    def addMovieToKodiLibrary( self, item ):
        itemPath = os.path.join(movieLibrary,item["Id"])
        strmFile = os.path.join(itemPath,item["Id"] + ".strm")
        
        changes = False
        
        #create path if not exists
        if not xbmcvfs.exists(itemPath + os.sep):
            xbmcvfs.mkdir(itemPath)
        
        #create nfo file
        changes = CreateFiles().createNFO(item)
        
        # create strm file
        changes = CreateFiles().createSTRM(item)
        
        if changes:
            utils.logMsg("MB3 Sync","Added movie to Kodi Library",item["Id"] + " - " + item["Name"])
    
    def addEpisodeToKodiLibrary(self, item, tvshowId):
        
        changes = False

        #create nfo file
        changes = CreateFiles().createNFO(item, tvshowId)
        
        # create strm file
        changes = CreateFiles().createSTRM(item, tvshowId)
        
        if changes:
            utils.logMsg("MB3 Sync","Added episode to Kodi Library",item["Id"] + " - " + item["Name"])
    
    def deleteMovieFromKodiLibrary(self, id ):
        kodiItem = ReadKodiDB().getKodiMovie(id)
        utils.logMsg("deleting movie from Kodi library",id)
        if kodiItem != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveMovie", "params": { "movieid": %i}, "id": 1 }' %(kodiItem["movieid"]))
        
        path = os.path.join(movieLibrary,id)
        xbmcvfs.rmdir(path)
        
    def addTVShowToKodiLibrary( self, item ):
        itemPath = os.path.join(tvLibrary,item["Id"])
        
        changes = False
        
        #create path if not exists
        if not xbmcvfs.exists(itemPath + os.sep):
            xbmcvfs.mkdir(itemPath)
            
        #create nfo file
        changes = CreateFiles().createNFO(item)
        
        if changes:
            utils.logMsg("Added TV Show to Kodi Library ",item["Id"] + " - " + item["Name"])
        
    def deleteTVShowFromKodiLibrary(self, id ):
        kodiItem = ReadKodiDB().getKodiTVShow(id)
        utils.logMsg("deleting tvshow from Kodi library",id)
        if kodiItem != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveTVShow", "params": { "tvshowid": %i}, "id": 1 }' %(kodiItem["tvshowid"]))
        path = os.path.join(tvLibrary,id)
        xbmcvfs.rmdir(path)
    
    def setKodiResumePoint(self, id, resume_seconds, total_seconds, fileType):
        #use sqlite to set the resume point while json api doesn't support this yet
        #todo --> submit PR to kodi team to get this added to the jsonrpc api
        
        utils.logMsg("MB3 Sync","setting resume point in kodi db..." + fileType + ": " + str(id))
        
        dbPath = xbmc.translatePath("special://userdata/Database/MyVideos90.db")
        connection = sqlite3.connect(dbPath)
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
    
    def AddActorsToMedia(self, KodiItem, people, mediatype):
        #use sqlite to set add the actors while json api doesn't support this yet
        #todo --> submit PR to kodi team to get this added to the jsonrpc api
        
        downloadUtils = DownloadUtils()
        if mediatype == "movie":
            id = KodiItem["movieid"]
        if mediatype == "tvshow":
            id = KodiItem["tvshowid"]
        if mediatype == "episode":
            id = KodiItem["episodeid"]

        
        dbPath = xbmc.translatePath("special://userdata/Database/MyVideos90.db")
        connection = sqlite3.connect(dbPath)
        cursor = connection.cursor()
        
        currentcast = list()
        if KodiItem["cast"] != None:
            for cast in KodiItem["cast"]:
                currentcast.append(cast["name"])

        if(people != None):
            for person in people:              
                if(person.get("Type") == "Actor"):
                    if person.get("Name") not in currentcast:
                        Name = person.get("Name")
                        Role = person.get("Role")
                        actorid = None
                        Thumb = downloadUtils.imageUrl(person.get("Id"), "Primary", 0, 400, 400)
                        cursor.execute("SELECT idActor as actorid FROM actors WHERE strActor = ?",(Name,))
                        result = cursor.fetchone()
                        if result != None:
                            actorid = result[0]
                        if actorid == None:
                            cursor.execute("select coalesce(max(idActor),0) as actorid from actors")
                            actorid = cursor.fetchone()[0]
                            actorid = actorid + 1
                            peoplesql="insert into actors(idActor, strActor, strThumb) values(?, ?, ?)"
                            cursor.execute(peoplesql, (actorid,Name,Thumb))
                        
                        if mediatype == "movie":
                            peoplesql="INSERT OR REPLACE into actorlinkmovie(idActor, idMovie, strRole, iOrder) values(?, ?, ?, ?)"
                        if mediatype == "tvshow":
                            peoplesql="INSERT OR REPLACE into actorlinktvshow(idActor, idShow, strRole, iOrder) values(?, ?, ?, ?)"
                        if mediatype == "episode":
                            peoplesql="INSERT OR REPLACE into actorlinkepisode(idActor, idEpisode, strRole, iOrder) values(?, ?, ?, ?)"
                        cursor.execute(peoplesql, (actorid,id,Role,None))
        
        connection.commit()
        cursor.close()
    
    
    def ShouldStop(self):
        if(xbmc.Player().isPlaying() or xbmc.abortRequested):
            return True
        else:
            return False

        
        
        