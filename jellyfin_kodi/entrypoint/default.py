# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import sys
import os

from six import iteritems
from six.moves.urllib.parse import parse_qsl, urlencode
from kodi_six import xbmc, xbmcvfs, xbmcgui, xbmcplugin, xbmcaddon

from .. import client
from ..database import reset, get_sync, Database, jellyfin_db, get_credentials
from ..objects import Objects, Actions
from ..helper import translate, event, settings, window, dialog, api, JSONRPC, LazyLogger
from ..helper.utils import JsonDebugPrinter, translate_path, kodi_version
from ..jellyfin import Jellyfin

#################################################################################################

LOG = LazyLogger(__name__)

ADDON_BASE_URL = sys.argv[0]
try:
    PROCESS_HANDLE = int(sys.argv[1])
    QUERY_STRING = sys.argv[2]
except IndexError:
    pass

#################################################################################################


class Events(object):

    def __init__(self):

        ''' Parse the parameters. Reroute to our service.py
            where user is fully identified already.
        '''
        base_url = ADDON_BASE_URL
        path = QUERY_STRING

        try:
            params = dict(parse_qsl(path[1:]))
        except Exception:
            params = {}

        mode = params.get('mode')
        server = params.get('server')

        if server == 'None':
            server = None

        jellyfin_client = Jellyfin(server).get_client()
        api_client = jellyfin_client.jellyfin

        addon_data = translate_path("special://profile/addon_data/plugin.video.jellyfin/data.json")
        try:
            with open(addon_data, 'rb') as infile:
                data = json.load(infile)

            server_data = data['Servers'][0]
            api_client.config.data['auth.server'] = server_data.get('address')
            api_client.config.data['auth.server-name'] = server_data.get('Name')
            api_client.config.data['auth.user_id'] = server_data.get('UserId')
            api_client.config.data['auth.token'] = server_data.get('AccessToken')
        except Exception as e:
            LOG.warning('Addon appears to not be configured yet: {}'.format(e))

        LOG.info("path: %s params: %s", path, JsonDebugPrinter(params))

        if '/extrafanart' in base_url:

            jellyfin_path = path[1:]
            jellyfin_id = params.get('id')
            get_fanart(jellyfin_id, jellyfin_path, server, api_client)

        elif '/Extras' in base_url or '/VideoFiles' in base_url:

            jellyfin_path = path[1:]
            jellyfin_id = params.get('id')
            get_video_extras(jellyfin_id, jellyfin_path, server, api_client)

        elif mode == 'play':

            item = api_client.get_item(params['id'])
            item["resumePlayback"] = sys.argv[3].split(":")[1] == "true"
            Actions(server, api_client).play(item, params.get('dbid'), params.get('transcode') == 'true', playlist=params.get('playlist') == 'true')

        elif mode == 'playlist':
            api_client.post_session(api_client.config.data['app.session'], "Playing", {
                'PlayCommand': "PlayNow",
                'ItemIds': params['id'],
                'StartPositionTicks': 0
            })
        elif mode == 'deviceid':
            client.reset_device_id()
        elif mode == 'reset':
            reset()
        elif mode == 'delete':
            delete_item()
        elif mode == 'refreshboxsets':
            event('SyncLibrary', {'Id': "Boxsets:Refresh"})
        elif mode == 'nextepisodes':
            get_next_episodes(params['id'], params['limit'])
        elif mode == 'browse':
            browse(params.get('type'), params.get('id'), params.get('folder'), server, api_client)
        elif mode == 'synclib':
            event('SyncLibrary', {'Id': params.get('id')})
        elif mode == 'updatelib':
            event('SyncLibrary', {'Id': params.get('id'), 'Update': True})
        elif mode == 'repairlib':
            event('RepairLibrary', {'Id': params.get('id')})
        elif mode == 'removelib':
            event('RemoveLibrary', {'Id': params.get('id')})
        elif mode == 'repairlibs':
            event('RepairLibrarySelection')
        elif mode == 'updatelibs':
            event('SyncLibrarySelection')
        elif mode == 'removelibs':
            event('RemoveLibrarySelection')
        elif mode == 'addlibs':
            event('AddLibrarySelection')
        elif mode == 'addserver':
            event('AddServer')
        elif mode == 'login':
            event('ServerConnect', {'Id': server})
        elif mode == 'removeserver':
            event('RemoveServer', {'Id': server})
        elif mode == 'settings':
            xbmc.executebuiltin('Addon.OpenSettings(plugin.video.jellyfin)')
        elif mode == 'adduser':
            add_user(api_client)
        elif mode == 'updatepassword':
            event('UpdatePassword')
        elif mode == 'thememedia':
            get_themes(api_client)
        elif mode == 'managelibs':
            manage_libraries()
        elif mode == 'backup':
            backup()
        elif mode == 'restartservice':
            window('jellyfin.restart.bool', True)
        elif mode is None and not params and base_url != 'plugin://plugin.video.jellyfin/':
            # Used when selecting "Browse" from a context menu, see #548
            item_id = base_url.strip('/').split('/')[-1]
            browse('', item_id, None, server, api_client)
        else:
            listing()


