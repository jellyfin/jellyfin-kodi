#################################################################################################
# ReadKodiDB
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import json

class ReadKodiDB():   
    def getKodiMovie(self, id):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties" : ["art", "rating", "thumbnail", "resume", "runtime", "year", "genre", "cast", "trailer", "country", "studio", "set", "imdbnumber", "mpaa", "tagline", "plotoutline","plot", "sorttitle", "director", "writer", "playcount", "tag", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movie = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']
                movie = movies[0]

        return movie
    
    def getKodiTVShow(self, id):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties": ["art", "genre", "plot", "mpaa", "cast", "studio", "sorttitle", "title", "originaltitle", "imdbnumber", "year", "premiered", "rating", "thumbnail", "playcount", "file", "fanart"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        tvshow = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                tvshow = tvshows[0]
        return tvshow
    
    def getKodiEpisodes(self, id):
        episodes = None
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties": ["sorttitle", "title", "originaltitle", "playcount", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        tvshow = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                tvshow = tvshows[0]
                
                json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["title", "playcount", "plot", "season", "episode", "showtitle", "file", "lastplayed", "rating", "resume", "art", "streamdetails", "firstaired", "runtime", "writer", "cast", "dateadded"], "sort": {"method": "episode"}}, "id": 1}' %tvshow['tvshowid'])
                jsonobject = json.loads(json_response.decode('utf-8','replace'))  
                episodes = None
                if(jsonobject.has_key('result')):
                    result = jsonobject['result']
                    if(result.has_key('episodes')):
                        episodes = result['episodes']
        return episodes
        
    def getKodiEpisodeByMbItem(self, MBitem):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "filter": {"operator": "is", "field": "title", "value": "' + MBitem.get("SeriesName").encode('utf-8') + '"} }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        episode = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                tvshow = tvshows[0]

                # find the episode by combination of season and episode
                json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["playcount","season", "resume", "episode"], "sort": {"method": "episode"}}, "id": 1}' %tvshow['tvshowid'])
                jsonobject = json.loads(json_response.decode('utf-8','replace'))  
                episodes = None
                if(jsonobject.has_key('result')):
                    result = jsonobject['result']
                    if(result.has_key('episodes')):
                        episodes = result['episodes']
                        
                        comparestring1 = str(MBitem.get("ParentIndexNumber")) + "-" + str(MBitem.get("IndexNumber"))
                        for item in episodes:
                            comparestring2 = str(item["season"]) + "-" + str(item["episode"])
                            if comparestring1 == comparestring2:
                                episode = item

        return episode
    
