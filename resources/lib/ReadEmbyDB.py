#################################################################################################
# ReadEmbyDB
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import json

from DownloadUtils import DownloadUtils

addon = xbmcaddon.Addon(id='plugin.video.emby')

class ReadEmbyDB():   
    def getMovies(self, id, fullinfo = False, fullSync = True, itemList = []):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()

        if fullSync:
            sortstring = "&SortBy=SortName"
        else:
            if(len(itemList) > 0): # if we want a certain list specify it
                #sortstring = "&Ids=" + ",".join(itemList)
                sortstring = "" # work around for now until ParetnId and Id work together
            else: # just get the last 20 created items
                sortstring = "&Limit=20&SortBy=DateCreated"
            
        if fullinfo:
            url = "%s/mediabrowser/Users/%s/items?ParentId=%s%s&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Descending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1" % (server, userid, id, sortstring)
        else:
            url = "%s/mediabrowser/Users/%s/items?ParentId=%s%s&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Descending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1" % (server, userid, id, sortstring)

        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        # work around for now until ParetnId and Id work together
        if(result != None and len(result) > 0 and len(itemList) > 0):
            newResult = []
            for item in result:
                if(item.get("Id") in itemList):
                    newResult.append(item)
            result = newResult
            
        return result

    def getMusicVideos(self, fullinfo = False, fullSync = True):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()

        if not fullSync:
            sortstring = "&Limit=20&SortBy=DateCreated"
        else:
            sortstring = "&SortBy=SortName"
        
        if fullinfo:
            url = "%s/mediabrowser/Users/%s/items?%s&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Descending&IncludeItemTypes=MusicVideo&format=json&ImageTypeLimit=1" % (server, userid, sortstring)
        else:
            url = "%s/mediabrowser/Users/%s/items?%s&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Descending&IncludeItemTypes=MusicVideo&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1" % (server, userid, sortstring)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
        
    def getItem(self, id):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()

        url = "%s/mediabrowser/Users/%s/Items/%s?format=json&ImageTypeLimit=1" % (server, userid, id)
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=1 )     
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)

        return result
    
    def getFullItem(self, id):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()

        url = "%s/mediabrowser/Users/%s/Items/%s?format=json" % (server, userid, id)
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=1 )     
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)

        return result
    
    def getTVShows(self, id, fullinfo = False, fullSync = False):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()

        if not fullSync:
            sortstring = "&Limit=20&SortBy=DateCreated"
        else:
            sortstring = "&SortBy=SortName"
        
        
        if fullinfo:
            url = "%s/mediabrowser/Users/%s/Items?ParentId=%s%s&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Descending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1" % (server, userid, id, sortstring)
        else:
            url = "%s/mediabrowser/Users/%s/Items?ParentId=%s%s&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Descending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1" % (server, userid, id, sortstring)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
    
    def getTVShowSeasons(self, tvShowId):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()

        url = "%s/Shows/%s/Seasons?UserId=%s&format=json&ImageTypeLimit=1" % (server, tvShowId, userid)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
                result = self.changeSeasonSpecialToSeason100(result)

        return result

    def changeSeasonSpecialToSeason100(self, result):
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        if(addon.getSetting("useSeason100ForSpecials") != "true"):
            return result
            
        for item in result:
            if(item != None and item.get("IndexNumber") != None and item.get("IndexNumber") == 0):
                item["IndexNumber"] = 100
        return result
    
    def changeEpisodeSpecialToSeason100(self, result):
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        if(addon.getSetting("useSeason100ForSpecials") != "true"):
            return result
            
        for item in result:
            if(item != None and item.get("ParentIndexNumber") != None and item.get("ParentIndexNumber") == 0):
                item["ParentIndexNumber"] = 100
        return result
    
    def getEpisodes(self, showId, fullinfo = False):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()  
        
        if fullinfo:
            url = "%s/mediabrowser/Users/%s/Items?ParentId=%s&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % (server, userid, showId)
        else:
            url = "%s/mediabrowser/Users/%s/Items?ParentId=%s&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Name,SortName,CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % (server, userid, showId)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
                result = self.changeEpisodeSpecialToSeason100(result)
                
        return result
    
    def getLatestEpisodes(self, fullinfo = False, itemList = []):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils() 
        
        limitString = "Limit=20&SortBy=DateCreated&"
        if(len(itemList) > 0): # if we want a certain list specify it
            limitString = "Ids=" + ",".join(itemList) + "&"
        
        if fullinfo:
            url = "%s/mediabrowser/Users/%s/Items?%sIsVirtualUnaired=false&IsMissing=False&Fields=ParentId,Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Descending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % (server, userid, limitString)
        else:
            url = "%s/mediabrowser/Users/%s/Items?%sIsVirtualUnaired=false&IsMissing=False&Fields=ParentId,Name,SortName,CumulativeRunTimeTicks&Recursive=true&SortOrder=Descending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1" % (server, userid, limitString)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
                result = self.changeEpisodeSpecialToSeason100(result)
                
        return result
    
    def getCollections(self, type):
        #Build a list of the user views
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)

        downloadUtils = DownloadUtils()
        
        try:
            url = "%s/mediabrowser/Users/%s/Items/Root?format=json" % (server, userid)
            jsonData = downloadUtils.downloadUrl(url)
        except Exception, msg:
            error = "Get connect : " + str(msg)
            xbmc.log (error)
            return []
        
        if(jsonData == ""):
            return []
            
        result = json.loads(jsonData)
        
        parentid = result.get("Id")
        
        htmlpath = "%s/mediabrowser/Users/%s/items?ParentId=%s&Sortby=SortName&format=json" % (server, userid, parentid)
        jsonData = downloadUtils.downloadUrl(htmlpath)
        collections=[]
        
        if(jsonData == ""):
            return []
        
        result = json.loads(jsonData)
        result = result.get("Items")
        
        for item in result:
            if(item.get("RecursiveItemCount") != 0):
                Temp = item.get("Name")
                Name = Temp.encode('utf-8')
                section = item.get("CollectionType")
                itemtype = item.get("CollectionType")
                if itemtype == None or itemtype == "":
                    itemtype = "movies" # User may not have declared the type
                if itemtype == type and item.get("Name") != "Collections":
                    collections.append( {'title'      : item.get("Name"),
                            'type'           : itemtype,
                            'id'             : item.get("Id")})
        return collections
    
    def getViewCollections(self, type):
        #Build a list of the user views
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        viewsUrl = "%s/mediabrowser/Users/%s/Views?format=json&ImageTypeLimit=1" % (server, userid)
        jsonData = DownloadUtils().downloadUrl(viewsUrl, suppress=False, popup=0 )
        collections=[]
        
        if(jsonData != ""):
            views = json.loads(jsonData)
            views = views.get("Items")

            for view in views:
                if view.get("Type") == 'UserView': # Need to grab the real main node
                    newViewsUrl = "%s/mediabrowser/Users/%s/items?ParentId=%s&SortBy=SortName&SortOrder=Ascending&format=json&ImageTypeLimit=1" % (server, userid, view.get("Id"))
                    jsonData = DownloadUtils().downloadUrl(newViewsUrl, suppress=False, popup=0 )
                    if(jsonData != ""):
                        newViews = json.loads(jsonData)
                        newViews = newViews.get("Items")
                        for newView in newViews:
                            # There are multiple nodes in here like 'Latest', 'NextUp' - below we grab the full node.
                            if newView.get("CollectionType") == "MovieMovies" or newView.get("CollectionType") == "TvShowSeries":
                                view=newView
                if(view.get("ChildCount") != 0):
                    Name =(view.get("Name")) 
                    
                total = str(view.get("ChildCount"))
                type = view.get("CollectionType")
                if type == None:
                    type = "None" # User may not have declared the type
                if type == type:
                    collections.append( {'title'      : Name,
                            'type'           : type,
                            'id'             : view.get("Id")})
        return collections
    
    def getBoxSets(self):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()  
        
        url = "%s/mediabrowser/Users/%s/Items?SortBy=SortName&IsVirtualUnaired=false&IsMissing=False&Fields=Name,SortName,CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=BoxSet&format=json&ImageTypeLimit=1" % (server, userid)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
        return result
    
    def getMoviesInBoxSet(self,boxsetId):
        result = None
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        
        downloadUtils = DownloadUtils()
        
        url = "%s/mediabrowser/Users/%s/Items?ParentId=%s&Fields=ItemCounts&format=json&ImageTypeLimit=1" % (server, userid, boxsetId)
        
        jsonData = downloadUtils.downloadUrl(url, suppress=False, popup=0)
        
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
        return result