def listing():

    ''' Display all jellyfin nodes and dynamic entries when appropriate.
    '''
    total = int(window('Jellyfin.nodes.total') or 0)
    sync = get_sync()
    whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
    servers = get_credentials()['Servers'][1:]

    for i in range(total):

        window_prop = "Jellyfin.nodes.%s" % i
        path = window('%s.index' % window_prop)

        if not path:
            path = window('%s.content' % window_prop) or window('%s.path' % window_prop)

        label = window('%s.title' % window_prop)
        node = window('%s.type' % window_prop)
        artwork = window('%s.artwork' % window_prop)
        view_id = window('%s.id' % window_prop)
        context = []

        if view_id and node in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed') and view_id not in whitelist:
            label = "%s %s" % (label, translate(33166))
            context.append((translate(33123), "RunPlugin(plugin://plugin.video.jellyfin/?mode=synclib&id=%s)" % view_id))

        if view_id and node in ('movies', 'tvshows', 'musicvideos', 'music') and view_id in whitelist:

            context.append((translate(33136), "RunPlugin(plugin://plugin.video.jellyfin/?mode=updatelib&id=%s)" % view_id))
            context.append((translate(33132), "RunPlugin(plugin://plugin.video.jellyfin/?mode=repairlib&id=%s)" % view_id))
            context.append((translate(33133), "RunPlugin(plugin://plugin.video.jellyfin/?mode=removelib&id=%s)" % view_id))

        LOG.debug("--[ listing/%s/%s ] %s", node, label, path)

        if path:
            directory(label, path, artwork=artwork, context=context)

    for server in servers:
        context = []

        if server.get('ManualAddress'):
            context.append((translate(33141), "RunPlugin(plugin://plugin.video.jellyfin/?mode=removeserver&server=%s)" % server['Id']))

        if 'AccessToken' not in server:
            directory("%s (%s)" % (server['Name'], translate(30539)), "plugin://plugin.video.jellyfin/?mode=login&server=%s" % server['Id'], False, context=context)
        else:
            directory(server['Name'], "plugin://plugin.video.jellyfin/?mode=browse&server=%s" % server['Id'], context=context)

    directory(translate(33194), "plugin://plugin.video.jellyfin/?mode=managelibs", True)
    directory(translate(33134), "plugin://plugin.video.jellyfin/?mode=addserver", False)
    directory(translate(33054), "plugin://plugin.video.jellyfin/?mode=adduser", False)
    directory(translate(5), "plugin://plugin.video.jellyfin/?mode=settings", False)
    directory(translate(33161), "plugin://plugin.video.jellyfin/?mode=updatepassword", False)
    directory(translate(33058), "plugin://plugin.video.jellyfin/?mode=reset", False)
    directory(translate(33180), "plugin://plugin.video.jellyfin/?mode=restartservice", False)

    if settings('backupPath'):
        directory(translate(33092), "plugin://plugin.video.jellyfin/?mode=backup", False)

    xbmcplugin.setContent(PROCESS_HANDLE, 'files')
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def directory(label, path, folder=True, artwork=None, fanart=None, context=None):

    ''' Add directory listitem. context should be a list of tuples [(label, action)*]
    '''
    li = dir_listitem(label, path, artwork, fanart)

    if context:
        li.addContextMenuItems(context)

    xbmcplugin.addDirectoryItem(PROCESS_HANDLE, path, li, folder)

    return li


