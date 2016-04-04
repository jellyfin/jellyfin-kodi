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

        result = self.doUtils("{server}/metaman/Users/{UserId}/Items/%s?format=json" % itemid)
        if result:
            item = result

        return item

    def getItems(self, itemlist):
        
        items = []

        itemlists = self.split_list(itemlist, 50)
        for itemlist in itemlists:
            # Will return basic information
            params = {

                'Ids': ",".join(itemlist),
                'Fields': "Etag"
            }
            result = self.doUtils("{server}/emby/Users/{UserId}/Items?&format=json", parameters=params)
            if result:
                items.extend(result['Items'])

        return items

    def getFullItems(self, itemlist):
        
        items = []

        itemlists = self.split_list(itemlist, 50)
        for itemlist in itemlists:

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
            result = self.doUtils("{server}/emby/Users/{UserId}/Items?format=json", parameters=params)
            if result:
                items.extend(result['Items'])

        return items

    def getView_embyId(self, itemid):
        # Returns ancestors using embyId
        viewId = None

        for view in self.doUtils("{server}/emby/Items/%s/Ancestors?UserId={UserId}&format=json" % itemid):

            if view['Type'] == "CollectionFolder":
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
        return self.doUtils("{server}/emby/Users/{UserId}/Items?format=json", parameters=params)
    
    def getTvChannels(self):
        params = {

            'EnableImages': True,
            'Fields': ( "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
            "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
            "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
            "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
            "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers")
        }
        return self.doUtils("{server}/emby/LiveTv/Channels/?userid={UserId}&format=json", parameters=params)
    
    def getTvRecordings(self, groupid):
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
        return self.doUtils("{server}/emby/LiveTv/Recordings/?userid={UserId}&format=json", parameters=params)
    
    def getSection(self, parentid, itemtype=None, sortby="SortName", basic=False, dialog=None):

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
        result = self.doUtils(url, parameters=params)
        try:
            total = result['TotalRecordCount']
            items['TotalRecordCount'] = total

        except TypeError: # Failed to retrieve
            self.logMsg("%s:%s Failed to retrieve the server response." % (url, params), 2)

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
                result = self.doUtils(url, parameters=params)
                try:
                    items['Items'].extend(result['Items'])
                except TypeError:
                    # Something happened to the connection
                    if not throttled:
                        throttled = True
                        self.logMsg("Throttle activated.", 1)
                    
                    if jump == highestjump:
                        # We already tried with the highestjump, but it failed. Reset value.
                        self.logMsg("Reset highest value.", 1)
                        highestjump = 0

                    # Lower the number by half
                    if highestjump:
                        throttled = False
                        jump = highestjump
                        self.logMsg("Throttle deactivated.", 1)
                    else:
                        jump = int(jump/4)
                        self.logMsg("Set jump limit to recover: %s" % jump, 2)
                    
                    retry = 0
                    while utils.window('emby_online') != "true":
                        # Wait server to come back online
                        if retry == 5:
                            self.logMsg("Unable to reconnect to server. Abort process.", 1)
                            return items
                        
                        retry += 1
                        if xbmc.Monitor().waitForAbort(1):
                            # Abort was requested while waiting.
                            return items
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
                        self.logMsg("Increase jump limit to: %s" % jump, 1)
        return items

    def getViews(self, mediatype="", root=False, sortedlist=False):
        # Build a list of user views
        views = []
        mediatype = mediatype.lower()

        if not root:
            url = "{server}/emby/Users/{UserId}/Views?format=json"
        else: # Views ungrouped
            url = "{server}/emby/Users/{UserId}/Items?Sortby=SortName&format=json"

        result = self.doUtils(url)
        try:
            items = result['Items']
        except TypeError:
            self.logMsg("Error retrieving views for type: %s" % mediatype, 2)
        else:
            for item in items:

                item['Name'] = item['Name']
                if item['Type'] == "Channel":
                    # Filter view types
                    continue

                # 3/4/2016 OriginalCollectionType is added
                itemtype = item.get('OriginalCollectionType', item.get('CollectionType', "mixed"))

                # 11/29/2015 Remove this once OriginalCollectionType is added to stable server.
                # Assumed missing is mixed then.
                '''if itemtype is None:
                    url = "{server}/emby/Library/MediaFolders?format=json"
                    result = self.doUtils(url)

                    for folder in result['Items']:
                        if item['Id'] == folder['Id']:
                            itemtype = folder.get('CollectionType', "mixed")'''
                
                if item['Name'] not in ('Collections', 'Trailers'):
                    
                    if sortedlist:
                        views.append({

                            'name': item['Name'],
                            'type': itemtype,
                            'id': item['Id']
                        })

                    elif (itemtype == mediatype or 
                        (itemtype == "mixed" and mediatype in ("movies", "tvshows"))):
                    
                        views.append({

                            'name': item['Name'],
                            'type': itemtype,
                            'id': item['Id']
                        })
        
        return views

    def verifyView(self, parentid, itemid):

        belongs = False
        params = {

            'ParentId': parentid,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'Recursive': True,
            'Ids': itemid
        }
        result = self.doUtils("{server}/emby/Users/{UserId}/Items?format=json", parameters=params)
        try:
            total = result['TotalRecordCount']
        except TypeError:
            # Something happened to the connection
            pass
        else:
            if total:
                belongs = True

        return belongs

    def getMovies(self, parentId, basic=False, dialog=None):
        return self.getSection(parentId, "Movie", basic=basic, dialog=dialog)

    def getBoxset(self, dialog=None):
        return self.getSection(None, "BoxSet", dialog=dialog)

    def getMovies_byBoxset(self, boxsetid):
        return self.getSection(boxsetid, "Movie")

    def getMusicVideos(self, parentId, basic=False, dialog=None):
        return self.getSection(parentId, "MusicVideo", basic=basic, dialog=dialog)

    def getHomeVideos(self, parentId):

        return self.getSection(parentId, "Video")

    def getShows(self, parentId, basic=False, dialog=None):
        return self.getSection(parentId, "Series", basic=basic, dialog=dialog)

    def getSeasons(self, showId):

        items = {
            
            'Items': [],
            'TotalRecordCount': 0
        }

        params = {

            'IsVirtualUnaired': False,
            'Fields': "Etag"
        }
        result = self.doUtils("{server}/emby/Shows/%s/Seasons?UserId={UserId}&format=json" % showId, parameters=params)
        if result:
            items = result

        return items

    def getEpisodes(self, parentId, basic=False, dialog=None):

        return self.getSection(parentId, "Episode", basic=basic, dialog=dialog)

    def getEpisodesbyShow(self, showId):

        return self.getSection(showId, "Episode")

    def getEpisodesbySeason(self, seasonId):

        return self.getSection(seasonId, "Episode")


    def getArtists(self, dialog=None):

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
        result = self.doUtils(url, parameters=params)
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
                result = self.doUtils(url, parameters=params)
                items['Items'].extend(result['Items'])

                index += jump
                if dialog:
                    percentage = int((float(index) / float(total))*100)
                    dialog.update(percentage)
        return items

    def getAlbums(self, basic=False, dialog=None):
        return self.getSection(None, "MusicAlbum", sortby="DateCreated", basic=basic, dialog=dialog)

    def getAlbumsbyArtist(self, artistId):
        return self.getSection(artistId, "MusicAlbum", sortby="DateCreated")

    def getSongs(self, basic=False, dialog=None):
        return self.getSection(None, "Audio", basic=basic, dialog=dialog)

    def getSongsbyAlbum(self, albumId):
        return self.getSection(albumId, "Audio")


    def getAdditionalParts(self, itemId):

        items = {
            
            'Items': [],
            'TotalRecordCount': 0
        }

        result = self.doUtils("{server}/emby/Videos/%s/AdditionalParts?UserId={UserId}&format=json" % itemId)
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

    def updateUserRating(self, itemid, like=None, favourite=None, deletelike=False):
        # Updates the user rating to Emby
        
        if favourite:
            self.doUtils("{server}/emby/Users/{UserId}/FavoriteItems/%s?format=json" % itemid, action_type="POST")
        elif favourite == False:
            self.doUtils("{server}/emby/Users/{UserId}/FavoriteItems/%s?format=json" % itemid, action_type="DELETE")

        if not deletelike and like:
            self.doUtils("{server}/emby/Users/{UserId}/Items/%s/Rating?Likes=true&format=json" % itemid, action_type="POST")
        elif not deletelike and like is False:
            self.doUtils("{server}/emby/Users/{UserId}/Items/%s/Rating?Likes=false&format=json" % itemid, action_type="POST")
        elif deletelike:
            self.doUtils("{server}/emby/Users/{UserId}/Items/%s/Rating?format=json" % itemid, action_type="DELETE")

        self.logMsg("Update user rating to emby for itemid: %s "
                    "| like: %s | favourite: %s | deletelike: %s"
                    % (itemid, like, favourite, deletelike), 1)