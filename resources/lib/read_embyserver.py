# -*- coding: utf-8 -*-

#################################################################################################

import logging
import hashlib
import threading
import Queue

import xbmc

import downloadutils
import database
from utils import window, settings
from contextlib import closing

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class DownloadThreader(threading.Thread):

    is_finished = False

    def __init__(self, queue, output):

        self.queue = queue
        self.output = output
        threading.Thread.__init__(self)

    def run(self):

        try:
            query = self.queue.get()
        except Queue.Empty:
            self.is_finished = True
            return

        try:
            result = downloadutils.DownloadUtils().downloadUrl(query['url'],
                                                               parameters=query.get('params'))
            if result:
                self.output.extend(result['Items'])
        except Exception as error:
            log.error(error)

        self.queue.task_done()
        self.is_finished = True


class Read_EmbyServer():

    limitIndex = min(int(settings('limitIndex')), 50)
    download_limit = int(settings('downloadThreads'))
    download_threads = list()

    def __init__(self):

        self.doUtils = downloadutils.DownloadUtils()
        self.userId = window('emby_currUser')
        self.server = window('emby_server%s' % self.userId)

    def get_emby_url(self, handler):
        return "{server}/emby/%s" % handler

    def _add_worker_thread(self, queue, output):

        while True:
            for thread in self.download_threads:
                if thread.is_finished:
                    self.download_threads.remove(thread)

            if window('emby_online') != "true":
                # Something happened
                log.error("Server is not online, don't start new download thread")
                queue.task_done()
                return False

            if len(self.download_threads) < self.download_limit:
                # Start new "daemon thread" - actual daemon thread is not supported in Kodi
                new_thread = DownloadThreader(queue, output)

                counter = 0
                worked = False
                while counter < 10:
                    try:
                        new_thread.start()
                        worked = True
                        break
                    except:
                        counter = counter + 1
                        xbmc.sleep(1000)

                if worked:
                    self.download_threads.append(new_thread)
                    return True
                else:
                    return False
            else:
                log.info("Waiting for empty download spot: %s", len(self.download_threads))
                xbmc.sleep(100)


    def split_list(self, itemlist, size):
        # Split up list in pieces of size. Will generate a list of lists
        return [itemlist[i:i+size] for i in range(0, len(itemlist), size)]

    def getItem(self, itemid):
        # This will return the full item
        item = self.doUtils.downloadUrl("{server}/emby/Users/{UserId}/Items/%s?format=json" % itemid)
        return item

    def getItems(self, item_list):
        
        items = []
        queue = Queue.Queue()

        url = "{server}/emby/Users/{UserId}/Items?&format=json"
        for item_ids in self.split_list(item_list, self.limitIndex):
            # Will return basic information
            params = {

                'Ids': ",".join(item_ids),
                'Fields': "Etag"
            }
            queue.put({'url': url, 'params': params})
            if not self._add_worker_thread(queue, items):
                break

        queue.join()

        return items

    def getFullItems(self, item_list):
  
        items = []
        queue = Queue.Queue()

        url = "{server}/emby/Users/{UserId}/Items?format=json"
        for item_ids in self.split_list(item_list, self.limitIndex):
            params = {

                "Ids": ",".join(item_ids),
                "Fields": (
                        
                        "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                        "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                        "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                        "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                        "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
                        "MediaSources,VoteCount,ItemCounts"
                )
            }
            queue.put({'url': url, 'params': params})
            if not self._add_worker_thread(queue, items):
                break

        queue.join()

        return items
    
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
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,ItemCounts"
            )
        }
        return self.doUtils.downloadUrl("{server}/emby/Users/{UserId}/Items?format=json", parameters=params)
    
    def getTvChannels(self):
        
        params = {

            'EnableImages': True,
            'Fields': (

                "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,ItemCounts"
            )
        }
        url = "{server}/emby/LiveTv/Channels/?userid={UserId}&format=json"
        return self.doUtils.downloadUrl(url, parameters=params)
    
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
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,ItemCounts"
            )
        }
        url = "{server}/emby/LiveTv/Recordings/?userid={UserId}&format=json"
        return self.doUtils.downloadUrl(url, parameters=params)
    
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
            'LocationTypes': "FileSystem,Remote,Offline",
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'IsMissing': False,
            'Recursive': True,
            'Limit': 1
        }
        try:
            result = self.doUtils.downloadUrl(url, parameters=params)
            total = result['TotalRecordCount']
            items['TotalRecordCount'] = total
        except Exception as error: # Failed to retrieve
            log.debug("%s:%s Failed to retrieve the server response: %s", url, params, error)
        else:
            index = 0
            jump = self.limitIndex
            queue = Queue.Queue()

            while index < total:
                # Get items by chunk to increase retrieval speed at scale
                params = {

                    'ParentId': parentid,
                    'ArtistIds': artist_id,
                    'IncludeItemTypes': itemtype,
                    'CollapseBoxSetItems': False,
                    'IsVirtualUnaired': False,
                    'EnableTotalRecordCount': False,
                    'LocationTypes': "FileSystem,Remote,Offline",
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
                        "MediaSources,VoteCount,ItemCounts"
                    )
                queue.put({'url': url, 'params': params})
                if not self._add_worker_thread(queue, items['Items']):
                    break

                index += jump

                if dialog:
                    percentage = int((float(index) / float(total))*100)
                    dialog.update(percentage)

            queue.join()
            if dialog:
                dialog.update(100)

        return items

    def get_views(self, root=False):

        if not root:
            url = "{server}/emby/Users/{UserId}/Views?format=json"
        else: # Views ungrouped
            url = "{server}/emby/Users/{UserId}/Items?Sortby=SortName&format=json"

        return self.doUtils.downloadUrl(url)

    def getViews(self, mediatype="", root=False, sortedlist=False):
        # Build a list of user views
        views = []
        mediatype = mediatype.lower()

        try:
            items = self.get_views(root)['Items']
        except Exception as error:
            log.debug("Error retrieving views for type: %s error:%s" % (mediatype, error))
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

        params = {

            'ParentId': parentid,
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'LocationTypes': "FileSystem,Remote,Offline",
            'IsMissing': False,
            'Recursive': True,
            'Ids': itemid
        }
        try:
            result = self.doUtils.downloadUrl("{server}/emby/Users/{UserId}/Items?format=json", parameters=params)
            total = result['TotalRecordCount']
        except Exception as error:
            # Something happened to the connection
            log.info("Error getting item count: " + str(error))
            return False

        return True if total else False

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

        try:
            result = self.doUtils.downloadUrl(url, parameters=params)
        except Exception as error:
            log.info("Error getting Seasons form server: " + str(error))
            result = None

        if result is not None:
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
        try:
            result = self.doUtils.downloadUrl(url, parameters=params)
            total = result['TotalRecordCount']
            items['TotalRecordCount'] = total
        except Exception as error: # Failed to retrieve
            log.debug("%s:%s Failed to retrieve the server response: %s", url, params, error)
        else:
            index = 0
            jump = self.limitIndex
            queue = Queue.Queue()

            while index < total:
                # Get items by chunk to increase retrieval speed at scale
                params = {

                    'ParentId': parent_id,
                    'Recursive': True,
                    'IsVirtualUnaired': False,
                    'EnableTotalRecordCount': False,
                    'LocationTypes': "FileSystem,Remote,Offline",
                    'IsMissing': False,
                    'StartIndex': index,
                    'Limit': jump,
                    'SortBy': "SortName",
                    'SortOrder': "Ascending",
                    'Fields': (

                        "Etag,Genres,SortName,Studios,Writer,ProductionYear,"
                        "CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,"
                        "AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts"
                    )
                }
                queue.put({'url': url, 'params': params})
                if not self._add_worker_thread(queue, items['Items']):
                    break

                index += jump

                if dialog:
                    percentage = int((float(index) / float(total))*100)
                    dialog.update(percentage)

            queue.join()
            if dialog:
                dialog.update(100)

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

        try:
            result = self.doUtils.downloadUrl(url)
        except Exception as error:
            log.info("Error getting additional parts form server: " + str(error))
            result = None

        if result is not None:
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
        doUtils = self.doUtils.downloadUrl

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
        self.doUtils.downloadUrl(url, postBody=params, action_type="POST")

    def deleteItem(self, itemid):

        url = "{server}/emby/Items/%s?format=json" % itemid
        self.doUtils.downloadUrl(url, action_type="DELETE")

    def getUsers(self, server):

        url = "%s/emby/Users/Public?format=json" % server
        try:
            users = self.doUtils.downloadUrl(url, authenticate=False)
        except Exception as error:
            log.info("Error getting users from server: " + str(error))
            users = []

        return users

    def loginUser(self, server, username, password=None):

        password = password or ""
        url = "%s/emby/Users/AuthenticateByName?format=json" % server
        data = {'username': username, 'password': hashlib.sha1(password).hexdigest()}
        user = self.doUtils.downloadUrl(url, postBody=data, action_type="POST", authenticate=False)

        return user

    def get_single_item(self, media_type, parent_id):

        params = {
            'ParentId': parent_id,
            'Recursive': True,
            'Limit': 1,
            'IncludeItemTypes': media_type
        }
        url = self.get_emby_url('Users/{UserId}/Items?format=json')
        return self.doUtils.downloadUrl(url, parameters=params)

    # NEW CODE ----------------------------------------------------

    @classmethod
    def _get_full_details(cls, params):
        params.update({
            'Fields': (

                "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
                "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
                "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
                "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
                "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
                "MediaSources,VoteCount,ItemCounts"
            )
        })
        return params

    def get_parent_child(self, parent_id, media_format=None):

        url = self.get_emby_url('Users/{UserId}/Items')
        params = {
            'SortBy': "SortName",
            'SortOrder': "Ascending",
            'IncludeItemTypes': media_format,
            'Recursive': True,
            'Limit': 1,
            'ParentId': parent_id
        }
        result = self.doUtils.downloadUrl(url, parameters=params)
        params['Limit'] = self.limitIndex
        params = self._get_full_details(params)

        index = 0
        while index < result['TotalRecordCount']:
            params['StartIndex'] = index
            yield self.doUtils.downloadUrl(url, parameters=params)

            index += self.limitIndex

    def get_view_options(self, view_id):

        url = self.get_emby_url('Library/VirtualFolders')
        for library in self.doUtils.downloadUrl(url):
            if library['ItemId'] == view_id:
                return library['LibraryOptions']

    def get_server_transcoding_settings(self):
        return self.doUtils.downloadUrl(self.get_emby_url('System/Configuration/encoding'))

    def get_intros(self, item_id):
        return self.doUtils.downloadUrl(self.get_emby_url('Users/{UserId}/Items/%s/Intros' % item_id))

    def get_additional_parts(self, item_id):
        return self.doUtils.downloadUrl(self.get_emby_url('Videos/%s/AdditionalParts' % item_id))

    def get_playback_info(self, item_id, profile, offset=0, audio=None, subtitles=None):

        url = self.get_emby_url('Items/%s/PlaybackInfo' % item_id)
        return self.doUtils.downloadUrl(url, action_type="POST", postBody={ 

            'UserId': self.userId,
            'DeviceProfile': profile,
            'StartTimeTicks': offset, #TODO
            'AudioStreamIndex': audio, #TODO
            'SubtitleStreamIndex': subtitles, #TODO
            'MediaSourceId': None, 
            'LiveStreamId': None 
        })

    def get_live_stream(self, item_id, profile, session_id, token, offset=0, audio=None, subtitles=None):

        url = self.get_emby_url('/LiveStreams/Open')
        return self.doUtils.downloadUrl(url, action_type="POST", postBody={

            'UserId': self.userId,
            'DeviceProfile': profile,
            'ItemId': item_id,
            'PlaySessionId': session_id,
            'OpenToken': token,
            'StartTimeTicks': offset, #TODO
            'AudioStreamIndex': audio, #TODO
            'SubtitleStreamIndex': subtitles #TODO
        })
