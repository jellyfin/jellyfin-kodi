# -*- coding: utf-8 -*-

#################################################################################################
# ReadEmbyDB
#################################################################################################

from DownloadUtils import DownloadUtils


class ReadEmbyDB():

    doUtils = DownloadUtils()
    
    def getMovies(self, parentId, itemList = []):

        # Only get basic info for our sync-compares
        result = []
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&SortBy=SortName&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&ImageTypeLimit=1&format=json" % parentId
        # Process itemList if any
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result

    def getMusicVideos(self, itemList = []):
        
        # Only get basic info for our sync-compares
        result = []
        url = "{server}/mediabrowser/Users/{UserId}/items?&SortBy=SortName&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=MusicVideo&CollapseBoxSetItems=false&ImageTypeLimit=1&format=json"
        # Process itemList if any
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getMusicArtists(self, itemList = []):
        
        # Only get basic info for our sync-compares
        result = []
        url = "{server}/Artists?Recursive=true&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&UserId={UserId}&format=json"
        # Process itemList if any
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getMusicSongs(self, itemList = []):
        
        # Only get basic info for our sync-compares
        result = []
        url = "{server}/mediabrowser/Users/{UserId}/Items?Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=Audio&format=json"
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getMusicAlbums(self, itemList = []):
        
        # Only get basic info for our sync-compares
        result = []
        url = "{server}/mediabrowser/Users/{UserId}/Items?Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=MusicAlbum&format=json"
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))
        
        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else:
            tempresult = []
            # Only return valid albums - which have artists
            for item in result:
                if item['AlbumArtists']:
                    tempresult.append(item)
            result = tempresult

        return result
        
    def getItem(self, id):
        
        result = {}
        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1&Fields=Etag" % id
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata

        return result
    
    def getFullItem(self, id):
        
        result = {}
        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview" % id
        
        jsondata = self.doUtils.downloadUrl(url)     
        if jsondata:
            result = jsondata

        return result
    
    def getTvShows(self, parentId, itemList = []):
        
        # Only get basic info for our sync-compares
        result = []

        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&SortBy=SortName&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1" % parentId
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getTVShowSeasons(self, tvShowId):
        
        result = []
        url = "{server}/Shows/%s/Seasons?UserId={UserId}&format=json&ImageTypeLimit=1" % tvShowId
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getEpisodes(self, showId, itemList = []):
        
        result = []
        
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % showId
        if itemList:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getLatestEpisodes(self, fullinfo = False, itemList = []):
        
        result = [] 
        
        limitString = "Limit=20&SortBy=DateCreated&"
        if itemList: # if we want a certain list specify it
            limitString = "Ids=%s&" % ",".join(itemList)
        
        if fullinfo:
            url = "{server}/mediabrowser/Users/{UserId}/Items?%sIsVirtualUnaired=false&IsMissing=False&Fields=ParentId,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % limitString
        else:
            url = "{server}/mediabrowser/Users/{UserId}/Items?%sIsVirtualUnaired=false&IsMissing=False&Fields=ParentId,Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % limitString
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getCollections(self, type):
        # Build a list of the user views
        doUtils = self.doUtils
        collections = []

        url = "{server}/mediabrowser/Users/{UserId}/Items?Sortby=SortName&format=json"
        jsondata = doUtils.downloadUrl(url)

        try:
            result = jsondata['Items']
        except: pass
        else:
            for item in result:
                if item['RecursiveItemCount']:
                    name = item['Name']
                    itemtype = item.get('CollectionType', "movies")

                    if itemtype == type and name != "Collections":
                        collections.append({
                            'title': name,
                            'type': itemtype,
                            'id': item['Id']
                        })

        return collections
    
    def getBoxSets(self):
        
        result = []
        url = "{server}/mediabrowser/Users/{UserId}/Items?SortBy=SortName&IsVirtualUnaired=false&IsMissing=False&Fields=Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Ascending&IncludeItemTypes=BoxSet&format=json&ImageTypeLimit=1"
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result
    
    def getMoviesInBoxSet(self, boxsetId):
        
        result = []
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&Fields=ItemCounts,Etag&format=json&ImageTypeLimit=1" % boxsetId
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata['Items']

        return result


    # This is not being used.
    # To be removed?

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