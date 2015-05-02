#################################################################################################
# ReadKodiDB
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import json
import os

import Utils as utils


#sleepval is used to throttle the calls to the xbmc json API
sleepVal = 15

class ReadKodiDB():   
       
   
    def getKodiMovies(self, connection, cursor):
        #returns all movies in Kodi db
        cursor.execute("SELECT kodi_id, emby_id, checksum FROM emby WHERE media_type='movie'")
        allmovies = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allmovies
        
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
        
