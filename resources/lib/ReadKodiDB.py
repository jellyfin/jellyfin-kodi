#################################################################################################
# ReadKodiDB
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import json
import os

addon = xbmcaddon.Addon(id='plugin.video.emby')
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')
musicvideoLibrary = os.path.join(dataPath,'musicvideos')

#sleepval is used to throttle the calls to the xbmc json API
sleepVal = 15

class ReadKodiDB():   
    
    def getKodiMovie(self, id):
        #returns a single movie from Kodi db selected on MB item ID
        xbmc.sleep(sleepVal)
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "properties" : ["art", "rating", "thumbnail", "resume", "runtime", "year", "genre", "cast", "trailer", "country", "studio", "set", "imdbnumber", "mpaa", "tagline", "plotoutline","plot", "sorttitle", "director", "lastplayed", "writer", "playcount", "tag", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movie = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']
                movie = movies[0]
                for item in movies:
                    if item["imdbnumber"] == id:
                        movie = item
                        break
        return movie
    
    def getEmbyIdByKodiId(self, kodiid, type):
        #returns the emby id by search on kodi id
        xbmc.sleep(sleepVal)
        
        embyId = None
        
        if type == "movie":
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovieDetails", "params": { "movieid": %d, "properties" : ["imdbnumber","file"] }, "id": "libMovies"}' %kodiid)
        if type == "episode":
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodeDetails", "params": {"episodeid": %d, "properties": ["file","uniqueid"]}, "id": 1}' %kodiid)
        
        if json_response != None:
            jsonobject = json.loads(json_response.decode('utf-8','replace'))  
            if(jsonobject.has_key('result')):
                result = jsonobject['result']
                resulttype = type + "details"
                if(result.has_key(resulttype)):
                    item = result[resulttype]
                    if type == "movie":
                        if item.has_key('imdbnumber'):
                            embyId = item['imdbnumber']
                    if type == "episode":
                        if item.has_key('uniqueid'):
                            if item['uniqueid'].has_key('unknown'):
                                embyId = item["uniqueid"]["unknown"]

            return embyId
    
    def getKodiMovies(self,fullInfo = False):
        #returns all movies in Kodi db
        xbmc.sleep(sleepVal)
        if fullInfo:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "properties" : ["art", "rating", "thumbnail", "resume", "runtime", "year", "genre", "cast", "trailer", "country", "lastplayed", "studio", "set", "imdbnumber", "mpaa", "tagline", "plotoutline","plot", "sorttitle", "director", "writer", "playcount", "tag", "file"] }, "id": "libMovies"}')
        else:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "properties" : ["resume", "playcount", "imdbnumber", "lastplayed", "file"] }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movies = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']

        kodiMovieMap = None
        if(movies != None and len(movies) > 0):
            kodiMovieMap = {}
            for kodimovie in movies:
                key = kodimovie["imdbnumber"] #extract the id from the imdbnumber 
                kodiMovieMap[key] = kodimovie
                
        return kodiMovieMap
    
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
        
    def getKodiTvShows(self,fullInfo = False):
        #returns all tvshows in Kodi db inserted by MB
        xbmc.sleep(sleepVal)
        if fullInfo:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "properties": ["art", "genre", "plot", "mpaa", "cast", "studio", "sorttitle", "title", "originaltitle", "imdbnumber", "year", "premiered", "rating", "thumbnail", "playcount", "lastplayed", "file", "fanart"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        else:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "properties": ["sorttitle", "title", "playcount", "lastplayed", "imdbnumber", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        tvshows = None

        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']

        kodiShowMap = None
        if(tvshows != None and len(tvshows) > 0):
            kodiShowMap = {}
            for kodishow in tvshows:
                key = kodishow["imdbnumber"] #extract the id from the imdb number
                kodiShowMap[key] = kodishow
                
        return kodiShowMap
    
    def getKodiTVShow(self, id):
        xbmc.sleep(sleepVal)
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "properties": ["art", "genre", "plot", "mpaa", "cast", "studio", "sorttitle", "title", "originaltitle", "imdbnumber", "year", "lastplayed", "premiered", "rating", "thumbnail", "playcount", "file", "fanart"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
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
    
    def getKodiEpisodes(self, KodiTvShowId, fullInfo = True, returnmap = True):
        xbmc.sleep(sleepVal)
        episodes = None
        if fullInfo:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["title", "playcount", "plot", "season", "episode", "showtitle", "file", "lastplayed", "rating", "resume", "art", "streamdetails", "firstaired", "runtime", "writer", "cast", "dateadded","uniqueid"], "sort": {"method": "episode"}}, "id": 1}' %KodiTvShowId)
        else:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["title", "playcount", "season", "episode", "lastplayed", "resume","file","uniqueid"], "sort": {"method": "episode"}}, "id": 1}' %KodiTvShowId)
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        episodes = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('episodes')):
                episodes = result['episodes']
        if returnmap:                 
            episodeMap = None
            if(episodes != None):
                episodeMap = {}
                for KodiItem in episodes:
                    key = str(KodiItem["season"]) + "-" + str(KodiItem["episode"])
                    episodeMap[key] = KodiItem    
            return episodeMap
        else:
            return episodes
        
    def getKodiEpisodeByMbItem(self, episodeid, tvshowid):
        xbmc.sleep(sleepVal)
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
        
    def getKodiMusicVideo(self, id):
        #returns a single musicvideo from Kodi db selected on MB item ID
        xbmc.sleep(sleepVal)
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMusicVideos", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties" : ["art", "thumbnail", "resume", "runtime", "year", "genre", "studio", "artist", "album", "track","plot", "director", "playcount", "lastplayed", "tag", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMusicVideos"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        musicvideo = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('musicvideos')):
                musicvideos = result['musicvideos']
                musicvideo = musicvideos[0]

        return musicvideo
    
    def getKodiMusicVideos(self,fullInfo = False):
        #returns all musicvideos in Kodi db inserted by MB
        xbmc.sleep(sleepVal)
        if fullInfo:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMusicVideos", "params": { "filter": {"operator": "contains", "field": "path", "value": "plugin.video.emby"}, "properties" : ["art", "thumbnail", "resume", "runtime", "year", "genre", "studio", "artist", "album", "track", "lastplayed", "plot", "director", "playcount", "tag", "file"] }, "id": "libMusicVideos"}')
        else:
            json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMusicVideos", "params": { "filter": {"operator": "contains", "field": "path", "value": "plugin.video.emby"}, "properties" : ["resume", "playcount", "lastplayed", "file"] }, "id": "libMusicVideos"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        musicvideos = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('musicvideos')):
                musicvideos = result['musicvideos']

        kodiMusicVideoMap = None
        if(musicvideos != None and len(musicvideos) > 0):
            kodiMusicVideoMap = {}
            for kodivideo in musicvideos:
                key = kodivideo["file"][-37:-5] #extract the id from the file name
                kodiMusicVideoMap[key] = kodivideo
                
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
        