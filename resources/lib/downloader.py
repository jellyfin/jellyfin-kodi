# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import Queue
import threading
import os
from datetime import datetime

import xbmc
import xbmcvfs
import xbmcaddon

import requests
from helper.utils import should_stop, delete_folder
from helper import settings, stop, event, window, kodi_version, unzip, create_id
from emby import Emby
from emby.core import api
from emby.core.exceptions import HTTPException

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
LIMIT = min(int(settings('limitIndex') or 50), 50)
CACHE = xbmc.translatePath(os.path.join(xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('profile').decode('utf-8'), 'emby')).decode('utf-8')

#################################################################################################

def get_embyserver_url(handler):

    if handler.startswith('/'):

        handler = handler[1:]
        LOG.warn("handler starts with /: %s", handler)

    return  "{server}/emby/%s" % handler

def browse_info():
    return  (  
                "DateCreated,EpisodeCount,SeasonCount,Path,Genres,Studios,Taglines,MediaStreams,Overview,Etag,"
                "ProductionLocations,Width,Height,RecursiveItemCount,ChildCount"
            )

def _http(action, url, request={}, server_id=None):
    request.update({'url': url, 'type': action})
    
    return Emby(server_id)['http/request'](request)

def _get(handler, params=None, server_id=None):
    return  _http("GET", get_embyserver_url(handler), {'params': params}, server_id)

def _post(handler, json=None, params=None, server_id=None):
    return  _http("POST", get_embyserver_url(handler), {'params': params, 'json': json}, server_id)

def _delete(handler, params=None, server_id=None):
    return  _http("DELETE", get_embyserver_url(handler), {'params': params}, server_id)

def validate_view(library_id, item_id):

    ''' This confirms a single item from the library matches the view it belongs to.
        Used to detect grouped libraries.
    '''
    try:
        result = _get("Users/{UserId}/Items", {
                    'ParentId': library_id,
                    'Recursive': True,
                    'Ids': item_id
                 })
    except Exception:
        return False

    return True if len(result['Items']) else False

def get_single_item(parent_id, media):
    return  _get("Users/{UserId}/Items", {
                'ParentId': parent_id,
                'Recursive': True,
                'Limit': 1,
                'IncludeItemTypes': media
            })

def get_filtered_section(parent_id=None, media=None, limit=None, recursive=None, sort=None, sort_order=None,
                         filters=None, extra=None, server_id=None):

    ''' Get dynamic listings.
    '''
    params = {
        'ParentId': parent_id,
        'IncludeItemTypes': media,
        'IsMissing': False,
        'Recursive': recursive if recursive is not None else True,
        'Limit': limit,
        'SortBy': sort or "SortName",
        'SortOrder': sort_order or "Ascending",
        'ImageTypeLimit': 1,
        'IsVirtualUnaired': False,
        'Fields': browse_info()
    }
    if filters:

        if 'Boxsets' in filters:

            filters.remove('Boxsets')
            params['CollapseBoxSetItems'] = settings('groupedSets.bool')

        params['Filters'] = ','.join(filters)

    if settings('getCast.bool'):
        params['Fields'] += ",People"

    if media and 'Photo' in media:
        params['Fields'] += ",Width,Height"

    if extra is not None:
        params.update(extra)

    return  _get("Users/{UserId}/Items", params, server_id)

def get_movies_by_boxset(boxset_id):

    for items in get_items(boxset_id, "Movie"):
        yield items

def get_episode_by_show(show_id):

    query = {
        'url': "Shows/%s/Episodes" % show_id,
        'params': {
            'EnableUserData': True, 
            'EnableImages': True, 
            'UserId': "{UserId}",
            'Fields': api.info()
        }
    }
    for items in _get_items(query):
        yield items

def get_episode_by_season(show_id, season_id):

    query = {
        'url': "Shows/%s/Episodes" % show_id,
        'params': {
            'SeasonId': season_id,
            'EnableUserData': True, 
            'EnableImages': True, 
            'UserId': "{UserId}",
            'Fields': api.info()
        }
    }
    for items in _get_items(query):
        yield items

def get_items(parent_id, item_type=None, basic=False, params=None):

    query = {
        'url': "Users/{UserId}/Items",
        'params': {
            'ParentId': parent_id,
            'IncludeItemTypes': item_type,
            'SortBy': "SortName",
            'SortOrder': "Ascending",
            'Fields': api.basic_info() if basic else api.info(),
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'EnableTotalRecordCount': False,
            'LocationTypes': "FileSystem,Remote,Offline",
            'IsMissing': False,
            'Recursive': True
        }
    }
    if params:
        query['params'].update(params)

    for items in _get_items(query):
        yield items

