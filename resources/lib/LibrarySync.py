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

sleepVal = 20
showProgress = True

processMovies = True
processTvShows = False


class LibrarySync():   
        
    def syncDatabase(self):
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None

        #set some variable to check if this is the first run
        startupDone = False
        startupStr = WINDOW.getProperty("startup")
        if startupStr == "done":
            startupDone = True
        
        #are we running startup sync or background sync ?
        if not startupDone:
            syncOption = addon.getSetting("syncSettingStartup")
        else:
            syncOption = addon.getSetting("syncSettingBackground")
        
        #what sync method to perform ?
        if syncOption == "Full Sync":
            self.MoviesSync(True)
        if syncOption == "Incremental Sync":
            self.MoviesSync(False)
        
        WINDOW.setProperty("startup", "done")
                        
              
    
    def MoviesSync(self, fullsync=True):
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None
        
        try:
        
            if(addon.getSetting("enableProgressFullSync")):
                pDialog = xbmcgui.DialogProgressBG()
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            allEmbyMovieIds = list()
                
            views = ReadEmbyDB().getCollections("movies")

            for view in views:
                
<<<<<<< HEAD
                updateNeeded = False
=======
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
                                if count % 10 == 0:
                                    pDialog.update(percentage, message=progMessage + " Movie: " + str(count))
                                count += 1
                        
            #process full tv shows sync
            if processTvShows:
                allTVShows = list()
                allEpisodes = list()
                tvShowData = ReadEmbyDB().getTVShows(True)
>>>>>>> 5127a770b59a941a51bae652ab239fafa77591b3
                
                #process new movies
                allMB3Movies = ReadEmbyDB().getMovies(view.get('id'), True, fullsync)
                allKodiIds = set(ReadKodiDB().getKodiMoviesIds(True))
            
                if(self.ShouldStop()):
                    return True            
            
                if(allMB3Movies == None):
                    return False
            
                if(pDialog != None):
                    pDialog.update(0, "Sync DB : Processing " + view.get('title'))
                    total = len(allMB3Movies) + 1
                    count = 1
                
                for item in allMB3Movies:
                    
                    if not item.get('IsFolder'):
                        allEmbyMovieIds.append(item["Id"])
                        progMessage = "Updating movies"
                        item['Tag'] = []
                        item['Tag'].append(view.get('title'))
                        
                        if item["Id"] not in allKodiIds:
                            xbmc.sleep(sleepVal)
                            WriteKodiDB().addMovieToKodiLibrary(item)
                            updateNeeded = True
                            progMessage = "Adding"
                        
                        if(self.ShouldStop()):
                            return True
                                               
                        if(self.ShouldStop()):
                            return True
                    
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
<<<<<<< HEAD
                            pDialog.update(percentage, message=progMessage + " Movie: " + str(count))
                            count += 1
=======
                            if count % 10 == 0:
                                pDialog.update(percentage, message=progMessage + " Tv Show: " + str(count))
                            count += 1                        
                        
>>>>>>> 5127a770b59a941a51bae652ab239fafa77591b3
                
                #initiate library update and wait for finish before processing any updates
                if updateNeeded:
                    self.doKodiLibraryUpdate()  
                
                if(self.ShouldStop()):
                    return True
                
                #process updates
                allKodiMovies = ReadKodiDB().getKodiMovies(True)
                for item in allMB3Movies:
                    
                    if not item.get('IsFolder'):
                        progMessage = "Updating movies"
                        item['Tag'] = []
                        item['Tag'].append(view.get('title'))
                        
                        progMessage = "Updating"
                        
                        for kodimovie in allKodiMovies:
                            if item["Id"] in kodimovie["file"]:
                                WriteKodiDB().updateMovieToKodiLibrary(item,kodimovie)
                                break
                        
                        if(self.ShouldStop()):
                            return True
                                               
                        if(self.ShouldStop()):
                            return True
                    
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
<<<<<<< HEAD
                            pDialog.update(percentage, message=progMessage + " Movie: " + str(count))
                            count += 1
=======
                            if count % 10 == 0:
                                pDialog.update(percentage, message=progMessage + " Episode: " + str(count))
                            count += 1    
                    
            
>>>>>>> 5127a770b59a941a51bae652ab239fafa77591b3
            
            if(pDialog != None):
                pDialog.update(0, message="Removing Deleted Items")
            
            if(self.ShouldStop()):
                return True            
            
            cleanNeeded = False
            
            # process any deletes only at fullsync
            if fullsync:
                allKodiIds = ReadKodiDB().getKodiMoviesIds(True)
                allEmbyMovieIds = set(allEmbyMovieIds)
                for kodiId in allKodiIds:
                    if not kodiId in allEmbyMovieIds:
                        xbmc.sleep(sleepVal)
                        print "delete needed for: " + kodiId
                        WriteKodiDB().deleteMovieFromKodiLibrary(dir)
                        cleanNeeded = True
            
            if(self.ShouldStop()):
                return True            
            
            #initiate library clean and wait for finish before processing any updates
            if cleanNeeded:
                doKodiLibraryUpdate(True)
                    
            if(self.ShouldStop()):
                return True
        
        finally:
            WINDOW.clearProperty("librarysync")
            if(pDialog != None):
                pDialog.close()
        
        return True
    
    def doKodiLibraryUpdate(self,clean=False):
        #initiate library update and wait for finish before processing any updates
        if clean:
            xbmc.executebuiltin("CleanLibrary(video)")
        else:
            xbmc.executebuiltin("UpdateLibrary(video)")
        xbmc.sleep(1000)
        while (xbmc.getCondVisibility("Library.IsScanningVideo")):
            if(self.ShouldStop()):
                return True
            xbmc.sleep(250)
    
    def updatePlayCounts(self):
        #update all playcounts from MB3 to Kodi library
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None
        
        try:
            if(addon.getSetting("enableProgressPlayCountSync")):
                pDialog = xbmcgui.DialogProgressBG()
            if(pDialog != None):
                pDialog.create('Sync PlayCounts', 'Sync PlayCounts')        
        
            #process movies
            if processMovies:
                views = ReadEmbyDB().getCollections("movies")
                for view in views:
                    allMB3Movies = ReadEmbyDB().getMovies(view.get('id'),False)
                
                    if(self.ShouldStop()):
                        return True
                            
                    if(allMB3Movies == None):
                        return False    
                
                    if(pDialog != None):
                        pDialog.update(0, "Sync PlayCounts: Processing Movies")
                        totalCount = len(allMB3Movies) + 1
                        count = 1            
                
                    for item in allMB3Movies:
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
                                if count % 10 == 0:
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
                                if count % 10 == 0:
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

        
        
        