def dir_listitem(label, path, artwork=None, fanart=None):

    ''' Gets the icon paths for default node listings
    '''
    li = xbmcgui.ListItem(label, path=path)
    li.setArt({
        "thumb": artwork or "special://home/addons/plugin.video.jellyfin/resources/icon.png",
        "fanart": fanart or "special://home/addons/plugin.video.jellyfin/resources/fanart.png",
        "landscape": artwork or fanart or "special://home/addons/plugin.video.jellyfin/resources/fanart.png",
    })

    return li


def manage_libraries():

    directory(translate(33098), "plugin://plugin.video.jellyfin/?mode=refreshboxsets", False)
    directory(translate(33154), "plugin://plugin.video.jellyfin/?mode=addlibs", False)
    directory(translate(33139), "plugin://plugin.video.jellyfin/?mode=updatelibs", False)
    directory(translate(33140), "plugin://plugin.video.jellyfin/?mode=repairlibs", False)
    directory(translate(33184), "plugin://plugin.video.jellyfin/?mode=removelibs", False)
    directory(translate(33060), "plugin://plugin.video.jellyfin/?mode=thememedia", False)

    xbmcplugin.setContent(PROCESS_HANDLE, 'files')
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def browse(media, view_id=None, folder=None, server_id=None, api_client=None):

    ''' Browse content dynamically.
    '''
    LOG.info("--[ v:%s/%s ] %s", view_id, media, folder)

    if not window('jellyfin_online.bool') and server_id is None:

        monitor = xbmc.Monitor()

        for _i in range(300):
            if window('jellyfin_online.bool'):
                break
            elif monitor.waitForAbort(0.1):
                return
        else:
            LOG.error("Default server is not online.")

            return

    folder = folder.lower() if folder else None

    if folder is None and media in ('homevideos', 'movies', 'books', 'audiobooks'):
        return browse_subfolders(media, view_id, server_id)

    if folder and folder == 'firstletter':
        return browse_letters(media, view_id, server_id)

    if view_id:

        view = api_client.get_item(view_id)
        xbmcplugin.setPluginCategory(PROCESS_HANDLE, view['Name'])

    content_type = "files"

    if media in ('tvshows', 'seasons', 'episodes', 'movies', 'musicvideos', 'songs', 'albums'):
        content_type = media
    elif media in ('homevideos', 'photos'):
        content_type = "images"
    elif media in ('books', 'audiobooks'):
        content_type = "videos"
    elif media == 'music':
        content_type = "artists"

    if folder == 'recentlyadded':
        listing = api_client.get_recently_added(None, view_id, None)
    elif folder == 'genres':
        listing = api_client.get_genres(view_id)
    elif media == 'livetv':
        listing = api_client.get_channels()
    elif folder == 'unwatched':
        listing = get_filtered_section(view_id, None, None, None, None, None, ['IsUnplayed'], None, server_id, api_client)
    elif folder == 'favorite':
        listing = get_filtered_section(view_id, None, None, None, None, None, ['IsFavorite'], None, server_id, api_client)
    elif folder == 'inprogress':
        listing = get_filtered_section(view_id, None, None, None, None, None, ['IsResumable'], None, server_id, api_client)
    elif folder == 'boxsets':
        listing = get_filtered_section(view_id, get_media_type('boxsets'), None, True, None, None, None, None, server_id, api_client)
    elif folder == 'random':
        listing = get_filtered_section(view_id, get_media_type(content_type), 25, True, "Random", None, None, None, server_id, api_client)
    elif (folder or "").startswith('firstletter-'):
        listing = get_filtered_section(view_id, get_media_type(content_type), None, None, None, None, None, {'NameStartsWith': folder.split('-')[1]}, server_id, api_client)
    elif (folder or "").startswith('genres-'):
        listing = get_filtered_section(view_id, get_media_type(content_type), None, None, None, None, None, {'GenreIds': folder.split('-')[1]}, server_id, api_client)
    elif folder == 'favepisodes':
        listing = get_filtered_section(None, get_media_type(content_type), 25, None, None, None, ['IsFavorite'], None, server_id, api_client)
    elif folder and media == 'playlists':
        listing = get_filtered_section(folder, get_media_type(content_type), None, False, 'None', None, None, None, server_id, api_client)
    elif media == 'homevideos':
        listing = get_filtered_section(folder or view_id, get_media_type(content_type), None, False, None, None, None, None, server_id, api_client)
    elif media in ['movies', 'episodes']:
        listing = get_filtered_section(folder or view_id, get_media_type(content_type), None, True, None, None, None, None, server_id, api_client)
    elif media in ('boxset', 'library'):
        listing = get_filtered_section(folder or view_id, None, None, True, None, None, None, None, server_id, api_client)
    elif media == 'boxsets':
        listing = get_filtered_section(folder or view_id, None, None, False, None, None, ['Boxsets'], None, server_id, api_client)
    elif media == 'tvshows':
        listing = get_filtered_section(folder or view_id, get_media_type(content_type), None, True, None, None, None, None, server_id, api_client)
    elif media == 'seasons':
        listing = api_client.get_seasons(folder)
    elif media != 'files':
        listing = get_filtered_section(folder or view_id, get_media_type(content_type), None, False, None, None, None, None, server_id, api_client)
    else:
        listing = get_filtered_section(folder or view_id, None, None, False, None, None, None, None, server_id, api_client)

    if listing:

        actions = Actions(server_id, api_client)
        list_li = []
        listing = listing if type(listing) == list else listing.get('Items', [])

        for item in listing:

            li = xbmcgui.ListItem()
            li.setProperty('jellyfinid', item['Id'])
            li.setProperty('jellyfinserver', server_id)
            actions.set_listitem(item, li)

            if item.get('IsFolder'):

                params = {
                    'id': view_id or item['Id'],
                    'mode': "browse",
                    'type': get_folder_type(item, media) or media,
                    'folder': item['Id'],
                    'server': server_id
                }
                path = "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))
                context = []

                if item['Type'] in ('Series', 'Season', 'Playlist'):
                    context.append(("Play", "RunPlugin(plugin://plugin.video.jellyfin/?mode=playlist&id=%s&server=%s)" % (item['Id'], server_id)))

                if item['UserData']['Played']:
                    context.append((translate(16104), "RunPlugin(plugin://plugin.video.jellyfin/?mode=unwatched&id=%s&server=%s)" % (item['Id'], server_id)))
                else:
                    context.append((translate(16103), "RunPlugin(plugin://plugin.video.jellyfin/?mode=watched&id=%s&server=%s)" % (item['Id'], server_id)))

                li.addContextMenuItems(context)
                list_li.append((path, li, True))

            elif item['Type'] == 'Genre':

                params = {
                    'id': view_id or item['Id'],
                    'mode': "browse",
                    'type': get_folder_type(item, media) or media,
                    'folder': 'genres-%s' % item['Id'],
                    'server': server_id
                }
                path = "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))
                list_li.append((path, li, True))

            else:
                if item['Type'] not in ('Photo', 'PhotoAlbum'):
                    params = {
                        'id': item['Id'],
                        'mode': "play",
                        'server': server_id
                    }
                    path = "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))
                    li.setProperty('path', path)
                    context = [(translate(13412), "RunPlugin(plugin://plugin.video.jellyfin/?mode=playlist&id=%s&server=%s)" % (item['Id'], server_id))]

                    if item['UserData']['Played']:
                        context.append((translate(16104), "RunPlugin(plugin://plugin.video.jellyfin/?mode=unwatched&id=%s&server=%s)" % (item['Id'], server_id)))
                    else:
                        context.append((translate(16103), "RunPlugin(plugin://plugin.video.jellyfin/?mode=watched&id=%s&server=%s)" % (item['Id'], server_id)))

                    li.addContextMenuItems(context)

                list_li.append((li.getProperty('path'), li, False))

        xbmcplugin.addDirectoryItems(PROCESS_HANDLE, list_li, len(list_li))

    if content_type == 'images':
        xbmcplugin.addSortMethod(PROCESS_HANDLE, xbmcplugin.SORT_METHOD_VIDEO_TITLE)
        xbmcplugin.addSortMethod(PROCESS_HANDLE, xbmcplugin.SORT_METHOD_DATE)
        xbmcplugin.addSortMethod(PROCESS_HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RATING)
        xbmcplugin.addSortMethod(PROCESS_HANDLE, xbmcplugin.SORT_METHOD_VIDEO_RUNTIME)

    xbmcplugin.setContent(PROCESS_HANDLE, content_type)
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def browse_subfolders(media, view_id, server_id=None):

    ''' Display submenus for jellyfin views.
    '''
    from ..views import DYNNODES

    view = Jellyfin(server_id).get_client().jellyfin.get_item(view_id)
    xbmcplugin.setPluginCategory(PROCESS_HANDLE, view['Name'])
    nodes = DYNNODES[media]

    for node in nodes:

        params = {
            'id': view_id,
            'mode': "browse",
            'type': media,
            'folder': view_id if node[0] == 'all' else node[0],
            'server': server_id
        }
        path = "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))
        directory(node[1] or view['Name'], path)

    xbmcplugin.setContent(PROCESS_HANDLE, 'files')
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def browse_letters(media, view_id, server_id=None):

    ''' Display letters as options.
    '''
    letters = "#ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    view = Jellyfin(server_id).get_client().jellyfin.get_item(view_id)
    xbmcplugin.setPluginCategory(PROCESS_HANDLE, view['Name'])

    for node in letters:

        params = {
            'id': view_id,
            'mode': "browse",
            'type': media,
            'folder': 'firstletter-%s' % node,
            'server': server_id
        }
        path = "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))
        directory(node, path)

    xbmcplugin.setContent(PROCESS_HANDLE, 'files')
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def get_folder_type(item, content_type=None):

    media = item['Type']

    if media == 'Series':
        return "seasons"
    elif media == 'Season':
        return "episodes"
    elif media == 'BoxSet':
        return "boxset"
    elif media == 'MusicArtist':
        return "albums"
    elif media == 'MusicAlbum':
        return "songs"
    elif media == 'CollectionFolder':
        return item.get('CollectionType', 'library')
    elif media == 'Folder' and content_type == 'music':
        return "albums"


