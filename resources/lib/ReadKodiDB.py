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
    
    def getKodiMovie(self, id):
        #returns a single movie from Kodi db selected on MB item ID
        xbmc.sleep(sleepVal)
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "properties" : ["art", "rating", "thumbnail", "fanart", "resume", "runtime", "year", "genre", "cast", "trailer", "country", "studio", "set", "imdbnumber", "mpaa", "tagline", "plotoutline","plot", "sorttitle", "director", "lastplayed", "writer", "playcount", "tag", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movie = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']
                movie = movies[0]
                for item in movies:
                    if id in item["file"]:
                        movie = item
                        break
        return movie
    
    def getEmbyIdByKodiId(self, kodiid, type):
        embyId = None
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        
        if type == "movie":
            cursor.execute("SELECT embyId as embyId FROM movie WHERE idMovie = ?",(kodiid,))
        if type == "episode":
            cursor.execute("SELECT embyId as embyId FROM episode WHERE idEpisode = ?",(kodiid,))
        if type == "musicvideo":
            cursor.execute("SELECT embyId as embyId FROM musicvideo WHERE idMVideo = ?",(kodiid,))
        if type == "tvshow":
            cursor.execute("SELECT embyId as embyId FROM tvshow WHERE idShow = ?",(kodiid,))
        
        result = cursor.fetchone()
        cursor.close()
        if result != None:
            embyId = result[0]

        return embyId
    
    def getKodiMovies(self, connection, cursor):
        #returns all movies in Kodi db
        cursor.execute("SELECT idMovie, embyId, c00 FROM movie")
        allmovies = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allmovies
    
    def getKodiMoviesIds(self,returnMB3Ids = False):
        # returns a list of movieIds or MB3 Id's from all movies currently in the Kodi library
        allKodiMovies = self.getKodiMovies(False)
        
        if(allKodiMovies == None):
            return list()
        
        if(returnMB3Ids):
            allKodiMovieIds = list(allKodiMovies.keys())
            return allKodiMovieIds
        else:
            allKodiMovieIds = list()
            for kodimovie in allKodiMovies.values():
                id = str(kodimovie["movieid"])
                allKodiMovieIds.append(id)
        
            return allKodiMovieIds
    
    def getKodiTvShowsIds(self,returnMB3Ids = False):
        # returns a list of tvshowIds or MB3 Id's from all tvshows currently in the Kodi library
        allKodiTvShows = self.getKodiTvShows(False)
        
        if allKodiTvShows == None:
            return list()
        
        if(returnMB3Ids):
            allKodiTvShowsIds = list(allKodiTvShows.keys())
            return allKodiTvShowsIds
        else:
            allKodiTvShowsIds = list()
            for kodishow in allKodiTvShows.values():
                id = str(kodishow["tvshowid"])
                allKodiTvShowsIds.append(id)
        
            return allKodiTvShowsIds
        
    def getKodiTvShows(self, connection, cursor):
        cursor.execute("SELECT idShow, embyId, c00 FROM tvshow")
        allshows = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allshows
    
    def getKodiTVShow(self, id):
        xbmc.sleep(sleepVal)
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "properties": ["art", "genre", "plot", "mpaa", "cast", "studio", "sorttitle", "title", "originaltitle", "imdbnumber", "year", "lastplayed", "premiered", "rating", "thumbnail", "playcount", "file", "fanart", "tag"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        tvshow = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                for show in tvshows:
                    if show["imdbnumber"] == id:
                        tvshow = show
                        break
        return tvshow
    
    def getKodiEpisodes(self, connection, cursor, showid):
        cursor.execute("SELECT idEpisode, embyId, c00 FROM episode WHERE idShow = ?", (showid,))
        allepisodes = cursor.fetchall()
        #this will return a list with tuples of all items returned from the database
        return allepisodes
        
    def getKodiEpisodeByMbItem(self, episodeid, tvshowid):
        episode = None
        tvshow = self.getKodiTVShow(tvshowid)
        
        if tvshow != None:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": ' + str(tvshow['tvshowid']) + ', "properties": ["playcount","season", "resume", "episode", "lastplayed", "uniqueid", "file"], "sort": {"method": "episode"}}, "id": 1}')
            jsonobject = json.loads(json_response.decode('utf-8','replace'))  
            if(jsonobject.has_key('result')):
                result = jsonobject['result']
                if(result.has_key('episodes')):
                    episodes = result['episodes']
                    for ep in episodes:
                        if ep["uniqueid"]["unknown"] == episodeid:
                            episode = ep
                            break

        return episode
        
    def getKodiEpisodeByMbItemEx(self, id):        
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        cursor.execute("SELECT idEpisode FROM episode WHERE c20 = ?", (id,))
        result = cursor.fetchone()
        kodiId = None
        if result != None:
            kodiId = result[0]
        cursor.close()
        
        episode = None
        if(kodiId != None):
            print "Kodi Episode ID : " + str(kodiId)
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodeDetails", "params": {"episodeid": %d, "properties": ["playcount", "season", "resume", "episode", "lastplayed", "uniqueid", "file"]}, "id": 1}' %kodiId)
            #json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodeDetails", "params": {"episodeid": ' + str(kodiId) + ', "properties": ["playcount", "season", "resume", "episode", "lastplayed", "uniqueid", "file"], "sort": {"method": "episode"}}, "id": 1}')
            jsonobject = json.loads(json_response.decode('utf-8','replace')) 
            print "Kodi_Item: " + str(jsonobject)
            if(jsonobject.has_key("result")):
                result = jsonobject["result"]
                if(result.has_key("episodedetails")):
                    episode = result["episodedetails"]
        
        return episode
        
    def getKodiMusicVideo(self, id):
        #returns a single musicvideo from Kodi db selected on MB item ID
        xbmc.sleep(sleepVal)
        #get the mediabrowser ID from DB
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        cursor.execute("SELECT idMVideo as musicvideoid FROM musicvideo WHERE c23 = ?",(id,))
        result = cursor.fetchone()
        musicvideoid = None
        if result != None:
            musicvideoid = result[0]
        cursor.close()
        
        musicvideo = None
        
        if musicvideoid != None:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMusicVideosDetails", "params": { "musicvideoid": ' + musicvideoid + ', "properties" : ["art", "thumbnail", "fanart", "resume", "runtime", "year", "genre", "studio", "artist", "album", "track","plot", "director", "playcount", "lastplayed", "tag", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMusicVideos"}')
            jsonobject = json.loads(json_response.decode('utf-8','replace'))  
            musicvideo = None
           
            if(jsonobject.has_key('result')):
                result = jsonobject['result']
                if(result.has_key('musicvideodetails')):
                    musicvideo = result['musicvideodetails']

        return musicvideo
    
    def getKodiMusicVideos(self,fullInfo = False):
        #returns all musicvideos in Kodi db inserted by MB
        xbmc.sleep(sleepVal)
        if fullInfo:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMusicVideos", "params": { "properties" : ["art", "thumbnail", "fanart", "resume", "runtime", "year", "genre", "studio", "artist", "album", "track", "lastplayed", "plot", "director", "playcount", "tag", "file"] }, "id": "libMusicVideos"}')
        else:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMusicVideos", "params": { "properties" : ["resume", "playcount", "lastplayed", "file", "track"] }, "id": "libMusicVideos"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        musicvideos = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('musicvideos')):
                musicvideos = result['musicvideos']

        kodiMusicVideoMap = None
        if(musicvideos != None and len(musicvideos) > 0):
            kodiMusicVideoMap = {}
            connection = utils.KodiSQL()
            cursor = connection.cursor()
            for kodivideo in musicvideos:
                cursor.execute("SELECT c23 as MBid FROM musicvideo WHERE idMVideo = ?",(kodivideo["musicvideoid"],))
                result = cursor.fetchone()
                if result != None:
                    key = result[0]
                    kodiMusicVideoMap[key] = kodivideo
            
            cursor.close()    
        return kodiMusicVideoMap
    
    def getKodiMusicVideoIds(self,returnMB3Ids = False):
        # returns a list of movieIds or MB3 Id's from all movies currently in the Kodi library
        allKodiMusicVideos = self.getKodiMusicVideos(False)
        
        if(allKodiMusicVideos == None):
            return list()
        
        if(returnMB3Ids):
            allKodiMusicVideoIds = list(allKodiMusicVideos.keys())
            return allKodiMusicVideoIds
        else:
            allKodiMusicVideoIds = list()
            for kodivideo in allKodiMusicVideos.values():
                id = str(kodivideo["musicvideoid"])
                allKodiMusicVideoIds.append(id)
        
            return allKodiMusicVideoIds
        