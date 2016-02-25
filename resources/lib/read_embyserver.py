# -*- coding: utf-8 -*-

#################################################################################################

import xbmc

import utils
import clientinfo
import downloadutils

#################################################################################################


class Read_EmbyServer():

    limitIndex = int(utils.settings('limitindex'))


    def __init__(self):

        window = utils.window

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl

        self.userId = window('emby_currUser')
        self.server = window('emby_server%s' % self.userId)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def split_list(self, itemlist, size):
        # Split up list in pieces of size. Will generate a list of lists
        return [itemlist[i:i+size] for i in range(0, len(itemlist), size)]


    def getItem(self, itemid):
        # This will return the full item
        item = {}

        url = "{server}/emby/Users/{UserId}/Items/%s?format=json" % itemid
        result = self.doUtils(url)
        if result:
            item = result

        return item

    def getItems(self, itemlist):
        
        items = []

        itemlists = self.split_list(itemlist, 50)
        for itemlist in itemlists:
            # Will return basic information
            url = "{server}/emby/Users/{UserId}/Items?&format=json"
            params = {

                'Ids': ",".join(itemlist),
                'Fields': "Etag"
            }
            result = self.doUtils(url, parameters=params)
            if result:
                items.extend(result['Items'])

        return items

    def getFullItems(self, itemlist):
        
        items = []

        itemlists = self.split_list(itemlist, 50)
        for itemlist in itemlists:

            url = "{server}/emby/Users/{UserId}/Items?format=json"
            params = {

                "Ids": ",".join(itemlist),
                "Fields": (
                        
                        "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                        "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                        "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                        "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                        "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
                        "MediaSources"
                )
            }
            result = self.doUtils(url, parameters=params)
            if result:
                items.extend(result['Items'])

        return items

    def getView_embyId(self, itemid):
        # Returns ancestors using embyId
        viewId = None
        url = "{server}/emby/Items/%s/Ancestors?UserId={UserId}&format=json" % itemid
        result = self.doUtils(url)

        for view in result:

            viewtype = view['Type']
            if viewtype == "CollectionFolder":
                # Found view
                viewId = view['Id']

        # Compare to view table in emby database
        emby = utils.kodiSQL('emby')
        cursor_emby = emby.cursor()
        query = ' '.join((

            "SELECT view_name, media_type",
            "FROM view",
            "WHERE view_id = ?"
        ))
        cursor_emby.execute(query, (viewId,))
        result = cursor_emby.fetchone()
        try:
            viewName = result[0]
            mediatype = result[1]
        except TypeError:
            viewName = None
            mediatype = None

        cursor_emby.close()

        return [viewName, viewId, mediatype]
    
    def getFilteredSection(self, parentid, itemtype=None, sortby="SortName", recursive=True, limit=None, sortorder="Ascending", filter=""):
        doUtils = self.doUtils
        url = "{server}/emby/Users/{UserId}/Items?format=json"
        params = {

            'ParentId': parentid,
            'IncludeItemTypes': itemtype,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'Recursive': recursive,
            'Limit': limit,
            'SortBy': sortby,
            'SortOrder': sortorder,
            'Filters': filter,
            'Fields': ( "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
            "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
            "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
            "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
            "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers")
        }
        return doUtils(url, parameters=params)
    
    def getTvChannels(self):
        doUtils = self.doUtils
        url = "{server}/emby/LiveTv/Channels/?userid={UserId}&format=json"
        params = {

            'EnableImages': True,
            'Fields': ( "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
            "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
            "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
            "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
            "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers")
        }
        return doUtils(url, parameters=params)
    
    def getTvRecordings(self, groupid):
        doUtils = self.doUtils
        url = "{server}/emby/LiveTv/Recordings/?userid={UserId}&format=json"
        if groupid == "root": groupid = ""
        params = {

            'GroupId': groupid,
            'EnableImages': True,
            'Fields': ( "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
            "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
            "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
            "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
            "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers")
        }
        return doUtils(url, parameters=params)
    
    def getSection(self, parentid, itemtype=None, sortby="SortName", basic=False, dialog=None):

        log = self.logMsg

        doUtils = self.doUtils
        items = {
            
            'Items': [],
            'TotalRecordCount': 0
        }

        # Get total number of items
        url = "{server}/emby/Users/{UserId}/Items?format=json"
        params = {

            'ParentId': parentid,
            'IncludeItemTypes': itemtype,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'Recursive': True,
            'Limit': 1
        }
        result = doUtils(url, parameters=params)
        try:
            total = result['TotalRecordCount']
            items['TotalRecordCount'] = total

        except TypeError: # Failed to retrieve
            log("%s:%s Failed to retrieve the server response." % (url, params), 2)

        else:
            index = 0
            jump = self.limitIndex
            throttled = False
            highestjump = 0

            while index < total:
                # Get items by chunk to increase retrieval speed at scale
                params = {

                    'ParentId': parentid,
                    'IncludeItemTypes': itemtype,
                    'CollapseBoxSetItems': False,
                    'IsVirtualUnaired': False,
                    'IsMissing': False,
                    'Recursive': True,
                    'StartIndex': index,
                    'Limit': jump,
                    'SortBy': sortby,
                    'SortOrder': "Ascending",
                }
                if basic:
                    params['Fields'] = "Etag"
                else:
                    params['Fields'] = (

                        "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                        "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                        "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                        "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                        "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
                        "MediaSources"
                    )
                result = doUtils(url, parameters=params)
                try:
                    items['Items'].extend(result['Items'])
                except TypeError:
                    # Something happened to the connection
                    if not throttled:
                        throttled = True
                        log("Throttle activated.", 1)
                    
                    if jump == highestjump:
                        # We already tried with the highestjump, but it failed. Reset value.
                        log("Reset highest value.", 1)
                        highestjump = 0

                    # Lower the number by half
                    if highestjump:
                        throttled = False
                        jump = highestjump
                        log("Throttle deactivated.", 1)
                    else:
                        jump = int(jump/4)
                        log("Set jump limit to recover: %s" % jump, 2)
                    
                    retry = 0
                    while utils.window('emby_online') != "true":
                        # Wait server to come back online
                        if retry == 3:
                            log("Unable to reconnect to server. Abort process.", 1)
                            return
                        
                        retry += 1
                        if xbmc.Monitor().waitForAbort(1):
                            # Abort was requested while waiting.
                            return
                else:
                    # Request succeeded
                    index += jump

                    if dialog:
                        percentage = int((float(index) / float(total))*100)
                        dialog.update(percentage)

                    if jump > highestjump:
                        # Adjust with the latest number, if it's greater
                        highestjump = jump

                    if throttled:
                        # We needed to adjust the number of item requested.
                        # keep increasing until the connection times out again
                        # to find the highest value
                        increment = int(jump*0.33)
                        if not increment: # Incase the increment is 0
                            increment = 10

                        jump += increment
                        log("Increase jump limit to: %s" % jump, 1)
        return items

    def getViews(self, mediatype="", root=False, sortedlist=False):
        # Build a list of user views
        doUtils = self.doUtils
        views = []
        mediatype = mediatype.lower()

        if not root:
            url = "{server}/emby/Users/{UserId}/Views?format=json"
        else: # Views ungrouped
            url = "{server}/emby/Users/{UserId}/Items?Sortby=SortName&format=json"

        result = doUtils(url)
        try:
            items = result['Items']
        except TypeError:
            self.logMsg("Error retrieving views for type: %s" % mediatype, 2)
        else:
            for item in items:

                name = item['Name']
                itemId = item['Id']
                viewtype = item['Type']

                if viewtype == "Channel":
                    # Filter view types
                    continue

                # 11/10/2015 Review key, when it's added to server. Currently unavailable.
                itemtype = item.get('OriginalCollectionType', item.get('CollectionType'))

                # 11/29/2015 Remove this once OriginalCollectionType is added to stable server.
                # Assumed missing is mixed then.
                if itemtype is None:
                    url = "{server}/emby/Library/MediaFolders?format=json"
                    result = doUtils(url)

                    for folder in result['Items']:
                        if itemId == folder['Id']:
                            itemtype = folder.get('CollectionType', "mixed")
                
                if name not in ('Collections', 'Trailers'):
                    
                    if sortedlist:
                        views.append({

                            'name': name,
                            'type': itemtype,
                            'id': itemId
                        })

                    elif (itemtype == mediatype or 
                        (itemtype == "mixed" and mediatype in ("movies", "tvshows"))):
                    
                        views.append({

                            'name': name,
                            'type': itemtype,
                            'id': itemId
                        })
        
        return views

    def getMovies(self, parentId, basic=False, dialog=None):

        items = self.getSection(parentId, "Movie", basic=basic, dialog=dialog)
        
        return items

    def getBoxset(self, dialog=None):

        items = self.getSection(None, "BoxSet", dialog=dialog)

        return items

    def getMovies_byBoxset(self, boxsetid):

        items = self.getSection(boxsetid, "Movie")

        return items

    def getMusicVideos(self, parentId, basic=False, dialog=None):

        items = self.getSection(parentId, "MusicVideo", basic=basic, dialog=dialog)

        return items

    def getHomeVideos(self, parentId):

        items = self.getSection(parentId, "Video")

        return items

    def getShows(self, parentId, basic=False, dialog=None):

        items = self.getSection(parentId, "Series", basic=basic, dialog=dialog)

        return items

    def getSeasons(self, showId):

        items = {
            
            'Items': [],
            'TotalRecordCount': 0
        }

        url = "{server}/emby/Shows/%s/Seasons?UserId={UserId}&format=json" % showId
        params = {

            'IsVirtualUnaired': False,
            'Fields': "Etag"
        }
        result = self.doUtils(url, parameters=params)
        if result:
            items = result

        return items

    def getEpisodes(self, parentId, basic=False, dialog=None):

        items = self.getSection(parentId, "Episode", basic=basic, dialog=dialog)

        return items

    def getEpisodesbyShow(self, showId):

        items = self.getSection(showId, "Episode")

        return items

    def getEpisodesbySeason(self, seasonId):

        items = self.getSection(seasonId, "Episode")

        return items

    def getArtists(self, dialog=None):

        doUtils = self.doUtils
        items = {

            'Items': [],
            'TotalRecordCount': 0
        }

        # Get total number of items
        url = "{server}/emby/Artists?UserId={UserId}&format=json"
        params = {

            'Recursive': True,
            'Limit': 1
        }
        result = doUtils(url, parameters=params)
        try:
            total = result['TotalRecordCount']
            items['TotalRecordCount'] = total

        except TypeError: # Failed to retrieve
            self.logMsg("%s:%s Failed to retrieve the server response." % (url, params), 2)

        else:
            index = 1
            jump = self.limitIndex

            while index < total:
                # Get items by chunk to increase retrieval speed at scale
                params = {

                    'Recursive': True,
                    'IsVirtualUnaired': False,
                    'IsMissing': False,
                    'StartIndex': index,
                    'Limit': jump,
                    'SortBy': "SortName",
                    'SortOrder': "Ascending",
                    'Fields': (

                        "Etag,Genres,SortName,Studios,Writer,ProductionYear,"
                        "CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,"
                        "AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview"
                    )
                }
                result = doUtils(url, parameters=params)
                items['Items'].extend(result['Items'])

                index += jump
                if dialog:
                    percentage = int((float(index) / float(total))*100)
                    dialog.update(percentage)
        return items

    def getAlbums(self, basic=False, dialog=None):

        items = self.getSection(None, "MusicAlbum", sortby="DateCreated", basic=basic, dialog=dialog)

        return items

    def getAlbumsbyArtist(self, artistId):

        items = self.getSection(artistId, "MusicAlbum", sortby="DateCreated")

        return items

    def getSongs(self, basic=False, dialog=None):

        items = self.getSection(None, "Audio", basic=basic, dialog=dialog)

        return items

    def getSongsbyAlbum(self, albumId):

        items = self.getSection(albumId, "Audio")

        return items

    def getAdditionalParts(self, itemId):

        items = {
            
            'Items': [],
            'TotalRecordCount': 0
        }

        url = "{server}/emby/Videos/%s/AdditionalParts?UserId={UserId}&format=json" % itemId
        result = self.doUtils(url)
        if result:
            items = result

        return items

    def sortby_mediatype(self, itemids):

        sorted_items = {}

        # Sort items
        items = self.getFullItems(itemids)
        for item in items:

            mediatype = item.get('Type')
            if mediatype:
                sorted_items.setdefault(mediatype, []).append(item)

        return sorted_items