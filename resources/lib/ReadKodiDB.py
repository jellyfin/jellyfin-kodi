#################################################################################################
# ReadKodiDB
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import json
import os

import Utils as utils

class ReadKodiDB():   
       
   
    def getKodiMovies(self, connection, cursor):
        #returns all movies in Kodi db
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='movie'")
        allmovies = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allmovies
    
    def getKodiMusicVideos(self, connection, cursor):
        #returns all musicvideos in Kodi db
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='musicvideo'")
        allvideos = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allvideos
    
    def getKodiTvShows(self, connection, cursor):
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='tvshow'")
        allshows = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allshows

    def getKodiEpisodes(self, connection, cursor, showid=None):
        
        if showid == None:
            cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type=?",("episode",))
        else:
            cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type=? AND parent_id=?",("episode", showid))
        
        allepisodes = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allepisodes
        
    def getEmbyIdByKodiId(self, id, type, connection=None, cursor=None):
        if not connection:
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            closeCon = True
        else:
            closeCon = False
        cursor.execute("SELECT emby_id FROM emby WHERE media_type=? AND kodi_id=?",(type,id))
        result = cursor.fetchone()
        if closeCon:
            connection.close()
        if result:
            return result[0]
        else:
            return None
            
    def getShowIdByEmbyId(self, id, connection=None, cursor=None):
        if not connection:
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            closeCon = True
        else:
            closeCon = False
        cursor.execute("SELECT parent_id FROM emby WHERE emby_id=?",(id,))
        result = cursor.fetchone()
        if closeCon:
            connection.close()
        if result:
            return result[0]
        else:
            return None    
            
    def getTypeByEmbyId(self, id, connection=None, cursor=None):
        if not connection:
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            closeCon = True
        else:
            closeCon = False
        cursor.execute("SELECT media_type FROM emby WHERE emby_id=?",(id,))
        result = cursor.fetchone()
        if closeCon:
            connection.close()
        if result:
            return result[0]
        else:
            return None            
            
    def getShowTotalCount(self, id, connection=None, cursor=None):
        if not connection:
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            closeCon = True
        else:
            closeCon = False
        command = "SELECT totalCount FROM tvshowcounts WHERE idShow=%s" % str(id)
        cursor.execute(command)
        result = cursor.fetchone()
        if closeCon:
            connection.close()
        if result:
            return result[0]
        else:
            return None    
            
    def getKodiMusicArtists(self, connection, cursor):
        #returns all artists in Kodi db
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='artist'")
        allartists = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allartists
    
    def getKodiMusicAlbums(self, connection, cursor):
        #returns all artists in Kodi db
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='album'")
        allalbums = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allalbums
        
    def getKodiMusicSongs(self, connection, cursor):
        #returns all songs in Kodi db
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='song'")
        allsongs = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allsongs    