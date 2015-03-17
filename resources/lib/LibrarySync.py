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
from WriteKodiDB import WriteKodiDB
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
                                WriteKodiDB().addMovieToKodiLibrary(item)
                                updateNeeded = True
                                progMessage = "Adding"
                            else:
                                WriteKodiDB().updateMovieToKodiLibrary(item, kodiItem)
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
                            WriteKodiDB().addTVShowToKodiLibrary(item)
                            updateNeeded = True
                            progMessage = "Adding"
                        else:
                            WriteKodiDB().updateTVShowToKodiLibrary(item, kodiItem)
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
                                    WriteKodiDB().updateEpisodeToKodiLibrary(item,KodiItem,tvshow)
                                    matchFound = True
                                    progMessage = "Updating"

                        if not matchFound:
                            #no match so we have to create it
                            print "episode not found...creating it: "
                            WriteKodiDB().addEpisodeToKodiLibrary(item,tvshow)
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
                        WriteKodiDB().deleteMovieFromKodiLibrary(dir)
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
                        WriteKodiDB().deleteTVShowFromKodiLibrary(dir)
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
                                WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"movie")
                      
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    print "updating resumepoint for movie " + str(kodiItem['movieid'])
                                    WriteKodiDB().setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
                                
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
                                    WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode")
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    WriteKodiDB().setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                                    
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
    
    def ShouldStop(self):
        if(xbmc.Player().isPlaying() or xbmc.abortRequested):
            return True
        else:
            return False

        
        
        