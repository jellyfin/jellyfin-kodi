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
from WriteKodiVideoDB import WriteKodiVideoDB
from WriteKodiMusicDB import WriteKodiMusicDB
from VideoNodes import VideoNodes

addondir = xbmc.translatePath(xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')

WINDOW = xbmcgui.Window( 10000 )

class LibrarySync():   
        
    def FullLibrarySync(self,manualRun=False):
        
        #set some variable to check if this is the first run
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        
        startupDone = WINDOW.getProperty("startup") == "done"
        syncInstallRunDone = addon.getSetting("SyncInstallRunDone") == "true"
        performMusicSync = addon.getSetting("enableMusicSync") == "true"
        dbSyncIndication = addon.getSetting("dbSyncIndication") == "true"
        WINDOW.setProperty("SyncDatabaseRunning", "true")
        
        
        #show the progress dialog
        pDialog = None
        if (syncInstallRunDone == False or dbSyncIndication or manualRun):
            pDialog = xbmcgui.DialogProgressBG()
            pDialog.create('Emby for Kodi', 'Performing full sync')
        
        if(WINDOW.getProperty("SyncDatabaseShouldStop") ==  "true"):
            utils.logMsg("Sync Database", "Can not start SyncDatabaseShouldStop=True", 0)
            return True

        try:
            completed = True
            

            ### BUILD VIDEO NODES LISTING ###
            VideoNodes().buildVideoNodesListing()
            
            ### PROCESS VIDEO LIBRARY ###
            
            #create the sql connection to video db
            connection = utils.KodiSQL("video")
            cursor = connection.cursor()
            
            #Add the special emby table
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
            
            #close sql connection
            cursor.close()
            
            ### PROCESS MUSIC LIBRARY ###
            if performMusicSync:
                #create the sql connection to music db
                connection = utils.KodiSQL("music")
                cursor = connection.cursor()
                
                #Add the special emby table
                cursor.execute("CREATE TABLE IF NOT EXISTS emby(emby_id TEXT, kodi_id INTEGER, media_type TEXT, checksum TEXT, parent_id INTEGER)")
                connection.commit()
                
                self.MusicFullSync(connection,cursor,pDialog)
                cursor.close()
            
            # set the install done setting
            if(syncInstallRunDone == False and completed):
                addon = xbmcaddon.Addon(id='plugin.video.emby') #force a new instance of the addon
                addon.setSetting("SyncInstallRunDone", "true")        
            
            # Commit all DB changes at once and Force refresh the library
            xbmc.executebuiltin("UpdateLibrary(video)")
            
            # set prop to show we have run for the first time
            WINDOW.setProperty("startup", "done")
            
            # tell any widgets to refresh because the content has changed
            WINDOW.setProperty("widgetreload", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            
        finally:
            WINDOW.setProperty("SyncDatabaseRunning", "false")
            utils.logMsg("Sync DB", "syncDatabase Exiting", 0)
            

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
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
                        count += 1        
                    
                    kodiMovie = None
                    for kodimovie in allKodiMovies:
                        if kodimovie[1] == item["Id"]:
                            kodiMovie = kodimovie
                          
                    if kodiMovie == None:
                        WriteKodiVideoDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        if kodiMovie[2] != API().getChecksum(item):
                            WriteKodiVideoDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
          
          
       
        #### PROCESS BOX SETS #####
        if(pDialog != None):
            utils.logMsg("Sync Movies", "BoxSet Sync Started", 1)
            boxsets = ReadEmbyDB().getBoxSets()
            
            total = len(boxsets) + 1
            count = 1
            for boxset in boxsets:
                progressTitle = "Processing BoxSets"+ " (" + str(count) + " of " + str(total) + ")"
                percentage = int(((float(count) / float(total)) * 100))
                pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
                count += 1
                if(self.ShouldStop()):
                    return False                
                boxsetMovies = ReadEmbyDB().getMoviesInBoxSet(boxset["Id"])
                WriteKodiVideoDB().addBoxsetToKodiLibrary(boxset,connection, cursor)
                    
                for boxsetMovie in boxsetMovies:
                    if(self.ShouldStop()):
                        return False
                    WriteKodiVideoDB().updateBoxsetToKodiLibrary(boxsetMovie,boxset, connection, cursor)
                        
            utils.logMsg("Sync Movies", "BoxSet Sync Finished", 1)    
            
        #### PROCESS DELETES #####
        allEmbyMovieIds = set(allEmbyMovieIds)
        for kodiId in allKodiMovieIds:
            if not kodiId in allEmbyMovieIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiVideoDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
                
        ### commit all changes to database ###
        connection.commit()

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
                    percentage = int(((float(count) / float(total)) * 100))
                    pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
                    count += 1        
                
                kodiVideo = None
                for kodivideo in allKodiMusicvideos:
                    if kodivideo[1] == item["Id"]:
                        kodiVideo = kodivideo
                      
                if kodiVideo == None:
                    WriteKodiVideoDB().addOrUpdateMusicVideoToKodiLibrary(item["Id"],connection, cursor)
                else:
                    if kodiVideo[2] != API().getChecksum(item):
                        WriteKodiVideoDB().addOrUpdateMusicVideoToKodiLibrary(item["Id"],connection, cursor)
            
        #### PROCESS DELETES #####
        allEmbyMusicvideoIds = set(allEmbyMusicvideoIds)
        for kodiId in allKodiMusicvideoIds:
            if not kodiId in allEmbyMusicvideoIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiVideoDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
                
        ### commit all changes to database ###
        connection.commit()
    
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
                    percentage = int(((float(count) / float(total)) * 100))
                    pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
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
                        WriteKodiVideoDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                    else:
                        # If there are changes to the item, perform a full sync of the item
                        if kodiShow[2] != API().getChecksum(item):
                            WriteKodiVideoDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                            
                    #### PROCESS EPISODES ######
                    self.EpisodesFullSync(connection,cursor,item["Id"])
            
        #### TVSHOW: PROCESS DELETES #####
        allEmbyTvShowIds = set(allEmbyTvShowIds)
        for kodiId in allKodiTvShowIds:
            if not kodiId in allEmbyTvShowIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiVideoDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
                
        ### commit all changes to database ###
        connection.commit()
         
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
                WriteKodiVideoDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
            else:
                # If there are changes to the item, perform a full sync of the item
                if kodiEpisode[2] != API().getChecksum(item):
                    WriteKodiVideoDB().addOrUpdateEpisodeToKodiLibrary(item["Id"], kodiShowId, connection, cursor)
        
        #### EPISODES: PROCESS DELETES #####
        allEmbyEpisodeIds = set(allEmbyEpisodeIds)
        for kodiId in allKodiEpisodeIds:
            if (not kodiId in allEmbyEpisodeIds):
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiVideoDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
                
    def MusicFullSync(self, connection,cursor, pDialog):

        self.ProcessMusicArtists(connection,cursor,pDialog)
        self.ProcessMusicAlbums(connection,cursor,pDialog)
        self.ProcessMusicSongs(connection,cursor,pDialog)
        
        ### commit all changes to database ###
        connection.commit()
    
    def ProcessMusicSongs(self,connection,cursor,pDialog):
               
        allKodiSongIds = list()
        allEmbySongIds = list()
        
        allEmbySongs = ReadEmbyDB().getMusicSongs()
        allKodiSongs = ReadKodiDB().getKodiMusicSongs(connection, cursor)
        
        for kodisong in allKodiSongs:
            allKodiSongIds.append(kodisong[1])
            
        total = len(allEmbySongs) + 1
        count = 1    
        
        #### PROCESS SONGS ADDS AND UPDATES ###
        for item in allEmbySongs:
            
            if (self.ShouldStop()):
                return False
                             
            allEmbySongIds.append(item["Id"])
            
            if(pDialog != None):
                progressTitle = "Processing Music Songs (" + str(count) + " of " + str(total) + ")"
                percentage = int(((float(count) / float(total)) * 100))
                pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
                count += 1        
            
            kodiSong = None
            for kodisong in allKodiSongs:
                if kodisong[1] == item["Id"]:
                    kodiSong = kodisong
                  
            if kodiSong == None:
                WriteKodiMusicDB().addOrUpdateSongToKodiLibrary(item["Id"],connection, cursor)
            else:
                if kodiSong[2] != API().getChecksum(item):
                    WriteKodiMusicDB().addOrUpdateSongToKodiLibrary(item["Id"],connection, cursor)
        
        #### PROCESS DELETES #####
        allEmbySongIds = set(allEmbySongIds)
        for kodiId in allKodiSongIds:
            if not kodiId in allEmbySongIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiMusicDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
        
    def ProcessMusicArtists(self,connection,cursor,pDialog):
               
        allKodiArtistIds = list()
        allEmbyArtistIds = list()
        
        allEmbyArtists = ReadEmbyDB().getMusicArtists()
        allKodiArtists = ReadKodiDB().getKodiMusicArtists(connection, cursor)
        
        for kodiartist in allKodiArtists:
            allKodiArtistIds.append(kodiartist[1])
            
        total = len(allEmbyArtists) + 1
        count = 1    
        
        #### PROCESS SONGS ADDS AND UPDATES ###
        for item in allEmbyArtists:
            
            if (self.ShouldStop()):
                return False
                             
            allEmbyArtistIds.append(item["Id"])
            
            if(pDialog != None):
                progressTitle = "Processing Music Artists (" + str(count) + " of " + str(total) + ")"
                percentage = int(((float(count) / float(total)) * 100))
                pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
                count += 1        
            
            kodiArtist = None
            for kodiartist in allKodiArtists:
                if kodiartist[1] == item["Id"]:
                    kodiArtist = kodiartist
                  
            if kodiArtist == None:
                WriteKodiMusicDB().addOrUpdateArtistToKodiLibrary(item["Id"],connection, cursor)
            else:
                if kodiArtist[2] != API().getChecksum(item):
                    WriteKodiMusicDB().addOrUpdateArtistToKodiLibrary(item["Id"],connection, cursor)
        
        #### PROCESS DELETES #####
        allEmbyArtistIds = set(allEmbyArtistIds)
        for kodiId in allKodiArtistIds:
            if not kodiId in allEmbyArtistIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiMusicDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
    
    def ProcessMusicAlbums(self,connection,cursor,pDialog):
               
        allKodiAlbumIds = list()
        allEmbyAlbumIds = list()
        
        allEmbyAlbums = ReadEmbyDB().getMusicAlbums()
        allKodiAlbums = ReadKodiDB().getKodiMusicAlbums(connection, cursor)
        
        for kodialbum in allKodiAlbums:
            allKodiAlbumIds.append(kodialbum[1])
            
        total = len(allEmbyAlbums) + 1
        count = 1    
        
        #### PROCESS SONGS ADDS AND UPDATES ###
        for item in allEmbyAlbums:
            
            if (self.ShouldStop()):
                return False
                             
            allEmbyAlbumIds.append(item["Id"])
            
            if(pDialog != None):
                progressTitle = "Processing Music Albums (" + str(count) + " of " + str(total) + ")"
                percentage = int(((float(count) / float(total)) * 100))
                pDialog.update(percentage, "Emby for Kodi - Running Sync", progressTitle)
                count += 1        
            
            kodiAlbum = None
            for kodialbum in allKodiAlbums:
                if kodialbum[1] == item["Id"]:
                    kodiAlbum = kodialbum
                  
            if kodiAlbum == None:
                WriteKodiMusicDB().addOrUpdateAlbumToKodiLibrary(item["Id"],connection, cursor)
            else:
                if kodiAlbum[2] != API().getChecksum(item):
                    WriteKodiMusicDB().addOrUpdateAlbumToKodiLibrary(item["Id"],connection, cursor)
        
        #### PROCESS DELETES #####
        allEmbyAlbumIds = set(allEmbyAlbumIds)
        for kodiId in allKodiAlbumIds:
            if not kodiId in allEmbyAlbumIds:
                WINDOW.setProperty(kodiId,"deleted")
                WriteKodiMusicDB().deleteItemFromKodiLibrary(kodiId, connection, cursor)
    
    def IncrementalSync(self, itemList):
        
        startupDone = WINDOW.getProperty("startup") == "done"
        
        #only perform incremental scan when full scan is completed 
        if startupDone:
        
            #this will only perform sync for items received by the websocket
            addon = xbmcaddon.Addon(id='plugin.video.emby')
            dbSyncIndication = addon.getSetting("dbSyncIndication") == "true"
            performMusicSync = addon.getSetting("enableMusicSync") == "true"
            WINDOW.setProperty("SyncDatabaseRunning", "true")
            
            #show the progress dialog
            if (dbSyncIndication and xbmc.Player().isPlaying() == False):
                xbmcgui.Dialog().notification('Emby for Kodi', 'Performing incremental sync...', "special://home/addons/plugin.video.emby/icon.png")
            
            connection = utils.KodiSQL("video")
            cursor = connection.cursor()
            
            try:
                #### PROCESS MOVIES ####
                views = ReadEmbyDB().getCollections("movies")
                for view in views:
                    allEmbyMovies = ReadEmbyDB().getMovies(view.get('id'), itemList)
                    for item in allEmbyMovies:
                            
                        if not item.get('IsFolder'):                    
                            WriteKodiVideoDB().addOrUpdateMovieToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
               
                
                #### PROCESS BOX SETS #####
                boxsets = ReadEmbyDB().getBoxSets()
               
                for boxset in boxsets:
                    boxsetMovies = ReadEmbyDB().getMoviesInBoxSet(boxset["Id"])
                    WriteKodiVideoDB().addBoxsetToKodiLibrary(boxset,connection, cursor)
                        
                    for boxsetMovie in boxsetMovies:
                        WriteKodiVideoDB().updateBoxsetToKodiLibrary(boxsetMovie,boxset, connection, cursor)      
                
                #### PROCESS TV SHOWS ####
                views = ReadEmbyDB().getCollections("tvshows")              
                for view in views:
                    allEmbyTvShows = ReadEmbyDB().getTvShows(view.get('id'),itemList)
                    for item in allEmbyTvShows:
                        if item.get('IsFolder') and item.get('RecursiveItemCount') != 0:                   
                            kodiId = WriteKodiVideoDB().addOrUpdateTvShowToKodiLibrary(item["Id"],connection, cursor, view.get('title'))
                
                
                #### PROCESS OTHERS BY THE ITEMLIST ######
                for item in itemList:
                        
                    MBitem = ReadEmbyDB().getItem(item)
                    
                    #### PROCESS EPISODES ######
                    if MBitem["Type"] == "Episode":

                        #get the tv show
                        cursor.execute("SELECT kodi_id FROM emby WHERE media_type='tvshow' AND emby_id=?", (MBitem["SeriesId"],))
                        result = cursor.fetchone()
                        if result:
                            kodi_show_id = result[0]
                        else:
                            kodi_show_id = None

                        if kodi_show_id:
                            WriteKodiVideoDB().addOrUpdateEpisodeToKodiLibrary(MBitem["Id"], kodi_show_id, connection, cursor)
                        else:
                            #tv show doesn't exist
                            #perform full tvshow sync instead so both the show and episodes get added
                            self.TvShowsFullSync(connection,cursor,None)

                    elif u"Season" in MBitem['Type']:

                        #get the tv show
                        cursor.execute("SELECT kodi_id FROM emby WHERE media_type='tvshow' AND emby_id=?", (MBitem["SeriesId"],))
                        result = cursor.fetchone()
                        if result:
                            kodi_show_id = result[0]
                            season = MBitem['IndexNumber']
                            # update season
                            WriteKodiVideoDB().updateSeasons(MBitem["SeriesId"], kodi_show_id, connection, cursor)
                    
                    #### PROCESS BOXSETS ######
                    elif MBitem["Type"] == "BoxSet":
                        boxsetMovies = ReadEmbyDB().getMoviesInBoxSet(boxset["Id"])
                        WriteKodiVideoDB().addBoxsetToKodiLibrary(boxset,connection, cursor)
                        
                        for boxsetMovie in boxsetMovies:
                            WriteKodiVideoDB().updateBoxsetToKodiLibrary(boxsetMovie,boxset, connection, cursor)

                    #### PROCESS MUSICVIDEOS ####
                    elif MBitem["Type"] == "MusicVideo":
                        if not MBitem.get('IsFolder'):                    
                            WriteKodiVideoDB().addOrUpdateMusicVideoToKodiLibrary(MBitem["Id"],connection, cursor)
                        
                ### commit all changes to database ###
                connection.commit()
                cursor.close()

                ### PROCESS MUSIC LIBRARY ###
                if performMusicSync:
                    connection = utils.KodiSQL("music")
                    cursor = connection.cursor()
                    for item in itemList:
                        MBitem = ReadEmbyDB().getItem(item)
                        if MBitem["Type"] == "MusicArtist":
                            WriteKodiMusicDB().addOrUpdateArtistToKodiLibrary(MBitem["Id"],connection, cursor)
                        if MBitem["Type"] == "MusicAlbum":
                            WriteKodiMusicDB().addOrUpdateAlbumToKodiLibrary(MBitem["Id"],connection, cursor)
                        if MBitem["Type"] == "Audio":
                            WriteKodiMusicDB().addOrUpdateSongToKodiLibrary(MBitem["Id"],connection, cursor)    
                    connection.commit()
                    cursor.close()

            finally:
                xbmc.executebuiltin("UpdateLibrary(video)")
                WINDOW.setProperty("SyncDatabaseRunning", "false")
                # tell any widgets to refresh because the content has changed
                WINDOW.setProperty("widgetreload", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

    def ShouldStop(self):
            
        if(xbmc.abortRequested):
            return True

        if(WINDOW.getProperty("SyncDatabaseShouldStop") == "true"):
            return True

        return False

        
        
        