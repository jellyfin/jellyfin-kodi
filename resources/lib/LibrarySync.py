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
        
        #show the progress dialog
        pDialog = xbmcgui.DialogProgressBG()
        pDialog.create('Emby for Kodi', 'Performing full sync')
        
        #set some variable to check if this is the first run
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        

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
            self.MoviesFullSync(connection,cursor,pDialog)
            #sync Tvshows and episodes
            self.TvShowsFullSync(connection,cursor,pDialog)

            # set the install done setting
            if(syncInstallRunDone == False and completed):
                addon = xbmcaddon.Addon(id='plugin.video.emby') #force a new instance of the addon
                addon.setSetting("SyncInstallRunDone", "true")        
            
            # Force refresh the library
            xbmc.executebuiltin("UpdateLibrary(video)")
            xbmc.executebuiltin("Container.Refresh")
            xbmc.executebuiltin("Container.Update")
            
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
                    
                if not item.get('IsFolder'):                    
                    allEmbyMovieIds.append(item["Id"])
                    
                    if(pDialog != None):
                        progressTitle = "Processing " + view.get('title') + " (" + str(count) + " of " + str(total) + ")"
                        pDialog.update(0, "Emby for Kodi - Running Sync", progressTitle)
                        count = 1        
                    
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
                    
                if item.get('IsFolder') and item.get('RecursiveItemCount') != 0:                   
                    allEmbyTvShowIds.append(item["Id"])
                    
                    if(pDialog != None):
                        progressTitle = "Processing " + view.get('title') + " (" + str(count) + " of " + str(total) + ")"
                        pDialog.update(0, "Emby for Kodi - Running Sync", progressTitle)
                        count = 1        
                    
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
                        if kodiShow[2] != API().getChecksum(item):
                            WriteKodiDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                            
                    #### PROCESS EPISODES ######
                    self.EpisodesFullSync(connection,cursor,item["Id"], kodiId)
            
            #### TVSHOW: PROCESS DELETES #####
            allEmbyTvShowIds = set(allEmbyTvShowIds)
            for kodiId in allKodiTvShowIds:
                if not kodiId in allEmbyTvShowIds:
                    WINDOW.setProperty(kodiId,"deleted")
                    WriteKodiDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)

         
    def EpisodesFullSync(self,connection,cursor,embyShowId, kodiShowId):
        
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
                if kodiEpisode[2] != API().getChecksum(item):
                    WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
        
        #### EPISODES: PROCESS DELETES #####
        allEmbyEpisodeIds = set(allEmbyEpisodeIds)
        for kodiId in allKodiEpisodeIds:
            if (not kodiId in allEmbyEpisodeIds):
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
    

    def IncrementalSync(self, itemList):
        #this will only perform sync for items received by the websocket
        
        pDialog = xbmcgui.DialogProgressBG()
        pDialog.create('Emby for Kodi', 'Performing incremental sync...')
        
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        
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
                result = cursor.fetchall()
                if result:
                    kodi_show_id = result[0]
                else:
                    kodi_show_id = None
                
                if kodi_show_id:
                    WriteKodiDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodi_show_id, connection, cursor)
        
        
        cursor.close()
        if(pDialog != None):
            pDialog.close()
    
    def ShouldStop(self, prog):
        
        if(prog != None and type(prog) == xbmcgui.DialogProgress):
            if(prog.iscanceled() == True):
                return True
    
        if(xbmc.Player().isPlaying() or xbmc.abortRequested):
            return True

        if(WINDOW.getProperty("SyncDatabaseShouldStop") == "true"):
            return True

        return False

        
        
        