def get_artists(parent_id=None, basic=False, params=None, server_id=None):

    query = {
        'url': "Artists",
        'params': {
            'UserId': "{UserId}",
            'ParentId': parent_id,
            'SortBy': "SortName",
            'SortOrder': "Ascending",
            'Fields': api.basic_info() if basic else api.music_info(),
            'CollapseBoxSetItems': False,
            'IsVirtualUnaired': False,
            'EnableTotalRecordCount': False,
            'LocationTypes': "FileSystem,Remote,Offline",
            'IsMissing': False,
            'Recursive': True
        }
    }

    if params:
        query['params'].update(params)

    for items in _get_items(query, server_id):
        yield items

def get_albums_by_artist(artist_id, basic=False):

    params = {
        'SortBy': "DateCreated",
        'ArtistIds': artist_id
    }
    for items in get_items(None, "MusicAlbum", basic, params):
        yield items

def get_songs_by_artist(artist_id, basic=False):

    params = {
        'SortBy': "DateCreated",
        'ArtistIds': artist_id
    }
    for items in get_items(None, "Audio", basic, params):
        yield items

@stop()
def _get_items(query, server_id=None):

    ''' query = {
            'url': string,
            'params': dict -- opt, include StartIndex to resume
        }
    '''
    items = {
        'Items': [],
        'TotalRecordCount': 0,
        'RestorePoint': {}
    }

    url = query['url']
    params = query.get('params', {})

    try:
        test_params = dict(params)
        test_params['Limit'] = 1
        test_params['EnableTotalRecordCount'] = True

        items['TotalRecordCount'] = _get(url, test_params, server_id=server_id)['TotalRecordCount']

    except Exception as error:
        LOG.error("Failed to retrieve the server response %s: %s params:%s", url, error, params)

    else:
        index = params.get('StartIndex', 0)
        total = items['TotalRecordCount']

        while index < total:

            params['StartIndex'] = index
            params['Limit'] = LIMIT
            result = _get(url, params, server_id=server_id) or {'Items': []}
            
            items['Items'].extend(result['Items'])
            items['RestorePoint'] = query
            yield items

            del items['Items'][:]
            index += LIMIT

class GetItemWorker(threading.Thread):

    is_done = False

    def __init__(self, server, queue, output):

        self.server = server
        self.queue = queue
        self.output = output
        threading.Thread.__init__(self)

    def run(self):

        with requests.Session() as s:
            while True:

                try:
                    item_ids = self.queue.get(timeout=1)
                except Queue.Empty:

                    self.is_done = True
                    LOG.info("--<[ q:download/%s ]", id(self))

                    return

                request = {
                    'type': "GET",
                    'handler': "Users/{UserId}/Items",
                    'params': {
                        'Ids': ','.join(str(x) for x in item_ids),
                        'Fields': api.info()
                    }
                }

                try:
                    result = self.server['http/request'](request, s)

                    for item in result['Items']:

                        if item['Type'] in self.output:
                            self.output[item['Type']].put(item)
                except HTTPException as error:
                    LOG.error("--[ http status: %s ]", error.status)

                    if error.status == 'ServerUnreachable':
                        self.is_done = True

                        break

                except Exception as error:
                    LOG.exception(error)

                self.queue.task_done()

                if window('emby_should_stop.bool'):
                    break

class TheVoid(object):

    def __init__(self, method, data):

        ''' If you call get, this will block until response is received.
            This is used to communicate between entrypoints.
        '''
        if type(data) != dict:
            raise Exception("unexpected data format")

        data['VoidName'] = str(create_id())
        LOG.info("---[ contact MU-TH-UR 6000/%s ]", method)
        LOG.debug(data)

        event(method, data)
        self.method = method
        self.data = data

    def get(self):

        while True:

            response = window('emby_%s.json' % self.data['VoidName'])

            if response != "":

                LOG.debug("--<[ nostromo/emby_%s.json ]", self.data['VoidName'])
                window('emby_%s' % self.data['VoidName'], clear=True)

                return response

            if window('emby_should_stop.bool'):
                LOG.info("Abandon mission! A black hole just swallowed [ %s/%s ]", self.method, self.data['VoidName'])
                
                return

            xbmc.sleep(100)
            LOG.info("--[ void/%s ]", self.data['VoidName'])

def get_objects(src, filename):

    ''' Download objects dependency to temp cache folder.
    '''
    temp = CACHE
    restart = not xbmcvfs.exists(os.path.join(temp, "objects") + '/')
    path = os.path.join(temp, filename).encode('utf-8')

    if restart and (settings('appliedPatch') or "") == filename:

        LOG.warn("Something went wrong applying this patch %s previously.", filename)
        restart = False

    if not xbmcvfs.exists(path) or filename.startswith('DEV'):
        delete_folder(CACHE)

        LOG.info("From %s to %s", src, path.decode('utf-8'))
        try:
            response = requests.get(src, stream=True, verify=True)
            response.raise_for_status()
        except requests.exceptions.SSLError as error:

            LOG.error(error)
            response = requests.get(src, stream=True, verify=False)
        except Exception as error:
            raise

        dl = xbmcvfs.File(path, 'w')
        dl.write(response.content)
        dl.close()
        del response

        settings('appliedPatch', filename)

    unzip(path, temp, "objects")

    return restart