def get_media_type(media):

    if media == 'movies':
        return "Movie,BoxSet"
    elif media == 'homevideos':
        return "Video,Folder,PhotoAlbum,Photo"
    elif media == 'episodes':
        return "Episode"
    elif media == 'boxsets':
        return "BoxSet"
    elif media == 'tvshows':
        return "Series"
    elif media == 'music':
        return "MusicArtist,MusicAlbum,Audio"


def get_fanart(item_id, path, server_id=None, api_client=None):

    ''' Get extra fanart for listitems. This is called by skinhelper.
        Images are stored locally, due to the Kodi caching system.
    '''
    if not item_id and 'plugin.video.jellyfin' in path:
        item_id = path.split('/')[-2]

    if not item_id:
        return

    LOG.info("[ extra fanart ] %s", item_id)
    objects = Objects()
    list_li = []
    directory = translate_path("special://thumbnails/jellyfin/%s/" % item_id)

    if not xbmcvfs.exists(directory):

        xbmcvfs.mkdirs(directory)
        item = api_client.get_item(item_id)
        obj = objects.map(item, 'Artwork')
        backdrops = api.API(item).get_all_artwork(obj)
        tags = obj['BackdropTags']

        for index, backdrop in enumerate(backdrops):

            tag = tags[index]
            fanart = os.path.join(directory, "fanart%s.jpg" % tag)
            li = xbmcgui.ListItem(tag, path=fanart)
            xbmcvfs.copy(backdrop, fanart)
            list_li.append((fanart, li, False))
    else:
        LOG.debug("cached backdrop found")
        dirs, files = xbmcvfs.listdir(directory)

        for file in files:
            fanart = os.path.join(directory, file)
            li = xbmcgui.ListItem(file, path=fanart)
            list_li.append((fanart, li, False))

    xbmcplugin.addDirectoryItems(PROCESS_HANDLE, list_li, len(list_li))
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def get_video_extras(item_id, path, server_id=None, api_client=None):

    ''' Returns the video files for the item as plugin listing, can be used
        to browse actual files or video extras, etc.
    '''
    if not item_id and 'plugin.video.jellyfin' in path:
        item_id = path.split('/')[-2]

    if not item_id:
        return

    # TODO implement????
    # Jellyfin(server_id).get_client().jellyfin.get_item(item_id)

    """
    def getVideoFiles(jellyfinId,jellyfinPath):
        #returns the video files for the item as plugin listing, can be used for browsing the actual files or videoextras etc.
        jellyfin = jellyfinserver.Read_JellyfinServer()
        if not jellyfinId:
            if "plugin.video.jellyfin" in jellyfinPath:
                jellyfinId = jellyfinPath.split("/")[-2]
        if jellyfinId:
            item = jellyfin.getItem(jellyfinId)
            putils = playutils.PlayUtils(item)
            if putils.isDirectPlay():
                #only proceed if we can access the files directly. TODO: copy local on the fly if accessed outside
                filelocation = putils.directPlay()
                if not filelocation.endswith("/"):
                    filelocation = filelocation.rpartition("/")[0]
                dirs, files = xbmcvfs.listdir(filelocation)
                for file in files:
                    file = filelocation + file
                    li = xbmcgui.ListItem(file, path=file)
                    xbmcplugin.addDirectoryItem(handle=PROCESS_HANDLE, url=file, listitem=li)
                for dir in dirs:
                    dir = filelocation + dir
                    li = xbmcgui.ListItem(dir, path=dir)
                    xbmcplugin.addDirectoryItem(handle=PROCESS_HANDLE, url=dir, listitem=li, isFolder=True)
        #xbmcplugin.endOfDirectory(PROCESS_HANDLE)
    """


