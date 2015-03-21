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

addondir = xbmc.translatePath(xbmcaddon.Addon(id='plugin.video.mb3sync').getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')

class LibrarySync():   
        
    def syncDatabase(self):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
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
        
            #pr = utils.startProfiling()
            self.MoviesSync(True)
            #utils.stopProfiling(pr, "MoviesSync(True)")
            
            #pr = utils.startProfiling()
            self.TvShowsSync(True)
            #utils.stopProfiling(pr, "TvShowsSync(True)")
            
        if syncOption == "Incremental Sync":
            self.MoviesSync(False)
            self.TvShowsSync(False)
        
        WINDOW.setProperty("startup", "done")
                        
        return True      
    
    def MoviesSync(self, fullsync=True):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        
        try:
            enableProgress = False
            if addon.getSetting("enableProgressFullSync") == 'true':
                enableProgress = True
                
            if(addon.getSetting("SyncFirstMovieRunDone") != 'true'):
                pDialog = xbmcgui.DialogProgress()
            elif(enableProgress):
                pDialog = xbmcgui.DialogProgressBG()
            
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            allEmbyMovieIds = list()
                
            views = ReadEmbyDB().getCollections("movies")
            viewCount = len(views)
            viewCurrent = 1
            progressTitle = ""
            
            for view in views:
                
                updateNeeded = False
                
                #process new movies
                allMB3Movies = ReadEmbyDB().getMovies(view.get('id'), True, fullsync)
                allKodiIds = set(ReadKodiDB().getKodiMoviesIds(True))
            
                if(self.ShouldStop(pDialog)):
                    return True            
            
                if(allMB3Movies == None):
                    return False
            
                if(pDialog != None):
                    progressTitle = "Sync DB : Processing " + view.get('title') + " " + str(viewCurrent) + " of " + str(viewCount)
                    pDialog.update(0, progressTitle)
                    total = len(allMB3Movies) + 1
                    count = 1
                
                for item in allMB3Movies:
                    
                    if not item.get('IsFolder'):
                        allEmbyMovieIds.append(item["Id"])
                        item['Tag'] = []
                        item['Tag'].append(view.get('title'))
                        
                        if item["Id"] not in allKodiIds:
                            WriteKodiDB().addMovieToKodiLibrary(item)
                            updateNeeded = True
                        
                        if(self.ShouldStop(pDialog)):
                            return True
                    
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, progressTitle, "Adding Movie: " + str(count))
                            count += 1
                
                #initiate library update and wait for finish before processing any updates
                if updateNeeded:
                    if(pDialog != None):
                        pDialog.update(0, "Processing New Items", "Importing STRM Files")
                    
                    if(pDialog != None and type(pDialog) == xbmcgui.DialogProgressBG):
                        pDialog.close()
                        
                    self.doKodiLibraryUpdate(False, pDialog)
                    
                    if(pDialog != None and type(pDialog) == xbmcgui.DialogProgressBG):
                        pDialog.create('Sync DB', 'Sync DB')
                
                if(self.ShouldStop(pDialog)):
                    return True

                if(pDialog != None):
                    progressTitle = "Sync DB : Processing " + view.get('title') + " " + str(viewCurrent) + " of " + str(viewCount)
                    pDialog.update(0, progressTitle, "")
                    total = len(allMB3Movies) + 1
                    count = 1                    
                
                #process updates
                allKodiMovies = ReadKodiDB().getKodiMovies(True)
                for item in allMB3Movies:
                    
                    if not item.get('IsFolder'):
                        item['Tag'] = []
                        item['Tag'].append(view.get('title'))
                        
                        kodimovie = allKodiMovies.get(item["Id"], None)
                        if(kodimovie != None):
                            #WriteKodiDB().updateMovieToKodiLibrary(item, kodimovie)
                            WriteKodiDB().updateMovieToKodiLibrary_Batched(item, kodimovie)
                        
                        if(self.ShouldStop(pDialog)):
                            return True
                    
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, progressTitle, "Updating Movie: " + str(count))
                            count += 1
                
                viewCurrent += 1
                
            if(pDialog != None):
                progressTitle = "Removing Deleted Items"
                pDialog.update(0, progressTitle, "")
            
            if(self.ShouldStop(pDialog)):
                return True            
            
            cleanNeeded = False
            
            # process any deletes only at fullsync
            if fullsync:
                allKodiIds = ReadKodiDB().getKodiMoviesIds(True)
                allEmbyMovieIds = set(allEmbyMovieIds)
                for kodiId in allKodiIds:
                    if not kodiId in allEmbyMovieIds:
                        WriteKodiDB().deleteMovieFromKodiLibrary(dir)
                        cleanNeeded = True
            
            if(self.ShouldStop(pDialog)):
                return True            
            
            #initiate library clean and wait for finish before processing any updates
            if cleanNeeded:
                self.doKodiLibraryUpdate(True, pDialog)
        
            addon.setSetting("SyncFirstMovieRunDone", "true")
            
        finally:
            if(pDialog != None):
                pDialog.close()
        
        return True
        
    def TvShowsSync(self, fullsync=True):

        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        
        try:
            enableProgress = False
            if addon.getSetting("enableProgressFullSync") == 'true':
                enableProgress = True
                
            if(addon.getSetting("SyncFirstTVRunDone") != 'true'):
                pDialog = xbmcgui.DialogProgress()
            elif(enableProgress):
                pDialog = xbmcgui.DialogProgressBG()
                
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
            
            progressTitle = "Sync DB : Processing Episodes"
            
            # incremental sync --> new episodes only
            if not fullsync:
                
                latestMBEpisodes = ReadEmbyDB().getLatestEpisodes(True)
                
                if latestMBEpisodes != None:
                    allKodiTvShowsIds = set(ReadKodiDB().getKodiTvShowsIds(True))
                    
                    updateNeeded = False
                    
                    if(pDialog != None):
                        pDialog.update(0, progressTitle)
                        total = len(latestMBEpisodes) + 1
                        count = 1                     
                    
                    # process new episodes
                    for episode in latestMBEpisodes:
                        if episode["SeriesId"] in allKodiTvShowsIds:
                            #only process tvshows that already exist in the db at incremental updates
                            kodiEpisodes = ReadKodiDB().getKodiEpisodes(episode["SeriesId"],True,True)
                            
                            if(self.ShouldStop(pDialog)):
                                return True                

                            #we have to compare the lists somehow
                            comparestring1 = str(episode.get("ParentIndexNumber")) + "-" + str(episode.get("IndexNumber"))
                            matchFound = False
                            if kodiEpisodes != None:
                                KodiItem = kodiEpisodes.get(comparestring1, None)
                                if(KodiItem != None): 
                                    matchFound = True
                            
                            progressAction = "Checking"
                            if not matchFound:
                                #no match so we have to create it
                                WriteKodiDB().addEpisodeToKodiLibrary(episode)
                                updateNeeded = True
                                progressAction = "Adding"
                                
                            if(self.ShouldStop(pDialog)):
                                return True                        
                            
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(total)) * 100))
                                pDialog.update(percentage, progressTitle, progressAction + " Episode: " + str(count))
                                count += 1    
                    
                    #initiate library update and wait for finish before processing any updates
                    if updateNeeded:
                        self.doKodiLibraryUpdate(False, pDialog)
                        updateNeeded = False
                    
                    #process updates
                    if(pDialog != None):
                        progressTitle = "Sync DB : Processing Episodes"
                        pDialog.update(0, progressTitle)
                        total = len(latestMBEpisodes) + 1
                        count = 1
                                
                    for episode in latestMBEpisodes:
                        if episode["SeriesId"] in allKodiTvShowsIds:
                            #only process tvshows that already exist in the db at incremental updates
                            kodiEpisodes = ReadKodiDB().getKodiEpisodes(episode["SeriesId"],True,True)
                            
                            if(self.ShouldStop(pDialog)):
                                return True                

                            #we have to compare the lists somehow
                            comparestring1 = str(episode.get("ParentIndexNumber")) + "-" + str(episode.get("IndexNumber"))

                            if kodiEpisodes != None:
                                KodiItem = kodiEpisodes.get(comparestring1, None)
                                if(KodiItem != None): 
                                    WriteKodiDB().updateEpisodeToKodiLibrary(episode, KodiItem)
                                        
                            if(self.ShouldStop(pDialog)):
                                return True                        

                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(total)) * 100))
                                pDialog.update(percentage, progressTitle, "Updating Episode: " + str(count))
                                count += 1    
                    
            
            # full sync --> Tv shows and Episodes
            if fullsync:
                allTVShows = list()
                allMB3EpisodeIds = list() #for use with deletions
                allKodiEpisodeIds = [] # for use with deletions

                tvShowData = ReadEmbyDB().getTVShows(True,True)
                allKodiIds = set(ReadKodiDB().getKodiTvShowsIds(True))
                updateNeeded = False
                
                if(self.ShouldStop(pDialog)):
                    return True            
                
                if (tvShowData == None):
                    return
                    
                if(pDialog != None):
                    progressTitle = "Sync DB : Processing TV Shows"
                    pDialog.update(0, progressTitle)
                    total = len(tvShowData) + 1
                    count = 1
                    
                for item in tvShowData:
                    if item.get('IsFolder'):
                        allTVShows.append(item["Id"])
                        progMessage = "Processing"
                        if item["Id"] not in allKodiIds:
                            WriteKodiDB().addTVShowToKodiLibrary(item)
                            updateNeeded = True
                            
                        if(self.ShouldStop(pDialog)):
                            return True
                            
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, progressTitle, "Adding Tv Show: " + str(count))
                            count += 1                        
                        
                #process episodes first before updating tvshows
                allEpisodes = list()
                
                showTotal = len(allTVShows)
                showCurrent = 1
                
                # do episode adds
                for tvshow in allTVShows:
                    
                    episodeData = ReadEmbyDB().getEpisodes(tvshow,True)
                    kodiEpisodes = ReadKodiDB().getKodiEpisodes(tvshow,True,True)
                    
                    if(self.ShouldStop(pDialog)):
                        return True                
                    
                    if(pDialog != None):
                        progressTitle = "Sync DB : Processing Tv Show " + str(showCurrent) + " of " + str(showTotal)
                        pDialog.update(0, progressTitle)
                        total = len(episodeData) + 1
                        count = 0         

                    #we have to compare the lists somehow
                    for item in episodeData:
                        comparestring1 = str(item.get("ParentIndexNumber")) + "-" + str(item.get("IndexNumber"))
                        matchFound = False
                        if kodiEpisodes != None:
                            KodiItem = kodiEpisodes.get(comparestring1, None)
                            if(KodiItem != None):
                                matchFound = True

                        progressAction = "Checking"
                        if not matchFound:
                            #no match so we have to create it
                            WriteKodiDB().addEpisodeToKodiLibrary(item)
                            updateNeeded = True
                            progressAction = "Adding"
                            
                        if(self.ShouldStop(pDialog)):
                            return True                        
                            
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, progressTitle, progressAction + " Episode: " + str(count))
                            count += 1
                            
                    showCurrent += 1
                    
                #initiate library update and wait for finish before processing any updates
                if updateNeeded:
                    if(pDialog != None):
                        pDialog.update(0, "Processing New Items", "Importing STRM Files")

                    if(pDialog != None and type(pDialog) == xbmcgui.DialogProgressBG):
                        pDialog.close()
                        
                    self.doKodiLibraryUpdate(False, pDialog)
                    updateNeeded = False
                    
                    if(pDialog != None and type(pDialog) == xbmcgui.DialogProgressBG):
                        pDialog.create('Sync DB', 'Sync DB')                      
                                      
                if(pDialog != None):
                    progressTitle = "Sync DB : Processing TV Shows"
                    pDialog.update(0, progressTitle, "")
                    total = len(allTVShows) + 1
                    count = 1                    
                
                #process updates at TV Show level
                allKodiTVShows = ReadKodiDB().getKodiTvShows(True)
                for item in tvShowData:
                    if item.get('IsFolder'):

                        kodishow = allKodiTVShows.get(item["Id"],None)
                        
                        if(kodishow != None):
                            WriteKodiDB().updateTVShowToKodiLibrary(item,kodishow)
                            
                        if(self.ShouldStop(pDialog)):
                            return True
                            
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, progressTitle, "Updating Tv Show: " + str(count))
                            count += 1                        

                # do episode updates
                showCurrent = 1
                for tvshow in allTVShows:
                    
                    episodeData = ReadEmbyDB().getEpisodes(tvshow,True)
                    kodiEpisodes = ReadKodiDB().getKodiEpisodes(tvshow,True,True)
                    
                    if(self.ShouldStop(pDialog)):
                        return True                
                    
                    if(pDialog != None):
                        progressTitle = "Sync DB : Processing Tv Show " + str(showCurrent) + " of " + str(showTotal)
                        pDialog.update(0, progressTitle)
                        total = len(episodeData) + 1
                        count = 0         

                    #we have to compare the lists somehow
                    for item in episodeData:
                        
                        #add episodeId to the list of all episodes for use later on the deletes
                        allMB3EpisodeIds.append(item["Id"])
                        
                        comparestring1 = str(item.get("ParentIndexNumber")) + "-" + str(item.get("IndexNumber"))
                        matchFound = False
                        if kodiEpisodes != None:
                            KodiItem = kodiEpisodes.get(comparestring1, None)
                            if(KodiItem != None):
                                WriteKodiDB().updateEpisodeToKodiLibrary(item, KodiItem)
                            
                        if(self.ShouldStop(pDialog)):
                            return True                        
                            
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, progressTitle, "Updating Episode: " + str(count))
                            count += 1
                    
                    
                    #add all kodi episodes to a list with episodes for use later on to delete episodes
                    #the mediabrowser ID is set as uniqueID in the NFO... for some reason this has key 'unknown' in the json response
                    show = ReadKodiDB().getKodiEpisodes(tvshow,False,False)
                    if show != None:
                        for episode in show:
                            dict = {'episodeid': str(episode["uniqueid"]["unknown"]),'tvshowid': tvshow}
                            allKodiEpisodeIds.append(dict)
                    
                    showCurrent += 1                  
                
                if(pDialog != None):
                    progressTitle = "Removing Deleted Items"
                    pDialog.update(0, progressTitle)
                
                if(self.ShouldStop(pDialog)):
                    return True            
                
                cleanNeeded = False
                
                # DELETES -- EPISODES
                # process any deletes only at fullsync
                allMB3EpisodeIds = set(allMB3EpisodeIds)
                for episode in allKodiEpisodeIds:
                    if episode.get('episodeid') not in allMB3EpisodeIds:
                        WriteKodiDB().deleteEpisodeFromKodiLibrary(episode.get('episodeid'),episode.get('tvshowid'))
                
                # DELETES -- TV SHOWS
                if fullsync:
                    allLocaldirs, filesTVShows = xbmcvfs.listdir(tvLibrary)
                    allMB3TVShows = set(allTVShows)
                    for dir in allLocaldirs:
                        if not dir in allMB3TVShows:
                            WriteKodiDB().deleteTVShowFromKodiLibrary(dir)
                            cleanneeded = True
            
                if(self.ShouldStop(pDialog)):
                    return True            
                
                #initiate library clean and wait for finish before processing any updates
                if cleanNeeded:
                    self.doKodiLibraryUpdate(True, pDialog)
          
            addon.setSetting("SyncFirstTVRunDone", "true")
            
        finally:
            if(pDialog != None):
                pDialog.close()
        
        return True
    
    def doKodiLibraryUpdate(self, clean, prog):
        #initiate library update and wait for finish before processing any updates
        if clean:
            xbmc.executebuiltin("CleanLibrary(video)")
        else:
            xbmc.executebuiltin("UpdateLibrary(video)")
        xbmc.sleep(1000)
        while (xbmc.getCondVisibility("Library.IsScanningVideo")):
            if(self.ShouldStop(prog)):
                return True
            xbmc.sleep(1000)
    
    def updatePlayCounts(self):
        #update all playcounts from MB3 to Kodi library
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        
        processMovies = True
        processTvShows = True
        
        try:
            enableProgress = False
            if addon.getSetting("enableProgressPlayCountSync") == 'true':
                enableProgress = True
                
            if(addon.getSetting("SyncFirstCountsRunDone") != 'true'):
                pDialog = xbmcgui.DialogProgress()
            elif(enableProgress):
                pDialog = xbmcgui.DialogProgressBG()
                
            if(pDialog != None):
                pDialog.create('Sync PlayCounts', 'Sync PlayCounts')        
        
            #process movies
            if processMovies:
                if(pDialog != None):
                    pDialog.update(0, "Processing Movies", "")
                    
                views = ReadEmbyDB().getCollections("movies")
                viewCount = len(views)
                viewCurrent = 1
                for view in views:
                    allMB3Movies = ReadEmbyDB().getMovies(view.get('id'), fullinfo = False, fullSync = True)
                    allKodiMovies = ReadKodiDB().getKodiMovies(False)
                    
                    if(self.ShouldStop(pDialog)):
                        return True
                            
                    if(allMB3Movies == None):
                        return False    
                    
                    if(allKodiMovies == None):
                        return False    
                        
                    if(pDialog != None):
                        progressTitle = "Sync PlayCounts: Processing " + view.get('title') + " " + str(viewCurrent) + " of " + str(viewCount)
                        pDialog.update(0, progressTitle)
                        totalCount = len(allMB3Movies) + 1
                        count = 1            
                
                    for item in allMB3Movies:
                        
                        if not item.get('IsFolder'):                           
                            kodiItem = allKodiMovies.get(item["Id"], None)
                            
                            userData = API().getUserData(item)
                            timeInfo = API().getTimeInfo(item)
                            
                            if kodiItem != None:
                                WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"movie")
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    WriteKodiDB().setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
                                
                            if(self.ShouldStop(pDialog)):
                                return True
                            
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(totalCount)) * 100))
                                pDialog.update(percentage, progressTitle, "Updating Movie: " + str(count))
                                count += 1   
                                
                    viewCurrent += 1
                    
            #process Tv shows
            if processTvShows:
                if(pDialog != None):
                    pDialog.update(0, "Processing TV Episodes", "")
                                
                tvshowData = ReadEmbyDB().getTVShows(fullinfo = False, fullSync = True)
                
                if(self.ShouldStop(pDialog)):
                    return True
                            
                if (tvshowData == None):
                    return False
                    
                showTotal = len(tvshowData)
                showCurrent = 1                    
                
                for item in tvshowData:
                    
                    episodeData = ReadEmbyDB().getEpisodes(item["Id"], False)
                    kodiEpisodes = ReadKodiDB().getKodiEpisodes(item["Id"],False,True)
                    
                    if (episodeData != None):
                        if(pDialog != None):
                            progressTitle = "Sync PlayCounts: Processing TV Show " + str(showCurrent) + " of " + str(showTotal)
                            pDialog.update(0, progressTitle)
                            totalCount = len(episodeData) + 1
                            count = 1                  
                    
                        for episode in episodeData:

                            kodiItem = None
                            comparestring1 = str(episode.get("ParentIndexNumber")) + "-" + str(episode.get("IndexNumber"))
                            matchFound = False
                            if kodiEpisodes != None:
                                kodiItem = kodiEpisodes.get(comparestring1, None)

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
                                    
                            if(self.ShouldStop(pDialog)):
                                return True
                            
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(totalCount)) * 100))
                                pDialog.update(percentage, progressTitle, "Updating Episode: " + str(count))
                                count += 1
                                
                        showCurrent += 1
                        
            addon.setSetting("SyncFirstCountsRunDone", "true")
            
        finally:
            if(pDialog != None):
                pDialog.close()            
        
        return True
    
    def updatePlayCount(self,itemID,type):
        #update playcount of the itemID from MB3 to Kodi library
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
        #process movie
        if type=='Movie':
            MB3Movie = ReadEmbyDB().getItem(itemID)
            kodiItem = ReadKodiDB().getKodiMovie(itemID)      
            if(self.ShouldStop(None)):
                return True
                            
            if(MB3Movie == None):
                return False    
                    
            if(kodiItem == None):
                return False               
                            
            userData=API().getUserData(MB3Movie)
            timeInfo = API().getTimeInfo(MB3Movie)
            if kodiItem != None:
                
                kodiresume = int(round(kodiItem['resume'].get("position")))
                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                total = int(round(float(timeInfo.get("TotalTime"))))*60
                if kodiresume != resume:
                    WriteKodiDB().setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
                #write property forced will refresh the item in the list so playcount change is immediately visible
                WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"movie",True)
            if(self.ShouldStop(None)):
                return True 
                    
        #process episode
        elif type=='Episode':
            if(self.ShouldStop(None)):
                return True                   
                    
            MB3Episode = ReadEmbyDB().getItem(itemID)
            kodiItem = ReadKodiDB().getKodiEpisodeByMbItem(MB3Episode["Id"], MB3Episode["SeriesId"])
            if (MB3Episode != None):
                userData=API().getUserData(MB3Episode)
                timeInfo = API().getTimeInfo(MB3Episode)
                if kodiItem != None:
                    kodiresume = int(round(kodiItem['resume'].get("position")))
                    resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                    total = int(round(float(timeInfo.get("TotalTime"))))*60
                    if kodiresume != resume:
                        WriteKodiDB().setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                    #write property forced will refresh the item in the list so playcount change is immediately visible
                    WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode",True)             
                if(self.ShouldStop(None)):
                    return True          
        
        return True
    
    def ShouldStop(self, prog):
        
        if(prog != None and type(prog) == xbmcgui.DialogProgress):
            if(prog.iscanceled() == True):
                return True
    
        if(xbmc.Player().isPlaying() or xbmc.abortRequested):
            return True
        else:
            return False

        
        
        