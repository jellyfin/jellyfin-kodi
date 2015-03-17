#################################################################################################
# ReadEmbyDB
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import json

from DownloadUtils import DownloadUtils

addon = xbmcaddon.Addon(id='plugin.video.mb3sync')

class ReadEmbyDB():   
    def getMovies(self, id, fullinfo = False):
        result = None
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()        
        
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/items?ParentId=' + id + '&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/items?ParentId=' + id + '&SortBy=SortName&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Movie&CollapseBoxSetItems=false&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
    
    def getTVShows(self, fullinfo = False):
        result = None
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()   
        
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/Items?&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/Items?&SortBy=SortName&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
    
    def getEpisodes(self, showId, fullinfo = False):
        result = None
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()   
        
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/Items?ParentId=' + showId + '&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/Items?ParentId=' + showId + '&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Name,SortName,CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
        return result
    
    def getCollections(self, type):
        #Build a list of the user views
        userid = DownloadUtils().getUserId()  
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        viewsUrl = server + "/mediabrowser/Users/" + userid + "/Views?format=json&ImageTypeLimit=1"
        jsonData = DownloadUtils().downloadUrl(viewsUrl, suppress=True, popup=0 )
        
        if(jsonData != ""):
            views = json.loads(jsonData)
            views = views.get("Items")
            collections=[]
            for view in views:
                if view.get("Type") == 'UserView': # Need to grab the real main node
                    newViewsUrl = server + '/mediabrowser/Users/' + userid + '/items?ParentId=' + view.get("Id") + '&SortBy=SortName&SortOrder=Ascending&format=json&ImageTypeLimit=1'
                    jsonData = DownloadUtils().downloadUrl(newViewsUrl, suppress=True, popup=0 )
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
        
