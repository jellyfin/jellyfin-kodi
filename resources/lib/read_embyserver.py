# -*- coding: utf-8 -*-

#################################################################################################

import logging
import hashlib

import xbmc

import downloadutils
from utils import window, settings, kodiSQL

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Read_EmbyServer():

    limitIndex = int(settings('limitindex'))


    def __init__(self):

        self.doUtils = downloadutils.DownloadUtils().downloadUrl

        self.userId = window('emby_currUser')
        self.server = window('emby_server%s' % self.userId)


    def split_list(self, itemlist, size):
        # Split up list in pieces of size. Will generate a list of lists
        return [itemlist[i:i+size] for i in range(0, len(itemlist), size)]

    def getItem(self, itemid):
        # This will return the full item
        item = {}

        result = self.doUtils("{server}/emby/Users/{UserId}/Items/%s?format=json" % itemid)
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
            url = "{server}/emby/Users/{UserId}/Items?&format=json"
            result = self.doUtils(url, parameters=params)
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
                        "MediaSources,VoteCount"
                )
            }
            url = "{server}/emby/Users/{UserId}/Items?format=json"
            result = self.doUtils(url, parameters=params)
            if result:
                items.extend(result['Items'])

        return items

    def getView_embyId(self, itemid):
        # Returns ancestors using embyId
        viewId = None

        url = "{server}/emby/Items/%s/Ancestors?UserId={UserId}&format=json" % itemid
        for view in self.doUtils(url):

            if view['Type'] == "CollectionFolder":
                # Found view
                viewId = view['Id']

        # Compare to view table in emby database
        emby = kodiSQL('emby')
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
    
    def getFilteredSection(self, parentid, itemtype=None, sortby="SortName", recursive=True,
                        limit=None, sortorder="Ascending", filter_type=""):
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
            'Filters': filter_type,
            'Fields': (

                "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers"
            )
        }
        return self.doUtils("{server}/emby/Users/{UserId}/Items?format=json", parameters=params)
    
    def getTvChannels(self):
        
        params = {

            'EnableImages': True,
            'Fields': (

                "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers"
            )
        }
        url = "{server}/emby/LiveTv/Channels/?userid={UserId}&format=json"
        return self.doUtils(url, parameters=params)
    
    def getTvRecordings(self, groupid):
        
        if groupid == "root":
            groupid = ""
        
        params = {

            'GroupId': groupid,
            'EnableImages': True,
            'Fields': (
                
                "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers"
            )
        }
        url = "{server}/emby/LiveTv/Recordings/?userid={UserId}&format=json"
        return self.doUtils(url, parameters=params)
    
    def getSection(self, parentid, itemtype=None, sortby="SortName", artist_id=None, basic=False, dialog=None):

        items = {
            
            'Items': [],
            'TotalRecordCount': 0
        }

        # Get total number of items
        url = "{server}/emby/Users/{UserId}/Items?format=json"
        params = {

            'ParentId': parentid,
            'ArtistIds': artist_id,
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
            log.debug("%s:%s Failed to retrieve the server response." % (url, params))

        else:
            index = 0
            jump = self.limitIndex
            throttled = False
            highestjump = 0

            while index < total:
                # Get items by chunk to increase retrieval speed at scale
                params = {

                    'ParentId': parentid,
                    'ArtistIds': artist_id,
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
                        "MediaSources,VoteCount"
                    )
                try:
                    result = self.doUtils(url, parameters=params)
                    items['Items'].extend(result['Items'])
                except Warning as error:
                    if "400" in error:
                        log.info("Something went wrong, aborting request.")
                        index += jump
                except TypeError:
                    # Something happened to the connection
                    if not throttled:
                        throttled = True
                        log.info("Throttle activated.")
                    
                    if jump == highestjump:
                        # We already tried with the highestjump, but it failed. Reset value.
                        log.info("Reset highest value.")
                        highestjump = 0

                    # Lower the number by half
                    if highestjump:
                        throttled = False
                        jump = highestjump
                        log.info("Throttle deactivated.")
                    else:
                        jump = int(jump/4)
                        log.debug("Set jump limit to recover: %s" % jump)
                    
                    retry = 0
                    while window('emby_online') != "true":
                        # Wait server to come back online
                        if retry == 5:
                            log.info("Unable to reconnect to server. Abort process.")
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
                        log.info("Increase jump limit to: %s" % jump)
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
            log.debug("Error retrieving views for type: %s" % mediatype)
        else:
            for item in items:

                if item['Type'] in ("Channel", "PlaylistsFolder"):
                    # Filter view types
                    continue

                # 3/4/2016 OriginalCollectionType is added
                itemtype = item.get('OriginalCollectionType', item.get('CollectionType', "mixed"))
                
                if item['Name'] not in ('Collections', 'Trailers', 'Playlists'):
                    
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
        url = "{server}/emby/Shows/%s/Seasons?UserId={UserId}&format=json" % showId
        result = self.doUtils(url, parameters=params)
        if result:
            items = result

        return items

    def getEpisodes(self, parentId, basic=False, dialog=None):

        return self.getSection(parentId, "Episode", basic=basic, dialog=dialog)

    def getEpisodesbyShow(self, showId):

        return self.getSection(showId, "Episode")

    def getEpisodesbySeason(self, seasonId):

        return self.getSection(seasonId, "Episode")

    def getArtists(self, parent_id=None, dialog=None):

        items = {

            'Items': [],
            'TotalRecordCount': 0
        }

        # Get total number of items
        url = "{server}/emby/Artists?UserId={UserId}&format=json"
        params = {

            'ParentId': parent_id,
            'Recursive': True,
            'Limit': 1
        }
        result = self.doUtils(url, parameters=params)
        try:
            total = result['TotalRecordCount']
            items['TotalRecordCount'] = total

        except TypeError: # Failed to retrieve
            log.debug("%s:%s Failed to retrieve the server response." % (url, params))

        else:
            index = 0
            jump = self.limitIndex

            while index < total:
                # Get items by chunk to increase retrieval speed at scale
                params = {

                    'ParentId': parent_id,
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

        return self.getSection(None, "MusicAlbum", sortby="DateCreated", artist_id=artistId)

    def getSongs(self, basic=False, dialog=None):

        return self.getSection(None, "Audio", basic=basic, dialog=dialog)

    def getSongsbyAlbum(self, albumId):

        return self.getSection(albumId, "Audio")

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

    def updateUserRating(self, itemid, favourite=None):
        # Updates the user rating to Emby
        doUtils = self.doUtils

        if favourite:
            url = "{server}/emby/Users/{UserId}/FavoriteItems/%s?format=json" % itemid
            doUtils(url, action_type="POST")
        elif not favourite:
            url = "{server}/emby/Users/{UserId}/FavoriteItems/%s?format=json" % itemid
            doUtils(url, action_type="DELETE")
        else:
            log.info("Error processing user rating.")

        log.info("Update user rating to emby for itemid: %s | favourite: %s" % (itemid, favourite))

    def refreshItem(self, itemid):

        url = "{server}/emby/Items/%s/Refresh?format=json" % itemid
        params = {

            'Recursive': True,
            'ImageRefreshMode': "FullRefresh",
            'MetadataRefreshMode': "FullRefresh",
            'ReplaceAllImages': False,
            'ReplaceAllMetadata': True

        }
        self.doUtils(url, postBody=params, action_type="POST")

    def deleteItem(self, itemid):

        url = "{server}/emby/Items/%s?format=json" % itemid
        self.doUtils(url, action_type="DELETE")

    def getUsers(self, server):

        url = "%s/emby/Users/Public?format=json" % server
        users = self.doUtils(url, authenticate=False)

        return users or []

    def loginUser(self, server, username, password=None):

        password = password or ""
        url = "%s/emby/Users/AuthenticateByName?format=json" % server
        data = {'username': username, 'password': hashlib.sha1(password).hexdigest()}
        user = self.doUtils(url, postBody=data, action_type="POST", authenticate=False)

        return user