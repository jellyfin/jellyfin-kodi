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
            
            #pr = utils.startProfiling()
            self.MusicVideosSync(True)
            #utils.stopProfiling(pr, "MusicVideosSync(True)")
            
        if syncOption == "Incremental Sync":
            self.MoviesSync(False)
            self.TvShowsSync(False)
            self.MusicVideosSync(False)
        
        WINDOW.setProperty("startup", "done")
                        
        return True      
    
    def MoviesSync(self, fullsync=True):
        
        
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        startedSync = datetime.today()
        
        try:
            addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
            dbSyncIndication = addon.getSetting("dbSyncIndication")
            dbSyncFirstRun = addon.getSetting("SyncFirstMovieRunDone")
                
            if(dbSyncFirstRun != "true" or dbSyncIndication == "Dialog Progress"):
                pDialog = xbmcgui.DialogProgress()
            elif(dbSyncIndication == "BG Progress"):
                pDialog = xbmcgui.DialogProgressBG()
            
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            totalItemsAdded = 0
            totalItemsUpdated = 0
            totalItemsDeleted = 0
            
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
                            totalItemsAdded += 1
                        
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
                
                # process box sets - TODO cope with movies removed from a set
                boxsets = ReadEmbyDB().getBoxSets()
                for boxset in boxsets:
                    boxsetMovies = ReadEmbyDB().getMoviesInBoxSet(boxset["Id"])
                    WriteKodiDB().addBoxsetToKodiLibrary(boxset)
                    for boxsetMovie in boxsetMovies:
                        WriteKodiDB().updateBoxsetToKodiLibrary(boxsetMovie,boxset)
                
                #process updates
                allKodiMovies = ReadKodiDB().getKodiMovies(True)
                for item in allMB3Movies:
                    
                    if not item.get('IsFolder'):
                        item['Tag'] = []
                        item['Tag'].append(view.get('title'))
                        
                        kodimovie = allKodiMovies.get(item["Id"], None)
                        if(kodimovie != None):
                            #WriteKodiDB().updateMovieToKodiLibrary(item, kodimovie)
                            updated = WriteKodiDB().updateMovieToKodiLibrary_Batched(item, kodimovie)
                            if(updated):
                                totalItemsUpdated += 1
                        
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
                        WriteKodiDB().deleteMovieFromKodiLibrary(kodiId)
                        cleanNeeded = True
                        totalItemsDeleted += 1
            
            if(self.ShouldStop(pDialog)):
                return True            
            
            #initiate library clean and wait for finish before processing any updates
            if cleanNeeded:
                self.doKodiLibraryUpdate(True, pDialog)
        
            if(dbSyncFirstRun != "true"):
                addon = xbmcaddon.Addon(id='plugin.video.mb3sync') #force a new instance of the addon
                addon.setSetting("SyncFirstMovieRunDone", "true")
            
            # display notification if set up
            notificationString = ""
            if(totalItemsAdded > 0):
                notificationString += "Added:" + str(totalItemsAdded) + " "
            if(totalItemsUpdated > 0):
                notificationString += "Updated:" + str(totalItemsUpdated) + " "
            if(totalItemsDeleted > 0):
                notificationString += "Deleted:" + str(totalItemsDeleted) + " "
                
            timeTaken = datetime.today() - startedSync
            timeTakenString = str(int(timeTaken.seconds / 60)) + ":" + str(timeTaken.seconds % 60)
            utils.logMsg("Sync Movies", "Finished " + timeTakenString + " " + notificationString, 0)
            
            if(dbSyncIndication == "Notify OnChange" and notificationString != ""):
                notificationString = "(" + timeTakenString + ") " + notificationString
                xbmc.executebuiltin("XBMC.Notification(Movie Sync: " + notificationString + ",)")
            elif(dbSyncIndication == "Notify OnFinish"):
                if(notificationString == ""):
                    notificationString = "Done"
                notificationString = "(" + timeTakenString + ") " + notificationString
                xbmc.executebuiltin("XBMC.Notification(Movie Sync: " + notificationString + ",)")

        finally:
            if(pDialog != None):
                pDialog.close()
        
        return True
        
    def TvShowsSync(self, fullsync=True):

        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        startedSync = datetime.today()
        
        try:
            dbSyncIndication = addon.getSetting("dbSyncIndication")
            dbSyncFirstRun = addon.getSetting("SyncFirstTVRunDone")
                
            if(dbSyncFirstRun != "true" or dbSyncIndication == "Dialog Progress"):
                pDialog = xbmcgui.DialogProgress()
            elif(dbSyncIndication == "BG Progress"):
                pDialog = xbmcgui.DialogProgressBG()
                
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            totalItemsAdded = 0
            totalItemsUpdated = 0
            totalItemsDeleted = 0                
            
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
                                totalItemsAdded += 1
                                
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
                            totalItemsAdded += 1
                            
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
                    
                    if episodeData != None:
                        
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
                                totalItemsAdded += 1
                                
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
                            updated = WriteKodiDB().updateTVShowToKodiLibrary(item,kodishow)
                            if(updated):
                                totalItemsUpdated += 1
                            
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
                                updated = WriteKodiDB().updateEpisodeToKodiLibrary(item, KodiItem)
                                if(updated):
                                    totalItemsUpdated += 1                                
                            
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
                        cleanneeded = True
                        totalItemsDeleted += 1
                
                # DELETES -- TV SHOWS
                if fullsync:
                    allLocaldirs, filesTVShows = xbmcvfs.listdir(tvLibrary)
                    allMB3TVShows = set(allTVShows)
                    for dir in allLocaldirs:
                        if not dir in allMB3TVShows:
                            WriteKodiDB().deleteTVShowFromKodiLibrary(dir)
                            cleanneeded = True
                            totalItemsDeleted += 1
            
                if(self.ShouldStop(pDialog)):
                    return True            
                
                #initiate library clean and wait for finish before processing any updates
                if cleanNeeded:
                    self.doKodiLibraryUpdate(True, pDialog)
          
            if(dbSyncFirstRun != "true"):
                addon = xbmcaddon.Addon(id='plugin.video.mb3sync') #force a new instance of the addon
                addon.setSetting("SyncFirstTVRunDone", "true")          

            # display notification if set up
            notificationString = ""
            if(totalItemsAdded > 0):
                notificationString += "Added:" + str(totalItemsAdded) + " "
            if(totalItemsUpdated > 0):
                notificationString += "Updated:" + str(totalItemsUpdated) + " "
            if(totalItemsDeleted > 0):
                notificationString += "Deleted:" + str(totalItemsDeleted) + " "
                
            timeTaken = datetime.today() - startedSync
            timeTakenString = str(int(timeTaken.seconds / 60)) + ":" + str(timeTaken.seconds % 60)
            utils.logMsg("Sync Episodes", "Finished " + timeTakenString + " " + notificationString, 0)
            
            if(dbSyncIndication == "Notify OnChange" and notificationString != ""):
                notificationString = "(" + timeTakenString + ") " + notificationString
                xbmc.executebuiltin("XBMC.Notification(Episode Sync: " + notificationString + ",)")
            elif(dbSyncIndication == "Notify OnFinish"):
                if(notificationString == ""):
                    notificationString = "Done"
                notificationString = "(" + timeTakenString + ") " + notificationString
                xbmc.executebuiltin("XBMC.Notification(Episode Sync: " + notificationString + ",)")

        finally:
            if(pDialog != None):
                pDialog.close()
        
        return True
    
    def MusicVideosSync(self, fullsync=True):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        
        try:
            dbSyncIndication = addon.getSetting("dbSyncIndication")
            dbSyncFirstRun = addon.getSetting("SyncFirstMusicVideoRunDone")
                
            if(dbSyncFirstRun != "true" or dbSyncIndication == "Dialog Progress"):
                pDialog = xbmcgui.DialogProgress()
            elif(dbSyncIndication == "BG Progress"):
                pDialog = xbmcgui.DialogProgressBG()
            
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            allEmbyMusicVideoIds = list()

            progressTitle = ""
            
            updateNeeded = False
            
            #process new musicvideos
            allMB3MusicVideos = ReadEmbyDB().getMusicVideos(True, fullsync)
            allKodiIds = set(ReadKodiDB().getKodiMusicVideoIds(True))
        
            if(self.ShouldStop(pDialog)):
                return True            
        
            if(allMB3MusicVideos == None):
                return False
        
            if(pDialog != None):
                progressTitle = "Sync DB : Processing Musicvideos"
                pDialog.update(0, progressTitle)
                total = len(allMB3MusicVideos) + 1
                count = 1
            
            for item in allMB3MusicVideos:
                
                if not item.get('IsFolder'):
                    allEmbyMusicVideoIds.append(item["Id"])
                    
                    if item["Id"] not in allKodiIds:
                        WriteKodiDB().addMusicVideoToKodiLibrary(item)
                        updateNeeded = True
                    
                    if(self.ShouldStop(pDialog)):
                        return True
                
                    # update progress bar
                    if(pDialog != None):
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, progressTitle, "Adding Musicvideo: " + str(count))
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
                progressTitle = "Sync DB : Processing musicvideos"
                pDialog.update(0, progressTitle, "")
                total = len(allMB3MusicVideos) + 1
                count = 1                    
            
            #process updates
            allKodiMusicVideos = ReadKodiDB().getKodiMusicVideos(True)
            for item in allMB3MusicVideos:
                
                if not item.get('IsFolder'):

                    kodimusicvideo = allKodiMusicVideos.get(item["Id"], None)
                    if(kodimusicvideo != None):
                        #WriteKodiDB().updateMusicVideoToKodiLibrary(item, kodimusicvideo)
                        WriteKodiDB().updateMusicVideoToKodiLibrary_Batched(item, kodimusicvideo)
                    
                    if(self.ShouldStop(pDialog)):
                        return True
                
                    # update progress bar
                    if(pDialog != None):
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, progressTitle, "Updating MusicVideo: " + str(count))
                        count += 1

                
            if(pDialog != None):
                progressTitle = "Removing Deleted Items"
                pDialog.update(0, progressTitle, "")
            
            if(self.ShouldStop(pDialog)):
                return True            
            
            cleanNeeded = False
            
            # process any deletes only at fullsync
            if fullsync:
                allKodiIds = ReadKodiDB().getKodiMusicVideoIds(True)
                allEmbyMusicVideoIds = set(allEmbyMusicVideoIds)
                for kodiId in allKodiIds:
                    if not kodiId in allEmbyMusicVideoIds:
                        WriteKodiDB().deleteMusicVideoFromKodiLibrary(kodiId)
                        cleanNeeded = True
            
            if(self.ShouldStop(pDialog)):
                return True            
            
            #initiate library clean and wait for finish before processing any updates
            if cleanNeeded:
                self.doKodiLibraryUpdate(True, pDialog)
        
            if(dbSyncFirstRun != "true"):
                addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
                addon.setSetting("SyncFirstMusicVideoRunDone", "true")
            
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
        startedSync = datetime.today()
        processMovies = True
        processTvShows = True
        
        try:
            playCountSyncIndication = addon.getSetting("playCountSyncIndication")
            playCountSyncFirstRun = addon.getSetting("SyncFirstCountsRunDone")
                
            if(playCountSyncFirstRun != "true" or playCountSyncIndication == "Dialog Progress"):
                pDialog = xbmcgui.DialogProgress()
            elif(playCountSyncIndication == "BG Progress"):
                pDialog = xbmcgui.DialogProgressBG()
                
            if(pDialog != None):
                pDialog.create('Sync PlayCounts', 'Sync PlayCounts')        
        
            totalCountsUpdated = 0
            totalPositionsUpdated = 0
            
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
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    WriteKodiDB().setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
                                    totalPositionsUpdated += 1
                                updated = WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")), "movie")
                                updated = WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "movie")
                                if(updated):
                                    totalCountsUpdated += 1
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
                                WINDOW = xbmcgui.Window( 10000 )
                                WINDOW.setProperty("episodeid" + str(kodiItem['episodeid']), episode.get('Name') + ";;" + episode.get('Id'))
                                kodiresume = int(round(kodiItem['resume'].get("position")))
                                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                total = int(round(float(timeInfo.get("TotalTime"))))*60
                                if kodiresume != resume:
                                    WriteKodiDB().setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                                    totalPositionsUpdated += 1
                                
                                updated = WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode")
                                updated = WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "episode")
                                if(updated):
                                    totalCountsUpdated += 1    
                            if(self.ShouldStop(pDialog)):
                                return True
                            
                            # update progress bar
                            if(pDialog != None):
                                percentage = int(((float(count) / float(totalCount)) * 100))
                                pDialog.update(percentage, progressTitle, "Updating Episode: " + str(count))
                                count += 1
                                
                        showCurrent += 1
             
            if(playCountSyncFirstRun != "true"):
                addon = xbmcaddon.Addon(id='plugin.video.mb3sync')                  
                addon.setSetting("SyncFirstCountsRunDone", "true")
                
            # display notification if set up
            notificationString = ""
            if(totalPositionsUpdated > 0):
                notificationString += "Pos:" + str(totalPositionsUpdated) + " "
            if(totalCountsUpdated > 0):
                notificationString += "Counts:" + str(totalCountsUpdated) + " "
                
            timeTaken = datetime.today() - startedSync
            timeTakenString = str(int(timeTaken.seconds / 60)) + ":" + str(timeTaken.seconds % 60)
            utils.logMsg("Sync PlayCount", "Finished " + timeTakenString + " " + notificationString, 0)
            
            if(playCountSyncIndication == "Notify OnChange" and notificationString != ""):
                notificationString = "(" + timeTakenString + ") " + notificationString
                xbmc.executebuiltin("XBMC.Notification(PlayCount Sync: " + notificationString + ",)")
            elif(playCountSyncIndication == "Notify OnFinish"):
                if(notificationString == ""):
                    notificationString = "Done"
                notificationString = "(" + timeTakenString + ") " + notificationString
                xbmc.executebuiltin("XBMC.Notification(PlayCount Sync: " + notificationString + ",)")

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
                WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "movie")
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
                    WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "episode")                    
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

        
        
        