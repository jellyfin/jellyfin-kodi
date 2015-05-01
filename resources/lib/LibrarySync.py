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
from itertools import chain
import urllib2
import os

from API import API
import Utils as utils
from DownloadUtils import DownloadUtils
from ReadEmbyDB import ReadEmbyDB
from ReadKodiDB import ReadKodiDB
from WriteKodiDB import WriteKodiDB

addondir = xbmc.translatePath(xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')

class LibrarySync():   
        
    def syncDatabase(self):
        
        #set some variable to check if this is the first run
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window( 10000 )

        startupDone = WINDOW.getProperty("startup") == "done"
        syncInstallRunDone = addon.getSetting("SyncInstallRunDone") == "true"
        WINDOW.setProperty("SyncDatabaseRunning", "true")
        
        if(WINDOW.getProperty("SyncDatabaseShouldStop") ==  "true"):
            utils.logMsg("Sync Database", "Can not start SyncDatabaseShouldStop=True", 0)
            return True

        try:
            completed = True
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            
            #TEMP --> add new columns
            try:
                cursor.execute("alter table movie ADD COLUMN 'embyId' TEXT")
                cursor.execute("alter table tvshow ADD COLUMN 'embyId' TEXT")
                cursor.execute("alter table episode ADD COLUMN 'embyId' TEXT")
                cursor.execute("alter table musicvideo ADD COLUMN 'embyId' TEXT")
                connection.commit()
            except: pass
            
            # sync movies
            self.MoviesSync(connection,cursor,True)
            #sync Tvshows and episodes
            self.TvShowsSync(connection,cursor,True)

            # set the install done setting
            if(syncInstallRunDone == False and completed):
                addon = xbmcaddon.Addon(id='plugin.video.emby') #force a new instance of the addon
                addon.setSetting("SyncInstallRunDone", "true")        
            
            # set prop to show we have run for the first time
            WINDOW.setProperty("startup", "done")
            
        finally:
            WINDOW.setProperty("SyncDatabaseRunning", "false")
            utils.logMsg("Sync DB", "syncDatabase Exiting", 0)
            cursor.close()
            
        return True      
      
    def MoviesSync(self,connection,cursor,installFirstRun,itemList = []):
        
        pDialog = xbmcgui.DialogProgressBG()
        pDialog.create('Sync DB', 'Sync Movies')
        
        views = ReadEmbyDB().getCollections("movies")
        
        allKodiMovieIds = list()
        allEmbyMovieIds = list()
        
        for view in views:
            
            allMB3Movies = ReadEmbyDB().getMovies(view.get('id'))
            allKodiMovies = ReadKodiDB().getKodiMovies(connection, cursor)

            #### PROCESS ADDS AND UPDATES ###
            for item in allMB3Movies:
                    
                if not item.get('IsFolder'):                    
                    allEmbyMovieIds.append(item["Id"])
                    
                    kodiMovie = None
                    for kodimovie in allKodiMovies:
                        allKodiMovieIds.append(kodimovie[1])
                        if kodimovie[1] == item["Id"]:
                            kodiMovie = kodimovie
                          
                    if kodiMovie == None:
                        allKodiMovieIds.append(item["Id"])
                        WriteKodiDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        # TODO --> compare with eTag
                        if kodiMovie[2] != item["Name"] or item["Id"] in itemList:
                            WriteKodiDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
            
            #### PROCESS DELETES #####
            allEmbyMovieIds = set(allEmbyMovieIds)
            for kodiId in allKodiMovieIds:
                if not kodiId in allEmbyMovieIds:
                    WINDOW.setProperty(kodiId,"deleted")
                    WriteKodiDB().deleteMovieFromKodiLibrary(kodiId, connection, cursor)

        if(pDialog != None):
            pDialog.close()
         
    def TvShowsSync(self,connection,cursor,installFirstRun,itemList = []):
        
        pDialog = xbmcgui.DialogProgressBG()
        pDialog.create('Sync DB', 'Sync TV Shows')
        
        views = ReadEmbyDB().getCollections("tvshows")
        
        allKodiTvShowIds = list()
        allEmbyTvShowIds = list()
        
        for view in views:
            
            allEmbyTvShows = ReadEmbyDB().getTvShows(view.get('id'))
            allKodiTvShows = ReadKodiDB().getKodiTvShows(connection, cursor)

            #### TVSHOW: PROCESS ADDS AND UPDATES ###
            for item in allEmbyTvShows:
                    
                if item.get('IsFolder') and item.get('RecursiveItemCount') != 0:                   
                    allEmbyTvShowIds.append(item["Id"])
                    
                    #build a list with all Id's and get the existing entry (if exists) in Kodi DB
                    kodiShow = None
                    for kodishow in allKodiTvShows:
                        allKodiTvShowIds.append(kodishow[1])
                        if kodishow[1] == item["Id"]:
                            kodiShow = kodishow
                          
                    if kodiShow == None:
                        # Tv show doesn't exist in Kodi yet so proceed and add it
                        allKodiTvShowIds.append(item["Id"])
                        kodiId = WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        kodiId = kodishow[0]
                        # If there are changes to the item, perform a full sync of the item
                        if kodiShow[2] != item["Name"] or item["Id"] in itemList:
                            WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                            
                    #### PROCESS EPISODES ######
                    self.EpisodesSync(connection,cursor,installFirstRun, item["Id"], kodiId, itemList)
            
            #### TVSHOW: PROCESS DELETES #####
            allEmbyTvShowIds = set(allEmbyTvShowIds)
            for kodiId in allKodiTvShowIds:
                if not kodiId in allEmbyTvShowIds:
                    WINDOW.setProperty(kodiId,"deleted")
                    WriteKodiDB().deleteTvShowFromKodiLibrary(kodiId, connection, cursor)

        if(pDialog != None):
            pDialog.close()
     
    
    def EpisodesSync(self,connection,cursor,installFirstRun, embyShowId, kodiShowId, itemList = []):
        
        WINDOW = xbmcgui.Window( 10000 )
        
        allKodiEpisodeIds = list()
        allEmbyEpisodeIds = list()
        
        allEmbyEpisodes = ReadEmbyDB().getEpisodes(embyShowId)
        allKodiEpisodes = ReadKodiDB().getKodiEpisodes(connection, cursor, kodiShowId)

        #### EPISODES: PROCESS ADDS AND UPDATES ###
        for item in allEmbyEpisodes:
                
            allEmbyEpisodeIds.append(item["Id"])
            
            #build a list with all Id's and get the existing entry (if exists) in Kodi DB
            kodiEpisode = None
            for kodiepisode in allKodiEpisodes:
                allKodiEpisodeIds.append(kodiepisode[1])
                if kodiepisode[1] == item["Id"]:
                    kodiEpisode = kodiepisode
                  
            if kodiEpisode == None:
                # Episode doesn't exist in Kodi yet so proceed and add it
                allKodiEpisodeIds.append(item["Id"])
                WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
            else:
                # If there are changes to the item, perform a full sync of the item
                if kodiEpisode[2] != item["Name"] or item["Id"] in itemList:
                    WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
        
        #### EPISODES: PROCESS DELETES #####
        allEmbyEpisodeIds = set(allEmbyEpisodeIds)
        print allEmbyEpisodeIds
        for kodiId in allKodiEpisodeIds:
            if not kodiId in allEmbyEpisodeIds:
                WINDOW.setProperty(kodiId,"deleted")
                print "deleting ???-->" + kodiId
                #WriteKodiDB().deleteEpisodeFromKodiLibrary(kodiId, connection, cursor)


    
    def MusicVideosSync(self, fullsync, installFirstRun,connection, cursor):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        
        try:
            dbSyncIndication = addon.getSetting("dbSyncIndication")
                
            if(installFirstRun or dbSyncIndication == "Dialog Progress"):
                pDialog = xbmcgui.DialogProgress()
            elif(dbSyncIndication == "BG Progress"):
                pDialog = xbmcgui.DialogProgressBG()
            
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            allEmbyMusicVideoIds = list()

            progressTitle = ""
            
            #process new musicvideos
            allMB3MusicVideos = ReadEmbyDB().getMusicVideos(True, fullsync)
            allKodiIds = set(ReadKodiDB().getKodiMusicVideoIds(True))
        
            if(self.ShouldStop(pDialog)):
                return False            
        
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
                        WriteKodiDB().addMusicVideoToKodiLibrary(item, connection, cursor)
                    
                    if(self.ShouldStop(pDialog)):
                        return False
                
                    # update progress bar
                    if(pDialog != None):
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, progressTitle, "Adding Musicvideo: " + str(count))
                        count += 1
            
            if(self.ShouldStop(pDialog)):
                return False

            if(pDialog != None):
                progressTitle = "Sync DB : Processing musicvideos"
                pDialog.update(0, progressTitle, "")
                total = len(allMB3MusicVideos) + 1
                count = 1                    
            
            #process updates
            allKodiMusicVideos = ReadKodiDB().getKodiMusicVideos(True)
            for item in allMB3MusicVideos:
                
                if not item.get('IsFolder'):
                    
                    if allKodiMusicVideos != None:
                        kodimusicvideo = allKodiMusicVideos.get(item["Id"], None)
                    else:
                        kodimusicvideo = None
                    
                    if(kodimusicvideo != None):
                        WriteKodiDB().updateMusicVideoToKodiLibrary_Batched(item, kodimusicvideo)
                    
                    if(self.ShouldStop(pDialog)):
                        return False
                
                    # update progress bar
                    if(pDialog != None):
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, progressTitle, "Updating MusicVideo: " + str(count))
                        count += 1

                
            if(pDialog != None):
                progressTitle = "Removing Deleted Items"
                pDialog.update(0, progressTitle, "")
            
            if(self.ShouldStop(pDialog)):
                return False            
            
            # process any deletes only at fullsync
            if fullsync:
                allKodiIds = ReadKodiDB().getKodiMusicVideoIds(True)
                allEmbyMusicVideoIds = set(allEmbyMusicVideoIds)
                for kodiId in allKodiIds:
                    if not kodiId in allEmbyMusicVideoIds:
                        WriteKodiDB().deleteMusicVideoFromKodiLibrary(kodiId)
            
            if(self.ShouldStop(pDialog)):
                return False            
            
        finally:
            if(pDialog != None):
                pDialog.close()
        
        return True  

    def updatePlayCounts(self):
        #update all playcounts from MB3 to Kodi library
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window( 10000 )
        pDialog = None
        startedSync = datetime.today()
        processMovies = True
        processTvShows = True
        
        if(WINDOW.getProperty("SyncDatabaseShouldStop") ==  "true"):
            utils.logMsg("Sync PlayCount", "Can not start SyncDatabaseShouldStop=True", 0)
            return True        
        
        if(WINDOW.getProperty("updatePlayCounts_Running") == "true"):
            utils.logMsg("Sync PlayCount", "updatePlayCounts Already Running", 0)
            return False
            
        WINDOW.setProperty("updatePlayCounts_Running", "true")
            
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
                        return False
                            
                    if(allMB3Movies != None and allKodiMovies != None):
                        
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
                                    updated |= WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "movie")
                                    if(updated):
                                        totalCountsUpdated += 1
                                        
                                if(self.ShouldStop(pDialog)):
                                    return False
                                
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
                views = ReadEmbyDB().getCollections("tvshows")
                viewCount = len(views)
                viewCurrent = 1
                progressTitle = ""
                for view in views:            
            
                    tvshowData = ReadEmbyDB().getTVShows(id = view.get('id'), fullinfo = False, fullSync = True)
                    
                    if(self.ShouldStop(pDialog)):
                        return False
                                
                    if (tvshowData != None):
                        
                        showTotal = len(tvshowData)
                        showCurrent = 1                    
                        
                        for item in tvshowData:
                            
                            episodeData = ReadEmbyDB().getEpisodes(item["Id"], False)
                            allKodiTVShows = ReadKodiDB().getKodiTvShows(False)
                            kodishow = allKodiTVShows.get(item["Id"],None)
                            if kodishow != None:
                                kodiEpisodes = ReadKodiDB().getKodiEpisodes(kodishow["tvshowid"],False,True)
                            else:
                                kodiEpisodes = None
                            
                            if (episodeData != None):
                                if(pDialog != None):
                                    progressTitle = "Sync PlayCounts: Processing TV Show " + str(showCurrent) + " of " + str(showTotal)
                                    pDialog.update(0, progressTitle)
                                    totalCount = len(episodeData) + 1
                                    count = 1                  
                            
                                for episode in episodeData:
    
                                    kodiItem = None
                                    matchFound = False
                                    if kodiEpisodes != None:
                                        kodiItem = kodiEpisodes.get(episode.get("Id"), None)
    
                                    userData=API().getUserData(episode)
                                    timeInfo = API().getTimeInfo(episode)
                                    
                                    
                                    if kodiItem != None:
                                        WINDOW = xbmcgui.Window( 10000 )
                                        WINDOW.setProperty("episodeid" + str(kodiItem['episodeid']), episode.get('Name') + ";;" + episode.get('Id'))
                                        WINDOW.setProperty(episode.get('Id'), "episode;;" + str(kodishow["tvshowid"]) + ";;" +str(kodiItem['episodeid']))
                                        kodiresume = int(round(kodiItem['resume'].get("position")))
                                        resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                                        total = int(round(float(timeInfo.get("TotalTime"))))*60
                                        if kodiresume != resume:
                                            WriteKodiDB().setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                                            totalPositionsUpdated += 1
                                        
                                        updated = WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode")
                                        updated |= WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "episode")
                                        if(updated):
                                            totalCountsUpdated += 1 
                                            
                                    if(self.ShouldStop(pDialog)):
                                        return False
                                    
                                    # update progress bar
                                    if(pDialog != None):
                                        percentage = int(((float(count) / float(totalCount)) * 100))
                                        pDialog.update(percentage, progressTitle, "Updating Episode: " + str(count))
                                        count += 1
                                        
                                showCurrent += 1
             
            if(playCountSyncFirstRun != "true"):
                addon = xbmcaddon.Addon(id='plugin.video.emby')                  
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
            WINDOW.setProperty("updatePlayCounts_Running", "false")
            if(pDialog != None):
                pDialog.close()            
        
        return True
    
    def updatePlayCount(self, itemID):
        #update playcount of the itemID from MB3 to Kodi library
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window( 10000 )
        
        embyItem = ReadEmbyDB().getItem(itemID)
        if(embyItem == None):
            return False
        
        type = embyItem.get("Type")
        
        #process movie
        if type == 'Movie':
            kodiItem = ReadKodiDB().getKodiMovie(itemID)     

            if(kodiItem == None):
                return False
                
            if(self.ShouldStop(None)):
                return False
 
            userData = API().getUserData(embyItem)
            timeInfo = API().getTimeInfo(embyItem)
                
            kodiresume = int(round(kodiItem['resume'].get("position")))
            resume = int(round(float(timeInfo.get("ResumeTime"))))*60
            total = int(round(float(timeInfo.get("TotalTime"))))*60
            if kodiresume != resume:
                WriteKodiDB().setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
            #write property forced will refresh the item in the list so playcount change is immediately visible
            WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"movie",True)
            WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "movie")
                
            if(self.ShouldStop(None)):
                return False 
                    
        #process episode
        elif type == 'Episode':
            if(self.ShouldStop(None)):
                return False                   
                    
            kodiItem = ReadKodiDB().getKodiEpisodeByMbItem(embyItem["Id"], embyItem["SeriesId"])

            userData = API().getUserData(embyItem)
            timeInfo = API().getTimeInfo(embyItem)
            
            if kodiItem != None:
                kodiresume = int(round(kodiItem['resume'].get("position")))
                resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                total = int(round(float(timeInfo.get("TotalTime"))))*60
                if kodiresume != resume:
                    WriteKodiDB().setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                #write property forced will refresh the item in the list so playcount change is immediately visible
                WriteKodiDB().updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode",True)
                WriteKodiDB().updateProperty(kodiItem,"lastplayed",userData.get("LastPlayedDate"), "episode")       
        
        return True
    
    def ShouldStop(self, prog):
        
        if(prog != None and type(prog) == xbmcgui.DialogProgress):
            if(prog.iscanceled() == True):
                return True
    
        if(xbmc.Player().isPlaying() or xbmc.abortRequested):
            return True

        WINDOW = xbmcgui.Window( 10000 )
        if(WINDOW.getProperty("SyncDatabaseShouldStop") == "true"):
            return True

        return False

        
        
        