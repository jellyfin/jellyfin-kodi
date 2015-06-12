#################################################################################################
# ReadEmbyDB
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon



from DownloadUtils import DownloadUtils

addon = xbmcaddon.Addon(id='plugin.video.emby')

class ReadEmbyDB():   
    
    def getMovies(self, id, itemList = []):
        
        result = []
        doUtils = DownloadUtils()
        
        #only get basic info for our sync-compares
        sortstring = "&SortBy=SortName"
        url = "{server}/mediabrowser/Users/{UserId}/items?ParentId=%s%s&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1" % (id, sortstring)

        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
            
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult
            
        return result

    def getMusicVideos(self, itemList = []):
        
        result = []
        doUtils = DownloadUtils()

        #only get basic info for our sync-compares
        sortstring = "&SortBy=SortName"
        url = "{server}/mediabrowser/Users/{UserId}/items?%s&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=MusicVideo&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1" % sortstring
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
            
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult

        return result
    
    def getMusicArtists(self, itemList = []):
        
        result = []
        doUtils = DownloadUtils()

        #only get basic info for our sync-compares
        url = "{server}/Artists?Recursive=true&Fields=Etag,CumulativeRunTimeTicks&UserId={UserId}&format=json"
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
                       
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult

        return result
    
    def getMusicSongs(self, itemList = []):
        
        result = []
        doUtils = DownloadUtils()

        #only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/Items?Fields=Name,CumulativeRunTimeTicks,Etag&Recursive=true&IncludeItemTypes=Audio&format=json"
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
            
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult

        return result
    
    def getMusicAlbums(self, itemList = []):
        
        result = []
        doUtils = DownloadUtils()

        #only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/Items?Fields=Name,CumulativeRunTimeTicks,Etag&Recursive=true&IncludeItemTypes=MusicAlbum&format=json"
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
            
            #only return valid albums - which have artists
            tempresult = []
            for item in result:
                if item["AlbumArtists"]:
                    tempresult.append(item)
            
            result = tempresult

            
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult

        return result
        
    def getItem(self, id):
        
        result = None
        doUtils = DownloadUtils()

        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1&Fields=Etag" % id
        
        jsonData = doUtils.downloadUrl(url)     
        if (jsonData != ""):
            result = jsonData

        return result
    
    def getFullItem(self, id):
        
        result = None
        doUtils = DownloadUtils()

        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview" % id
        
        jsonData = doUtils.downloadUrl(url)     
        if (jsonData != ""):
            result = jsonData

        return result
    
    def getTvShows(self, id, itemList = []):
        
        result = []
        doUtils = DownloadUtils()
        
        #only get basic info for our sync-compares
        sortstring = "&SortBy=SortName"
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s%s&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1" % (id, sortstring)
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
            
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult

        return result
    
    def getTVShowSeasons(self, tvShowId):
        
        result = []
        doUtils = DownloadUtils()

        url = "{server}/Shows/%s/Seasons?UserId={UserId}&format=json&ImageTypeLimit=1" % tvShowId
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']

        return result
    
    def getEpisodes(self, showId, itemList = []):
        
        result = []
        doUtils = DownloadUtils()  
        
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % showId
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
            
        # Work around to only return items from the given list
        if (result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if (item[u'Id'] in itemList):
                    newResult.append(item)
            result = newResult
                
        return result
    
    def getLatestEpisodes(self, fullinfo = False, itemList = []):
        
        result = []
        doUtils = DownloadUtils() 
        
        limitString = "Limit=20&SortBy=DateCreated&"
        if(len(itemList) > 0): # if we want a certain list specify it
            limitString = "Ids=" + ",".join(itemList) + "&"
        
        if fullinfo:
            url = "{server}/mediabrowser/Users/{UserId}/Items?%sIsVirtualUnaired=false&IsMissing=False&Fields=ParentId,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % limitString
        else:
            url = "{server}/mediabrowser/Users/{UserId}/Items?%sIsVirtualUnaired=false&IsMissing=False&Fields=ParentId,Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % limitString
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']
                
        return result
    
    def getCollections(self, type):
        #Build a list of the user views
        doUtils = DownloadUtils()
        
        try:
            url = "{server}/mediabrowser/Users/{UserId}/Items/Root?format=json"
            result = doUtils.downloadUrl(url)
        except Exception, msg:
            error = "Can't connect: %s" % msg
            xbmc.log(error)
            return []
        
        if (result == ""):
            return []

        parentid = result[u'Id']
        
        url = "{server}/mediabrowser/Users/{UserId}/items?ParentId=%s&Sortby=SortName&format=json" % parentid
        result = doUtils.downloadUrl(url)
        collections=[]
        
        if (result == ""):
            return []
        
        result = result[u'Items']
        
        for item in result:
            if (item[u'RecursiveItemCount'] != 0):
                Name = item[u'Name']
                if u'CollectionType' not in item:
                    itemtype = "movies" # User may not have declared the type
                else:
                    itemtype = item[u'CollectionType']
                    
                if itemtype == type and Name != "Collections":
                    collections.append({'title': Name,
                                        'type' : itemtype,
                                        'id'   : item[u'Id']})
        return collections
    
    def getViewCollections(self, type):
        #Build a list of the user views
        doUtils = DownloadUtils()

        viewsUrl = "{server}/mediabrowser/Users/{UserId}/Views?format=json&ImageTypeLimit=1"
        result = doUtils.downloadUrl(viewsUrl)
        collections=[]
        
        if (result == ""):
            return []
            
        result = result[u'Items']

        for view in result:
            if (view[u'Type'] == 'UserView'): # Need to grab the real main node
                newViewsUrl = "{server}/mediabrowser/Users/{UserId}/items?ParentId=%s&SortBy=SortName&SortOrder=Ascending&format=json&ImageTypeLimit=1" % view[u'Id']
                newViews = doUtils.downloadUrl(newViewsUrl)
                if (result == ""):
                    return []
                newViews = newViews[u'Items']
                for newView in newViews:
                    # There are multiple nodes in here like 'Latest', 'NextUp' - below we grab the full node.
                    if newView[u'CollectionType'] != None:
                        if newView[u'CollectionType'] == "MovieMovies" or newView[u'CollectionType'] == "TvShowSeries":
                            view=newView
            if (view[u'ChildCount'] != 0):
                Name = view[u'Name'] 
                
            total = str(view[u'ChildCount'])
            try:
                itemtype = view[u'CollectionType']
            except:
                itemtype = "movies"
            if itemtype == "MovieMovies":
                itemtype = "movies"
            if itemtype == "TvShowSeries":
                itemtype = "tvshows"
            if itemtype == type:
                collections.append( {'title'      : Name,
                                     'type'           : type,
                                     'id'             : view[u'Id']})
        return collections
    
    def getBoxSets(self):
        
        result = []
        doUtils = DownloadUtils()  
        
        url = "{server}/mediabrowser/Users/{UserId}/Items?SortBy=SortName&IsVirtualUnaired=false&IsMissing=False&Fields=Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Ascending&IncludeItemTypes=BoxSet&format=json&ImageTypeLimit=1"
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']

        return result
    
    def getMoviesInBoxSet(self,boxsetId):
        
        result = []
        doUtils = DownloadUtils()
        
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&Fields=ItemCounts,Etag&format=json&ImageTypeLimit=1" % boxsetId
        
        jsonData = doUtils.downloadUrl(url)
        if (jsonData == ""):
            return result

        if (jsonData[u'Items'] != ""):
            result = jsonData[u'Items']

        return result
