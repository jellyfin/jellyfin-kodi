# -*- coding: utf-8 -*-

#################################################################################################
# ReadEmbyDB
#################################################################################################

from DownloadUtils import DownloadUtils


class ReadEmbyDB():

    doUtils = DownloadUtils()
    urllimit = 50

    def filterbyId(self, result, itemList = []):

        newResult = []
        for item in result:
            if item['Id'] in itemList:
                newResult.append(item)

        return newResult
    
    def getMovies(self, parentId, itemList = []):
        
        result = []
        lenlist = len(itemList) < self.urllimit
        # Only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&SortBy=SortName&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&ImageTypeLimit=1&format=json" % parentId
        if itemList and lenlist:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else: # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

        return result

    def getMusicVideos(self, itemList = []):
        
        result = []
        lenlist = len(itemList) < self.urllimit
        # Only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/items?&SortBy=SortName&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=MusicVideo&CollapseBoxSetItems=false&ImageTypeLimit=1&format=json"
        if itemList and lenlist:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else: # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

        return result
    
    def getMusicArtists(self, itemList = []):
        
        result = []
        lenlist = len(itemList) < self.urllimit
        # Only get basic info for our sync-compares
        url = "{server}/Artists?Recursive=true&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&UserId={UserId}&format=json"
        if itemList and lenlist:
            url = "%s&Ids=%s" % (url, ",".join(itemList))
        
        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else: # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

        return result

    def getMusicArtistsTotal(self):

        result = []

        url = "{server}/Artists?Limit=1&Recursive=true&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&UserId={UserId}&format=json"
        jsondata = self.doUtils.downloadUrl(url)

        total = jsondata['TotalRecordCount']
        index = 1
        jump = 200

        while index < total:
            url = "{server}/Artists?StartIndex=%s&Limit=%s&Recursive=true&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&UserId={UserId}&format=json" % (index, jump)
            jsondata = self.doUtils.downloadUrl(url)
            result.extend(jsondata['Items'])
            index += jump

        return result
    
    def getMusicSongs(self, itemList = []):
        
        result = []
        lenlist = len(itemList) < self.urllimit
        # Only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/Items?Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=Audio&format=json"
        if itemList and lenlist:
            url = "%s&Ids=%s" % (url, ",".join(itemList))
        
        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else: # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

        return result

    def getMusicSongsTotal(self):

        result = []

        url = "{server}/mediabrowser/Users/{UserId}/Items?Index=1&Limit=1&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=Audio&format=json"
        jsondata = self.doUtils.downloadUrl(url)

        total = jsondata['TotalRecordCount']
        index = 1
        jump = 200

        while index < total:
            url = "{server}/mediabrowser/Users/{UserId}/Items?StartIndex=%s&Limit=%s&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=Audio&format=json" % (index, jump)
            jsondata = self.doUtils.downloadUrl(url)
            result.extend(jsondata['Items'])
            index += jump

        return result
    
    def getMusicAlbums(self, itemList = []):
        
        result = []
        lenlist = len(itemList) < self.urllimit
        # Only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/Items?Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=MusicAlbum&format=json"
        if itemList and lenlist:
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
            # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

        return result
    
    def getMusicAlbumsTotal(self):

        result = []

        url = "{server}/mediabrowser/Users/{UserId}/Items?Limit=1&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&IncludeItemTypes=MusicAlbum&format=json"
        jsondata = self.doUtils.downloadUrl(url)

        total = jsondata['TotalRecordCount']
        index = 1
        jump = 200

        while index < total:
            url = "{server}/mediabrowser/Users/{UserId}/Items?StartIndex=%s&Limit=%s&Fields=Etag,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&SortBy=DateCreated&Recursive=true&IncludeItemTypes=MusicAlbum&format=json" % (index, jump)
            jsondata = self.doUtils.downloadUrl(url)

            tempresult = []
            # Only return valid albums - which have artists
            for item in jsondata['Items']:
                if item['AlbumArtists']:
                    tempresult.append(item)

            result.extend(tempresult)
            index += jump

        return result

    def getTvShows(self, parentId, itemList = []):
        
        result = []
        lenlist = len(itemList) < self.urllimit
        # Only get basic info for our sync-compares
        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&SortBy=SortName&Fields=CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Descending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1" % parentId
        if itemList and lenlist:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else: # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

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
        lenlist = len(itemList) < self.urllimit

        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Name,SortName,CumulativeRunTimeTicks,Etag&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % showId
        if itemList and lenlist:
            url = "%s&Ids=%s" % (url, ",".join(itemList))

        jsondata = self.doUtils.downloadUrl(url)
        try:
            result = jsondata['Items']
        except: pass
        else: # If list was longer than 49 items, we pulled the entire list so we need to sort
            if not lenlist:
                result = self.filterbyId(result, itemList)

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

    def getItem(self, id):
        
        result = {}
        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&ImageTypeLimit=1&Fields=Etag" % id
        
        jsondata = self.doUtils.downloadUrl(url)
        if jsondata:
            result = jsondata

        return result
    
    def getFullItem(self, id):
        
        result = {}
        url = "{server}/mediabrowser/Users/{UserId}/Items/%s?format=json&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview,CriticRating,CriticRatingSummary" % id
        
        jsondata = self.doUtils.downloadUrl(url)     
        if jsondata:
            result = jsondata

        return result
    
    def getCollections(self, type):
        # Build a list of the user views
        collections = []

        url = "{server}/mediabrowser/Users/{UserId}/Items?Sortby=SortName&format=json"
        jsondata = self.doUtils.downloadUrl(url)

        try:
            result = jsondata['Items']
        except: pass
        else:
            for item in result:
                if item['RecursiveItemCount']:
                    name = item['Name']
                    itemtype = item.get('CollectionType')
                    content = itemtype

                    if itemtype is None and type in ("movies", "tvshows"):
                        # Mixed content or rich presentation is disabled
                        itemtype = type
                        content = "mixed"

                    if itemtype == type and name != "Collections":
                        collections.append({
                            
                            'title': name,
                            'type': itemtype,
                            'id': item['Id'],
                            'content': content
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