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

WINDOW = xbmcgui.Window( 10000 )

class LibrarySync():   
        
    def FullLibrarySync(self):
        
        #set some variable to check if this is the first run
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        
        startupDone = WINDOW.getProperty("startup") == "done"
        syncInstallRunDone = addon.getSetting("SyncInstallRunDone") == "true"
        dbSyncIndication = addon.getSetting("dbSyncIndication") == "true"
        WINDOW.setProperty("SyncDatabaseRunning", "true")
        
        
        #show the progress dialog
        pDialog = None
        if (syncInstallRunDone == False or dbSyncIndication):
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create('Emby for Kodi', 'Performing full sync')
        
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
            self.MoviesFullSync(connection,cursor,pDialog)
            
            if (self.ShouldStop()):
                return False
            
            #sync Tvshows and episodes
            self.TvShowsFullSync(connection,cursor,pDialog)
            
            if (self.ShouldStop()):
                return False
                    
            # sync musicvideos
            self.MusicVideosFullSync(connection,cursor,pDialog)
            
            # set the install done setting
            if(syncInstallRunDone == False and completed):
                addon = xbmcaddon.Addon(id='plugin.video.emby') #force a new instance of the addon
                addon.setSetting("SyncInstallRunDone", "true")        
            
            # Force refresh the library
            xbmc.executebuiltin("UpdateLibrary(video)")
            
            # set prop to show we have run for the first time
            WINDOW.setProperty("startup", "done")
            
        finally:
            WINDOW.setProperty("SyncDatabaseRunning", "false")
            utils.logMsg("Sync DB", "syncDatabase Exiting", 0)
            cursor.close()

        if(pDialog != None):
            pDialog.close()
        
        return True      
      
    def MoviesFullSync(self,connection,cursor, pDialog):
               
        views = ReadEmbyDB().getCollections("movies")
        
        allKodiMovieIds = list()
        allEmbyMovieIds = list()
        
        for view in views:
            
            allEmbyMovies = ReadEmbyDB().getMovies(view.get('id'))
            allKodiMovies = ReadKodiDB().getKodiMovies(connection, cursor)
            
            for kodimovie in allKodiMovies:
                allKodiMovieIds.append(kodimovie[1])
            
            total = len(allEmbyMovies) + 1
            count = 1
            
            #### PROCESS ADDS AND UPDATES ###
            for item in allEmbyMovies:
                
                if (self.ShouldStop()):
                    return False
                
                if not item.get('IsFolder'):                    
                    allEmbyMovieIds.append(item["Id"])
                    
                    if(pDialog != None):
                        progressTitle = "Processing " + view.get('title') + " (" + str(count) + " of " + str(total) + ")"
                        pDialog.update(0, "Emby for Kodi - Running Sync", progressTitle)
                        count += 1        
                    
                    kodiMovie = None
                    for kodimovie in allKodiMovies:
                        if kodimovie[1] == item["Id"]:
                            kodiMovie = kodimovie
                          
                    if kodiMovie == None:
                        WriteKodiDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        if kodiMovie[2] != API().getChecksum(item):
                            WriteKodiDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
            
        #### PROCESS DELETES #####
        allEmbyMovieIds = set(allEmbyMovieIds)
        for kodiId in allKodiMovieIds:
            if not kodiId in allEmbyMovieIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)

    def MusicVideosFullSync(self,connection,cursor, pDialog):
               
        allKodiMusicvideoIds = list()
        allEmbyMusicvideoIds = list()
            
        allEmbyMusicvideos = ReadEmbyDB().getMusicVideos()
        allKodiMusicvideos = ReadKodiDB().getKodiMusicVideos(connection, cursor)
        
        for kodivideo in allKodiMusicvideos:
            allKodiMusicvideoIds.append(kodivideo[1])
        
        total = len(allEmbyMusicvideos) + 1
        count = 1
        
        #### PROCESS ADDS AND UPDATES ###
        for item in allEmbyMusicvideos:
            
            if (self.ShouldStop()):
                return False
            
            if not item.get('IsFolder'):                    
                allEmbyMusicvideoIds.append(item["Id"])
                
                if(pDialog != None):
                    progressTitle = "Processing MusicVideos (" + str(count) + " of " + str(total) + ")"
                    pDialog.update(0, "Emby for Kodi - Running Sync", progressTitle)
                    count += 1        
                
                kodiVideo = None
                for kodivideo in allKodiMusicvideos:
                    if kodivideo[1] == item["Id"]:
                        kodiVideo = kodivideo
                      
                if kodiVideo == None:
                    WriteKodiDB().addOrUpdateMusicVideoToKodiLibrary(item["Id"],connection, cursor)
                else:
                    if kodiVideo[2] != API().getChecksum(item):
                        WriteKodiDB().addOrUpdateMusicVideoToKodiLibrary(item["Id"],connection, cursor)
            
        #### PROCESS DELETES #####
        allEmbyMusicvideoIds = set(allEmbyMusicvideoIds)
        for kodiId in allKodiMusicvideoIds:
            if not kodiId in allEmbyMusicvideoIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
    
    def TvShowsFullSync(self,connection,cursor,pDialog):
               
        views = ReadEmbyDB().getCollections("tvshows")
        
        allKodiTvShowIds = list()
        allEmbyTvShowIds = list()
                
        for view in views:
            
            allEmbyTvShows = ReadEmbyDB().getTvShows(view.get('id'))
            allKodiTvShows = ReadKodiDB().getKodiTvShows(connection, cursor)
            
            total = len(allEmbyTvShows) + 1
            count = 1
            
            for kodishow in allKodiTvShows:
                allKodiTvShowIds.append(kodishow[1])
            

            #### TVSHOW: PROCESS ADDS AND UPDATES ###
            for item in allEmbyTvShows:
                
                if (self.ShouldStop()):
                    return False
                
                if(pDialog != None):
                    progressTitle = "Processing " + view.get('title') + " (" + str(count) + " of " + str(total) + ")"
                    pDialog.update(0, "Emby for Kodi - Running Sync", progressTitle)
                    count += 1                   

                if item.get('IsFolder') and item.get('RecursiveItemCount') != 0:                   
                    allEmbyTvShowIds.append(item["Id"])
                    
                    #build a list with all Id's and get the existing entry (if exists) in Kodi DB
                    kodiShow = None
                    for kodishow in allKodiTvShows:
                        if kodishow[1] == item["Id"]:
                            kodiShow = kodishow
                          
                    if kodiShow == None:
                        # Tv show doesn't exist in Kodi yet so proceed and add it
                        WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        # If there are changes to the item, perform a full sync of the item
                        if kodiShow[2] != API().getChecksum(item):
                            WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                            
                    #### PROCESS EPISODES ######
                    self.EpisodesFullSync(connection,cursor,item["Id"])
            
        #### TVSHOW: PROCESS DELETES #####
        allEmbyTvShowIds = set(allEmbyTvShowIds)
        for kodiId in allKodiTvShowIds:
            if not kodiId in allEmbyTvShowIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
         
    def EpisodesFullSync(self,connection,cursor,showId):
        
        WINDOW = xbmcgui.Window( 10000 )
        
        allKodiEpisodeIds = list()
        allEmbyEpisodeIds = list()
        
        #get the kodi parent id
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id=?",(showId,))
        kodiShowId = cursor.fetchone()[0]
        
        allEmbyEpisodes = ReadEmbyDB().getEpisodes(showId)
        allKodiEpisodes = ReadKodiDB().getKodiEpisodes(connection, cursor, kodiShowId)
        
        for kodiepisode in allKodiEpisodes:
            allKodiEpisodeIds.append(kodiepisode[1])

        #### EPISODES: PROCESS ADDS AND UPDATES ###
        for item in allEmbyEpisodes:
            
            if (self.ShouldStop()):
                    return False    
            
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
                if kodiEpisode[2] != API().getChecksum(item):
                    print "previous checksum--> " + kodiEpisode[2]
                    print "new checksum--> " + API().getChecksum(item)
                    WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
        
        #### EPISODES: PROCESS DELETES #####
        allEmbyEpisodeIds = set(allEmbyEpisodeIds)
        for kodiId in allKodiEpisodeIds:
            if (not kodiId in allEmbyEpisodeIds):
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
    
    def IncrementalSync(self, itemList):
        #this will only perform sync for items received by the websocket
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        dbSyncIndication = addon.getSetting("dbSyncIndication") == "true"
        WINDOW.setProperty("SyncDatabaseRunning", "true")
        
        #show the progress dialog
        pDialog = None
        if (dbSyncIndication):
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create('Emby for Kodi', 'Performing incremental sync...')
        
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        
        try:
            #### PROCESS MOVIES ####
            views = ReadEmbyDB().getCollections("movies")
            for view in views:
                allEmbyMovies = ReadEmbyDB().getMovies(view.get('id'), itemList)
                for item in allEmbyMovies:
                        
                    if not item.get('IsFolder'):                    
                        WriteKodiDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                        
            #### PROCESS TV SHOWS ####
            views = ReadEmbyDB().getCollections("tvshows")              
            for view in views:
                allEmbyTvShows = ReadEmbyDB().getTvShows(view.get('id'),itemList)
                for item in allEmbyTvShows:
                    if item.get('IsFolder') and item.get('RecursiveItemCount') != 0:                   
                        kodiId = WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                        
            #### PROCESS EPISODES ######
            for item in itemList:
                    
                MBitem = ReadEmbyDB().getItem(item)
                if MBitem["Type"] == "Episode":

                    #get the tv show
                    cursor.execute("SELECT kodi_id FROM emby WHERE media_type='tvshow' AND emby_id=?", (MBitem["SeriesId"],))
                    result = cursor.fetchone()
                    if result:
                        kodi_show_id = result[0]
                    else:
                        kodi_show_id = None

                    if kodi_show_id:
                        WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(MBitem["Id"], kodi_show_id, connection, cursor)
        
            #### PROCESS MUSICVIDEOS ####
            allEmbyMusicvideos = ReadEmbyDB().getMusicVideos(itemList)
            for item in allEmbyMusicvideos:
                if not item.get('IsFolder'):                    
                    WriteKodiDB().addOrUpdateMusicVideoToKodiLibrary(item["Id"],connection, cursor)
        
        finally:
            cursor.close()
            xbmc.executebuiltin("UpdateLibrary(video)")
            WINDOW.setProperty("SyncDatabaseRunning", "false")
        
        #close the progress dialog
        if(pDialog != None):
            pDialog.close()
    
    def ShouldStop(self):
            
        if(xbmc.abortRequested):
            return True

        if(WINDOW.getProperty("SyncDatabaseShouldStop") == "true"):
            return True

        return False

        
        
        