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
            
            #Add the special emby table
            if not startupDone:
                cursor.execute("CREATE TABLE IF NOT EXISTS emby(emby_id TEXT, kodi_id INTEGER, media_type TEXT, checksum TEXT, parent_id INTEGER)")
                connection.commit()
            
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
            
            for kodimovie in allKodiMovies:
                allKodiMovieIds.append(kodimovie[1])

            #### PROCESS ADDS AND UPDATES ###
            for item in allMB3Movies:
                    
                if not item.get('IsFolder'):                    
                    allEmbyMovieIds.append(item["Id"])
                    
                    kodiMovie = None
                    for kodimovie in allKodiMovies:
                        if kodimovie[1] == item["Id"]:
                            kodiMovie = kodimovie
                          
                    if kodiMovie == None:
                        WriteKodiDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        if kodiMovie[2] != API().getChecksum(item) or item["Id"] in itemList:
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
            
            for kodishow in allKodiTvShows:
                allKodiTvShowIds.append(kodishow[1])
            

            #### TVSHOW: PROCESS ADDS AND UPDATES ###
            for item in allEmbyTvShows:
                    
                if item.get('IsFolder') and item.get('RecursiveItemCount') != 0:                   
                    allEmbyTvShowIds.append(item["Id"])
                    
                    #build a list with all Id's and get the existing entry (if exists) in Kodi DB
                    kodiShow = None
                    for kodishow in allKodiTvShows:
                        if kodishow[1] == item["Id"]:
                            kodiShow = kodishow
                          
                    if kodiShow == None:
                        # Tv show doesn't exist in Kodi yet so proceed and add it
                        kodiId = WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        kodiId = kodishow[0]
                        # If there are changes to the item, perform a full sync of the item
                        if kodiShow[2] != API().getChecksum(item) or item["Id"] in itemList:
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
        
        for kodiepisode in allKodiEpisodes:
            allKodiEpisodeIds.append(kodiepisode[1])

        #### EPISODES: PROCESS ADDS AND UPDATES ###
        for item in allEmbyEpisodes:
                
            allEmbyEpisodeIds.append(item["Id"])
            
            #get the existing entry (if exists) in Kodi DB
            kodiEpisode = None
            for kodiepisode in allKodiEpisodes:
                if kodiepisode[1] == item["Id"]:
                    kodiEpisode = kodiepisode
                  
            if kodiEpisode == None:
                # Episode doesn't exist in Kodi yet so proceed and add it
                WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
            else:
                # If there are changes to the item, perform a full sync of the item
                if kodiEpisode[2] != API().getChecksum(item) or item["Id"] in itemList:
                    WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
        
        #### EPISODES: PROCESS DELETES #####
        allEmbyEpisodeIds = set(allEmbyEpisodeIds)
        for kodiId in allKodiEpisodeIds:
            if (not kodiId in allEmbyEpisodeIds):
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiDB().deleteEpisodeFromKodiLibrary(kodiId, connection, cursor)

    
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

        
        
        