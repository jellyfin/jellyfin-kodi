# -*- coding: utf-8 -*-


''' The goal is to reduce memory usage.
    Generators to prevent having to hold all the info in memory
    while downloading from emby servers.

    Working with json, so we can resume where we left off.
'''
#################################################################################################

import json
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
limit = min(int(settings('limitIndex')), 50)
do = downloadutils.DownloadUtils()

#################################################################################################

def get_embyserver_url(handler):
    return  "{server}/emby/%s" % handler

def basic_info():
    return  "Etag"

def complete_info():
    return  (
        "Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,"
        "CommunityRating,OfficialRating,CumulativeRunTimeTicks,"
        "Metascore,AirTime,DateCreated,MediaStreams,People,Overview,"
        "CriticRating,CriticRatingSummary,Etag,ShortOverview,ProductionLocations,"
        "Tags,ProviderIds,ParentId,RemoteTrailers,SpecialEpisodeNumbers,"
        "MediaSources,VoteCount,ItemCounts"
    )

def _http(action, url, request={}):
    #request.update({'type': action, 'url': url})
    #return  HTTP.request_url(request)

    return do.downloadUrl(url, action_type=action, parameters=request['params'])

def _get(handler, params=None):
    return  _http("GET", get_embyserver_url(handler), {'params': params})

def _post(handler, json=None, params=None):
    return  _http("POST", get_embyserver_url(handler), {'params': params, 'json': json})

def _delete(handler, params=None):
    return  _http("DELETE", get_embyserver_url(handler), {'params': params})


def emby_session(handler="", params=None, action="GET", json=None):

    if action == "POST":
        return _post("Sessions%s" % handler, json, params)
    elif action == "DELETE":
        return _delete("Sessions%s" % handler, params)
    else:
        return _get("Sessions%s" % handler, params)

def user(handler="", params=None, action="GET", json=None):

    if action == "POST":
        return _post("Users/{UserId}%s" % handler, json, params)
    elif action == "DELETE":
        return  _delete(session, "Users/{UserId}%s" % handler, params)
    else:
        return _get(session, "Users/{UserId}%s" % handler, params)

def item(handler="", params=None):
    return  user("/Items%s" % handler, params)

def show(handler, params):
    return  _get("Shows%s" % handler, params)

#################################################################################################

# Single result functions

#################################################################################################

def get_item(item_id, fields=None):
    return  item(params={
                'Ids': item_id,
                'EnableTotalRecordCount': False,
                'Fields': fields
            })

def get_seasons(self, show_id):
    return  show("/%s/Seasons?UserId={UserId}" % show_id, {
                'IsVirtualUnaired': False,
                'Fields': "Etag"
            })

#################################################################################################

# Multiple calls to get multiple items (Generator)

''' This should help with memory issues.
    for items in generator(...):
        #do something

    If all items are required at once:
    a = (items['Items'] for items in generator(...))
'''

#################################################################################################

def get_all(generator):

    items = []
    for item in generator:
        items.extend(item['Items'])

    return items

def get_items(parent_id, item_type=None, basic=False, params=None):

    query = {
        'url': "Users/{UserId}/Items",
        'params': {
            'ParentId': parent_id,
            'IncludeItemTypes': item_type,
            'SortBy': "SortName",
            'SortOrder': "Ascending",
            'Fields': basic_info() if basic else complete_info()
        }
    }

    if params:
        query['params'].update(params)

    for items in _get_items(query):
        yield items

def get_item_list(item_list, basic=False):

    for item_ids in _split_list(item_list, limit):
        query = {
            'url': "Users/{UserId}/Items",
            'params': {
                "Ids": ",".join(item_ids),
                'Fields': basic_info() if basic else complete_info()
            }
        }
        for items in _get_items(query):
            yield items

def get_artists(parent_id=None):

    query = {
        'url': "Artists?UserId={UserId}",
        'params': {
            'ParentId': parent_id,
            'SortBy': "SortName",
            'SortOrder': "Ascending",
            'Fields': (
                "Etag,Genres,SortName,Studios,Writer,ProductionYear,"
                "CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,"
                "AirTime,DateCreated,MediaStreams,People,ProviderIds,Overview,ItemCounts"
            )
        }
    }
    for items in _get_items(query):
        yield items

def get_albums_by_artist(artist_id):

    params = {
        'SortBy': "DateCreated",
        'ArtistIds': artist_id
    }
    for items in get_items(None, "MusicAlbum", params=params):
        yield items

def sortby_mediatype(item_ids):

    sorted_items = {}

    items = get_all(get_item_list(item_ids))
    for item in items:

        mediatype = item.get('Type')
        if mediatype:
            sorted_items.setdefault(mediatype, []).append(item)

    return sorted_items


def _split_list(item_list, size):
    # Split up list in pieces of size. Will generate a list of lists
    return [item_list[i:i + size] for i in range(0, len(item_list), size)]

def _get_items(query):

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
    params.update({
        'CollapseBoxSetItems': False,
        'IsVirtualUnaired': False,
        'EnableTotalRecordCount': False,
        'LocationTypes': "FileSystem,Remote,Offline",
        'IsMissing': False,
        'Recursive': True
    })

    try:
        test_params = dict(params)
        test_params['Limit'] = 1
        test_params['EnableTotalRecordCount'] = True

        items['TotalRecordCount'] = _get(url, test_params)['TotalRecordCount']

    except Exception as error:
        log.error("Failed to retrieve the server response %s: %s params:%s", url, error, params)

    else:
        index = params.get('StartIndex', 0)
        total = items['TotalRecordCount']

        while index < total:

            params['StartIndex'] = index
            params['Limit'] = limit
            result = _get(url, params)

            items['Items'].extend(result['Items'])
            items['RestorePoint'] = query
            yield items

            del items['Items'][:]
            index += limit