def get_next_episodes(item_id, limit):

    ''' Only for synced content.
    '''
    with Database('jellyfin') as jellyfindb:

        db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)
        library = db.get_view_name(item_id)

        if not library:
            return

    result = JSONRPC('VideoLibrary.GetTVShows').execute({
        'sort': {'order': "descending", 'method': "lastplayed"},
        'filter': {
            'and': [
                {'operator': "true", 'field': "inprogress", 'value': ""},
                {'operator': "is", 'field': "tag", 'value': "%s" % library}
            ]},
        'properties': ['title', 'studio', 'mpaa', 'file', 'art']
    })

    try:
        items = result['result']['tvshows']
    except (KeyError, TypeError):
        return

    list_li = []

    for item in items:
        if settings('ignoreSpecialsNextEpisodes.bool'):
            params = {
                'tvshowid': item['tvshowid'],
                'sort': {'method': "episode"},
                'filter': {
                    'and': [
                        {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                        {'operator': "greaterthan", 'field': "season", 'value': "0"}
                    ]},
                'properties': [
                    "title", "playcount", "season", "episode", "showtitle",
                    "plot", "file", "rating", "resume", "tvshowid", "art",
                    "streamdetails", "firstaired", "runtime", "writer",
                    "dateadded", "lastplayed"
                ],
                'limits': {"end": 1}
            }
        else:
            params = {
                'tvshowid': item['tvshowid'],
                'sort': {'method': "episode"},
                'filter': {'operator': "lessthan", 'field': "playcount", 'value': "1"},
                'properties': [
                    "title", "playcount", "season", "episode", "showtitle",
                    "plot", "file", "rating", "resume", "tvshowid", "art",
                    "streamdetails", "firstaired", "runtime", "writer",
                    "dateadded", "lastplayed"
                ],
                'limits': {"end": 1}
            }

        result = JSONRPC('VideoLibrary.GetEpisodes').execute(params)

        try:
            episodes = result['result']['episodes']
        except (KeyError, TypeError):
            pass
        else:
            for episode in episodes:

                li = create_listitem(episode)
                list_li.append((episode['file'], li))

        if len(list_li) == limit:
            break

    xbmcplugin.addDirectoryItems(PROCESS_HANDLE, list_li, len(list_li))
    xbmcplugin.setContent(PROCESS_HANDLE, 'episodes')
    xbmcplugin.endOfDirectory(PROCESS_HANDLE)


def create_listitem(item):

    ''' Listitem based on jsonrpc items.
    '''
    title = item['title']
    label2 = ""
    li = xbmcgui.ListItem(title)
    li.setProperty('IsPlayable', "true")

    metadata = {
        'Title': title,
        'duration': str(item['runtime'] / 60),
        'Plot': item['plot'],
        'Playcount': item['playcount']
    }

    if "showtitle" in item:
        metadata['TVshowTitle'] = item['showtitle']
        label2 = item['showtitle']

    if "episodeid" in item:
        # Listitem of episode
        metadata['mediatype'] = "episode"
        metadata['dbid'] = item['episodeid']

    # TODO: Review once Krypton is RC - probably no longer needed if there's dbid
    if "episode" in item:
        episode = item['episode']
        metadata['Episode'] = episode

    if "season" in item:
        season = item['season']
        metadata['Season'] = season

    if season and episode:
        episodeno = "s%.2de%.2d" % (season, episode)
        li.setProperty('episodeno', episodeno)
        label2 = "%s - %s" % (label2, episodeno) if label2 else episodeno

    if "firstaired" in item:
        metadata['Premiered'] = item['firstaired']

    if "rating" in item:
        metadata['Rating'] = str(round(float(item['rating']), 1))

    if "director" in item:
        metadata['Director'] = " / ".join(item['director'])

    if "writer" in item:
        metadata['Writer'] = " / ".join(item['writer'])

    if "cast" in item:
        cast = []
        castandrole = []
        for person in item['cast']:
            name = person['name']
            cast.append(name)
            castandrole.append((name, person['role']))
        metadata['Cast'] = cast
        metadata['CastAndRole'] = castandrole

    li.setLabel2(label2)
    li.setInfo(type="Video", infoLabels=metadata)
    li.setProperty('resumetime', str(item['resume']['position']))
    li.setProperty('totaltime', str(item['resume']['total']))
    li.setArt(item['art'])
    li.setProperty('dbid', str(item['episodeid']))
    li.setProperty('fanart_image', item['art'].get('tvshow.fanart', ''))

    for key, value in iteritems(item['streamdetails']):
        for stream in value:
            li.addStreamInfo(key, stream)

    return li


def add_user(api_client):

    ''' Add or remove users from the default server session.
    '''
    if not window('jellyfin_online.bool'):
        return

    session = api_client.get_device(client.get_device_id())
    users = api_client.get_users()
    current = session[0]['AdditionalUsers']

    result = dialog("select", translate(33061), [translate(33062), translate(33063)] if current else [translate(33062)])

    if result < 0:
        return

    if not result:  # Add user
        eligible = [x for x in users if x['Id'] not in [current_user['UserId'] for current_user in current]]
        resp = dialog("select", translate(33064), [x['Name'] for x in eligible])

        if resp < 0:
            return

        user = eligible[resp]
        event('AddUser', {'Id': user['Id'], 'Add': True})
    else:  # Remove user
        resp = dialog("select", translate(33064), [x['UserName'] for x in current])

        if resp < 0:
            return

        user = current[resp]
        event('AddUser', {'Id': user['UserId'], 'Add': False})


def get_themes(api_client):

    ''' Add theme media locally, via strm. This is only for tv tunes.
        If another script is used, adjust this code.
    '''
    from ..helper.utils import normalize_string
    from ..helper.playutils import PlayUtils
    from ..helper.xmls import tvtunes_nfo

    library = translate_path("special://profile/addon_data/plugin.video.jellyfin/library")
    play = settings('useDirectPaths') == "1"

    if not xbmcvfs.exists(library + '/'):
        xbmcvfs.mkdir(library)

    if xbmc.getCondVisibility('System.HasAddon(script.tvtunes)'):

        tvtunes = xbmcaddon.Addon(id="script.tvtunes")
        tvtunes.setSetting('custom_path_enable', "true")
        tvtunes.setSetting('custom_path', library)
        LOG.info("TV Tunes custom path is enabled and set.")
    else:
        dialog("ok", "{jellyfin}", translate(33152))

        return

    with Database('jellyfin') as jellyfindb:
        all_views = jellyfin_db.JellyfinDatabase(jellyfindb.cursor).get_views()
        views = [x.view_id for x in all_views if x.media_type in ('movies', 'tvshows', 'mixed')]

    items = {}
    server = api_client.config.data['auth.server']

    for view in views:
        result = api_client.get_items_theme_video(view)

        for item in result['Items']:

            folder = normalize_string(item['Name'])
            items[item['Id']] = folder

        result = api_client.get_items_theme_song(view)

        for item in result['Items']:

            folder = normalize_string(item['Name'])
            items[item['Id']] = folder

    for item in items:

        nfo_path = os.path.join(library, items[item])
        nfo_file = os.path.join(nfo_path, "tvtunes.nfo")

        if not xbmcvfs.exists(nfo_path):
            xbmcvfs.mkdir(nfo_path)

        themes = api_client.get_themes(item)
        paths = []

        for theme in themes['ThemeVideosResult']['Items'] + themes['ThemeSongsResult']['Items']:
            putils = PlayUtils(theme, False, None, server, api_client)

            if play:
                paths.append(putils.direct_play(theme['MediaSources'][0]))
            else:
                paths.append(putils.direct_url(theme['MediaSources'][0]))

        tvtunes_nfo(nfo_file, paths)

    dialog("notification", heading="{jellyfin}", message=translate(33153), icon="{jellyfin}", time=1000, sound=False)


def delete_item():

    ''' Delete keymap action.
    '''
    from . import context

    context.Context(delete=True)


def backup():

    ''' Jellyfin backup.
    '''
    from ..helper.utils import delete_folder, copytree

    path = settings('backupPath')
    folder_name = "Kodi%s.%s" % (kodi_version(), xbmc.getInfoLabel('System.Date(dd-mm-yy)'))
    folder_name = dialog("input", heading=translate(33089), defaultt=folder_name)

    if not folder_name:
        return

    backup = os.path.join(path, folder_name)

    if xbmcvfs.exists(backup + '/'):
        if not dialog("yesno", "{jellyfin}", translate(33090)):

            return backup()

        delete_folder(backup)

    addon_data = translate_path("special://profile/addon_data/plugin.video.jellyfin")
    destination_data = os.path.join(backup, "addon_data", "plugin.video.jellyfin")
    destination_databases = os.path.join(backup, "Database")

    if not xbmcvfs.mkdirs(path) or not xbmcvfs.mkdirs(destination_databases):

        LOG.info("Unable to create all directories")
        dialog("notification", heading="{jellyfin}", icon="{jellyfin}", message=translate(33165), sound=False)

        return

    copytree(addon_data, destination_data)

    databases = Objects().objects

    db = translate_path(databases['jellyfin'])
    xbmcvfs.copy(db, os.path.join(destination_databases, db.rsplit('\\', 1)[1]))
    LOG.info("copied jellyfin.db")

    db = translate_path(databases['video'])
    filename = db.rsplit('\\', 1)[1]
    xbmcvfs.copy(db, os.path.join(destination_databases, filename))
    LOG.info("copied %s", filename)

    if settings('enableMusic.bool'):

        db = translate_path(databases['music'])
        filename = db.rsplit('\\', 1)[1]
        xbmcvfs.copy(db, os.path.join(destination_databases, filename))
        LOG.info("copied %s", filename)

    LOG.info("backup completed")
    dialog("ok", "{jellyfin}", "%s %s" % (translate(33091), backup))


def get_filtered_section(parent_id=None, media=None, limit=None, recursive=None, sort=None, sort_order=None,
                         filters=None, extra=None, server_id=None, api_client=None):

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

    return api_client._get("Users/{UserId}/Items", params)


def browse_info():
    return (
        "DateCreated,EpisodeCount,SeasonCount,Path,Genres,Studios,Taglines,MediaStreams,Overview,Etag,"
        "ProductionLocations,Width,Height,RecursiveItemCount,ChildCount"
    )
