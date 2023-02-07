# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os
import xml.etree.ElementTree as etree

from six.moves.urllib.parse import urlencode
from kodi_six import xbmcvfs

from .database import Database, jellyfin_db, get_sync, save_sync
from .helper import translate, api, window, event
from .jellyfin import Jellyfin
from .helper import LazyLogger
from .helper.utils import translate_path

#################################################################################################

LOG = LazyLogger(__name__)
NODES = {
    'tvshows': [
        ('all', None),
        ('recent', translate(30170)),
        ('recentepisodes', translate(30175)),
        ('inprogress', translate(30171)),
        ('inprogressepisodes', translate(30178)),
        ('nextepisodes', translate(30179)),
        ('genres', 135),
        ('random', translate(30229)),
        ('recommended', translate(30230))
    ],
    'movies': [
        ('all', None),
        ('recent', translate(30174)),
        ('inprogress', translate(30177)),
        ('unwatched', translate(30189)),
        ('sets', 20434),
        ('genres', 135),
        ('random', translate(30229)),
        ('recommended', translate(30230))
    ],
    'musicvideos': [
        ('all', None),
        ('recent', translate(30256)),
        ('inprogress', translate(30257)),
        ('unwatched', translate(30258))
    ]
}
DYNNODES = {
    'tvshows': [
        ('all', None),
        ('RecentlyAdded', translate(30170)),
        ('recentepisodes', translate(30175)),
        ('InProgress', translate(30171)),
        ('inprogressepisodes', translate(30178)),
        ('nextepisodes', translate(30179)),
        ('Genres', translate(135)),
        ('Random', translate(30229)),
        ('recommended', translate(30230))
    ],
    'movies': [
        ('all', None),
        ('RecentlyAdded', translate(30174)),
        ('InProgress', translate(30177)),
        ('Boxsets', translate(20434)),
        ('Favorite', translate(33168)),
        ('FirstLetter', translate(33171)),
        ('Genres', translate(135)),
        ('Random', translate(30229)),
        # ('Recommended', translate(30230))
    ],
    'musicvideos': [
        ('all', None),
        ('RecentlyAdded', translate(30256)),
        ('InProgress', translate(30257)),
        ('Unwatched', translate(30258))
    ],
    'homevideos': [
        ('all', None),
        ('RecentlyAdded', translate(33167)),
        ('InProgress', translate(33169)),
        ('Favorite', translate(33168))
    ],
    'books': [
        ('all', None),
        ('RecentlyAdded', translate(33167)),
        ('InProgress', translate(33169)),
        ('Favorite', translate(33168))
    ],
    'audiobooks': [
        ('all', None),
        ('RecentlyAdded', translate(33167)),
        ('InProgress', translate(33169)),
        ('Favorite', translate(33168))
    ],
    'music': [
        ('all', None),
        ('RecentlyAdded', translate(33167)),
        ('Favorite', translate(33168))
    ]
}

#################################################################################################


class Views(object):

    sync = None
    limit = 25
    media_folders = None

    def __init__(self):

        self.sync = get_sync()
        self.server = Jellyfin()

    def add_library(self, view):

        ''' Add entry to view table in jellyfin database.
        '''
        with Database('jellyfin') as jellyfindb:
            jellyfin_db.JellyfinDatabase(jellyfindb.cursor).add_view(view['Id'], view['Name'], view['Media'])

    def remove_library(self, view_id):

        ''' Remove entry from view table in jellyfin database.
        '''
        with Database('jellyfin') as jellyfindb:
            jellyfin_db.JellyfinDatabase(jellyfindb.cursor).remove_view(view_id)

        self.delete_playlist_by_id(view_id)
        self.delete_node_by_id(view_id)

    def get_libraries(self):

        try:
            libraries = self.server.jellyfin.get_media_folders()['Items']
            library_ids = [x['Id'] for x in libraries]
            for view in self.server.jellyfin.get_views()['Items']:
                if view['Id'] not in library_ids:
                    libraries.append(view)

        except Exception as error:
            LOG.exception(error)
            raise IndexError("Unable to retrieve libraries: %s" % error)

        return libraries

    def get_views(self):

        ''' Get the media folders. Add or remove them. Do not proceed if issue getting libraries.
        '''
        try:
            libraries = self.get_libraries()
        except IndexError as error:
            LOG.exception(error)

            return

        self.sync['SortedViews'] = [x['Id'] for x in libraries]

        for library in libraries:

            if library['Type'] == 'Channel':
                library['Media'] = "channels"
            else:
                library['Media'] = library.get('OriginalCollectionType', library.get('CollectionType', "mixed"))

            self.add_library(library)

        with Database('jellyfin') as jellyfindb:

            views = jellyfin_db.JellyfinDatabase(jellyfindb.cursor).get_views()
            removed = []

            for view in views:
                if view.view_id not in self.sync['SortedViews']:
                    removed.append(view.view_id)

            if removed:
                event('RemoveLibrary', {'Id': ','.join(removed)})

        save_sync(self.sync)

    def get_nodes(self):

        ''' Set up playlists, video nodes, window prop.
        '''
        node_path = translate_path("special://profile/library/video")
        playlist_path = translate_path("special://profile/playlists/video")
        index = 0

        # Kodi 19 doesn't seem to create this directory on its own
        if not os.path.isdir(node_path):
            os.makedirs(node_path)

        with Database('jellyfin') as jellyfindb:
            db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)

            for library in self.sync['Whitelist']:

                library = library.replace('Mixed:', "")
                view = db.get_view(library)

                if view:
                    view = {'Id': library, 'Name': view.view_name, 'Tag': view.view_name, 'Media': view.media_type}

                    if view['Media'] == 'mixed':
                        for media in ('movies', 'tvshows'):

                            temp_view = dict(view)
                            temp_view['Media'] = media
                            self.add_playlist(playlist_path, temp_view, True)
                            self.add_nodes(node_path, temp_view, True)

                        index += 1  # Compensate for the duplicate.
                    else:
                        if view['Media'] in ('movies', 'tvshows', 'musicvideos'):
                            self.add_playlist(playlist_path, view)

                        if view['Media'] not in ('music',):
                            self.add_nodes(node_path, view)

                    index += 1

        for single in [{'Name': translate('fav_movies'), 'Tag': "Favorite movies", 'Media': "movies"},
                       {'Name': translate('fav_tvshows'), 'Tag': "Favorite tvshows", 'Media': "tvshows"},
                       {'Name': translate('fav_episodes'), 'Tag': "Favorite episodes", 'Media': "episodes"}]:

            self.add_single_node(node_path, index, "favorites", single)
            index += 1

        self.window_nodes()

    def add_playlist(self, path, view, mixed=False):

        ''' Create or update the xps file.
        '''
        file = os.path.join(path, "jellyfin%s%s.xsp" % (view['Media'], view['Id']))

        try:
            if os.path.isfile(file):
                xml = etree.parse(file).getroot()
            else:
                xml = etree.Element('smartplaylist', {'type': view['Media']})
                etree.SubElement(xml, 'name')
                etree.SubElement(xml, 'match')
        except Exception:
            LOG.warning("Unable to parse file '%s'", file)
            xml = etree.Element('smartplaylist', {'type': view['Media']})
            etree.SubElement(xml, 'name')
            etree.SubElement(xml, 'match')

        name = xml.find('name')
        name.text = view['Name'] if not mixed else "%s (%s)" % (view['Name'], view['Media'])

        match = xml.find('match')
        match.text = "all"

        for rule in xml.findall('.//value'):
            if rule.text == view['Tag']:
                break
        else:
            rule = etree.SubElement(xml, 'rule', {'field': "tag", 'operator': "is"})
            etree.SubElement(rule, 'value').text = view['Tag']

        tree = etree.ElementTree(xml)
        tree.write(file)

    def add_nodes(self, path, view, mixed=False):

        ''' Create or update the video node file.
        '''
        folder = os.path.join(path, "jellyfin%s%s" % (view['Media'], view['Id']))

        if not xbmcvfs.exists(folder):
            xbmcvfs.mkdir(folder)

        self.node_index(folder, view, mixed)

        if view['Media'] == 'tvshows':
            self.node_tvshow(folder, view)
        else:
            self.node(folder, view)

    def add_single_node(self, path, index, item_type, view):

        file = os.path.join(path, "jellyfin_%s.xml" % view['Tag'].replace(" ", ""))

        try:
            if os.path.isfile(file):
                xml = etree.parse(file).getroot()
            else:
                xml = self.node_root('folder' if item_type == 'favorites' and view['Media'] == 'episodes' else 'filter', index)
                etree.SubElement(xml, 'label')
                etree.SubElement(xml, 'match')
                etree.SubElement(xml, 'content')
        except Exception:
            LOG.warning("Unable to parse file '%s'", file)
            xml = self.node_root('folder' if item_type == 'favorites' and view['Media'] == 'episodes' else 'filter', index)
            etree.SubElement(xml, 'label')
            etree.SubElement(xml, 'match')
            etree.SubElement(xml, 'content')

        label = xml.find('label')
        label.text = view['Name']

        content = xml.find('content')
        content.text = view['Media']

        match = xml.find('match')
        match.text = "all"

        if view['Media'] != 'episodes':

            for rule in xml.findall('.//value'):
                if rule.text == view['Tag']:
                    break
            else:
                rule = etree.SubElement(xml, 'rule', {'field': "tag", 'operator': "is"})
                etree.SubElement(rule, 'value').text = view['Tag']

        if item_type == 'favorites' and view['Media'] == 'episodes':
            path = self.window_browse(view, 'FavEpisodes')
            self.node_favepisodes(xml, path)
        else:
            self.node_all(xml)

        tree = etree.ElementTree(xml)
        tree.write(file)

    def node_root(self, root, index):

        ''' Create the root element
        '''
        if root == 'main':
            element = etree.Element('node', {'order': str(index)})
        elif root == 'filter':
            element = etree.Element('node', {'order': str(index), 'type': "filter"})
        else:
            element = etree.Element('node', {'order': str(index), 'type': "folder"})

        etree.SubElement(element, 'icon').text = "special://home/addons/plugin.video.jellyfin/resources/icon.png"

        return element

    def node_index(self, folder, view, mixed=False):

        file = os.path.join(folder, "index.xml")
        index = self.sync['SortedViews'].index(view['Id'])

        try:
            if os.path.isfile(file):
                xml = etree.parse(file).getroot()
                xml.set('order', str(index))
            else:
                xml = self.node_root('main', index)
                etree.SubElement(xml, 'label')
        except Exception as error:
            LOG.exception(error)
            xml = self.node_root('main', index)
            etree.SubElement(xml, 'label')

        label = xml.find('label')
        label.text = view['Name'] if not mixed else "%s (%s)" % (view['Name'], translate(view['Media']))

        tree = etree.ElementTree(xml)
        tree.write(file)

    def node(self, folder, view):

        for node in NODES[view['Media']]:

            xml_name = node[0]
            xml_label = node[1] or view['Name']
            file = os.path.join(folder, "%s.xml" % xml_name)
            self.add_node(NODES[view['Media']].index(node), file, view, xml_name, xml_label)

    def node_tvshow(self, folder, view):

        for node in NODES[view['Media']]:

            xml_name = node[0]
            xml_label = node[1] or view['Name']
            xml_index = NODES[view['Media']].index(node)
            file = os.path.join(folder, "%s.xml" % xml_name)

            if xml_name == 'nextepisodes':
                path = self.window_nextepisodes(view)
                self.add_dynamic_node(xml_index, file, view, xml_name, xml_label, path)
            else:
                self.add_node(xml_index, file, view, xml_name, xml_label)

    def add_node(self, index, file, view, node, name):

        try:
            if os.path.isfile(file):
                xml = etree.parse(file).getroot()
            else:
                xml = self.node_root('filter', index)
                etree.SubElement(xml, 'label')
                etree.SubElement(xml, 'match')
                etree.SubElement(xml, 'content')

        except Exception:
            LOG.warning("Unable to parse file '%s'", file)
            xml = self.node_root('filter', index)
            etree.SubElement(xml, 'label')
            etree.SubElement(xml, 'match')
            etree.SubElement(xml, 'content')

        label = xml.find('label')
        label.text = str(name) if type(name) == int else name

        content = xml.find('content')
        content.text = view['Media']

        match = xml.find('match')
        match.text = "all"

        for rule in xml.findall('.//value'):
            if rule.text == view['Tag']:
                break
        else:
            rule = etree.SubElement(xml, 'rule', {'field': "tag", 'operator': "is"})
            etree.SubElement(rule, 'value').text = view['Tag']

        getattr(self, 'node_' + node)(xml)  # get node function based on node type
        tree = etree.ElementTree(xml)
        tree.write(file)

    def add_dynamic_node(self, index, file, view, node, name, path):

        try:
            if os.path.isfile(file):
                xml = etree.parse(file).getroot()
            else:
                xml = self.node_root('folder', index)
                etree.SubElement(xml, 'label')
                etree.SubElement(xml, 'content')
        except Exception:
            LOG.warning("Unable to parse file '%s'", file)
            xml = self.node_root('folder', index)
            etree.SubElement(xml, 'label')
            etree.SubElement(xml, 'content')

        # Migration for https://github.com/jellyfin/jellyfin-kodi/issues/239
        if xml.attrib.get('type') == 'filter':
            xml.attrib = {'type': 'folder', 'order': '5'}

        label = xml.find('label')
        label.text = name

        getattr(self, 'node_' + node)(xml, path)
        tree = etree.ElementTree(xml)
        tree.write(file)

    def node_all(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

    def node_nextepisodes(self, root, path):

        for rule in root.findall('.//path'):
            rule.text = path
            break
        else:
            etree.SubElement(root, 'path').text = path

        for rule in root.findall('.//content'):
            rule.text = "episodes"
            break
        else:
            etree.SubElement(root, 'content').text = "episodes"

    def node_recent(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            etree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = etree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            etree.SubElement(rule, 'value').text = "0"

    def node_inprogress(self, root):

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'inprogress':
                break
        else:
            etree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            etree.SubElement(root, 'limit').text = str(self.limit)

    def node_genres(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//group'):
            rule.text = "genres"
            break
        else:
            etree.SubElement(root, 'group').text = "genres"

    def node_unwatched(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = etree.SubElement(root, "rule", {'field': "playcount", 'operator': "is"})
            etree.SubElement(rule, 'value').text = "0"

    def node_sets(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "sorttitle":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "ascending"}).text = "sorttitle"

        for rule in root.findall('.//group'):
            rule.text = "sets"
            break
        else:
            etree.SubElement(root, 'group').text = "sets"

    def node_random(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "random":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "ascending"}).text = "random"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            etree.SubElement(root, 'limit').text = str(self.limit)

    def node_recommended(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "rating":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "descending"}).text = "rating"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            etree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = etree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            etree.SubElement(rule, 'value').text = "0"

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'rating':
                rule.find('value').text = "7"
                break
        else:
            rule = etree.SubElement(root, 'rule', {'field': "rating", 'operator': "greaterthan"})
            etree.SubElement(rule, 'value').text = "7"

    def node_recentepisodes(self, root):

        for rule in root.findall('.//order'):
            if rule.text == "dateadded":
                break
        else:
            etree.SubElement(root, 'order', {'direction': "descending"}).text = "dateadded"

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            etree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'playcount':
                rule.find('value').text = "0"
                break
        else:
            rule = etree.SubElement(root, 'rule', {'field': "playcount", 'operator': "is"})
            etree.SubElement(rule, 'value').text = "0"

        content = root.find('content')
        content.text = "episodes"

    def node_inprogressepisodes(self, root):

        for rule in root.findall('.//limit'):
            rule.text = str(self.limit)
            break
        else:
            etree.SubElement(root, 'limit').text = str(self.limit)

        for rule in root.findall('.//rule'):
            if rule.attrib['field'] == 'inprogress':
                break
        else:
            etree.SubElement(root, 'rule', {'field': "inprogress", 'operator': "true"})

        content = root.find('content')
        content.text = "episodes"

    def node_favepisodes(self, root, path):

        for rule in root.findall('.//path'):
            rule.text = path
            break
        else:
            etree.SubElement(root, 'path').text = path

        for rule in root.findall('.//content'):
            rule.text = "episodes"
            break
        else:
            etree.SubElement(root, 'content').text = "episodes"

    def order_media_folders(self, folders):

        ''' Returns a list of sorted media folders based on the Jellyfin views.
            Insert them in SortedViews and remove Views that are not in media folders.
        '''
        if not folders:
            return folders

        sorted_views = list(self.sync['SortedViews'])
        unordered = [x[0] for x in folders]
        grouped = [x for x in unordered if x not in sorted_views]

        for library in grouped:
            sorted_views.append(library)

        sorted_folders = [x for x in sorted_views if x in unordered]

        return [folders[unordered.index(x)] for x in sorted_folders]

    def window_nodes(self):

        ''' Just read from the database and populate based on SortedViews
            Set up the window properties that reflect the jellyfin server views and more.
        '''
        self.window_clear()
        self.window_clear('Jellyfin.wnodes')

        with Database('jellyfin') as jellyfindb:
            libraries = jellyfin_db.JellyfinDatabase(jellyfindb.cursor).get_views()

        libraries = self.order_media_folders(libraries or [])
        index = 0
        windex = 0

        try:
            self.media_folders = self.get_libraries()
        except IndexError as error:
            LOG.exception(error)

        for library in libraries:
            view = {'Id': library.view_id, 'Name': library.view_name, 'Tag': library.view_name, 'Media': library.media_type}

            if library.view_id in [x.replace('Mixed:', "") for x in self.sync['Whitelist']]:  # Synced libraries

                if view['Media'] in ('movies', 'tvshows', 'musicvideos', 'mixed'):

                    if view['Media'] == 'mixed':
                        for media in ('movies', 'tvshows'):

                            for node in NODES[media]:

                                temp_view = dict(view)
                                temp_view['Media'] = media
                                temp_view['Name'] = "%s (%s)" % (view['Name'], translate(media))
                                self.window_node(index, temp_view, *node)
                                self.window_wnode(windex, temp_view, *node)

                            # Add one to compensate for the duplicate.
                            index += 1
                            windex += 1
                    else:
                        for node in NODES[view['Media']]:

                            self.window_node(index, view, *node)

                            if view['Media'] in ('movies', 'tvshows'):
                                self.window_wnode(windex, view, *node)

                        if view['Media'] in ('movies', 'tvshows'):
                            windex += 1

                elif view['Media'] == 'music':
                    self.window_node(index, view, 'music')
            else:  # Dynamic entry
                if view['Media'] in ('homevideos', 'books', 'playlists'):
                    self.window_wnode(windex, view, 'browse')
                    windex += 1

                self.window_node(index, view, 'browse')

            index += 1

        for single in [{'Name': translate('fav_movies'), 'Tag': "Favorite movies", 'Media': "movies"},
                       {'Name': translate('fav_tvshows'), 'Tag': "Favorite tvshows", 'Media': "tvshows"},
                       {'Name': translate('fav_episodes'), 'Tag': "Favorite episodes", 'Media': "episodes"}]:

            self.window_single_node(index, "favorites", single)
            index += 1

        window('Jellyfin.nodes.total', str(index))
        window('Jellyfin.wnodes.total', str(windex))

    def window_node(self, index, view, node=None, node_label=None):

        ''' Leads to another listing of nodes.
        '''
        if view['Media'] in ('homevideos', 'photos'):
            path = self.window_browse(view, None if node in ('all', 'browse') else node)
        elif node == 'nextepisodes':
            path = self.window_nextepisodes(view)
        elif node == 'music':
            path = self.window_music(view)
        elif node == 'browse':
            path = self.window_browse(view)
        else:
            path = self.window_path(view, node)

        if node == 'music':
            window_path = "ActivateWindow(Music,%s,return)" % path
        elif node in ('browse', 'homevideos', 'photos'):
            window_path = path
        else:
            window_path = "ActivateWindow(Videos,%s,return)" % path

        node_label = translate(node_label) if type(node_label) == int else node_label
        node_label = node_label or view['Name']

        if node in ('all', 'music'):

            window_prop = "Jellyfin.nodes.%s" % index
            window('%s.index' % window_prop, path.replace('all.xml', ""))  # dir
            window('%s.title' % window_prop, view['Name'])
            window('%s.content' % window_prop, path)

        elif node == 'browse':

            window_prop = "Jellyfin.nodes.%s" % index
            window('%s.title' % window_prop, view['Name'])
        else:
            window_prop = "Jellyfin.nodes.%s.%s" % (index, node)
            window('%s.title' % window_prop, node_label)
            window('%s.content' % window_prop, path)

        window('%s.id' % window_prop, view['Id'])
        window('%s.path' % window_prop, window_path)
        window('%s.type' % window_prop, view['Media'])
        self.window_artwork(window_prop, view['Id'])

    def window_single_node(self, index, item_type, view):

        ''' Single destination node.
        '''
        path = "library://video/jellyfin_%s.xml" % view['Tag'].replace(" ", "")
        window_path = "ActivateWindow(Videos,%s,return)" % path

        window_prop = "Jellyfin.nodes.%s" % index
        window('%s.title' % window_prop, view['Name'])
        window('%s.path' % window_prop, window_path)
        window('%s.content' % window_prop, path)
        window('%s.type' % window_prop, item_type)

    def window_wnode(self, index, view, node=None, node_label=None):

        ''' Similar to window_node, but does not contain music, musicvideos.
            Contains books, audiobooks.
        '''
        if view['Media'] in ('homevideos', 'photos', 'books', 'playlists'):
            path = self.window_browse(view, None if node in ('all', 'browse') else node)
        else:
            path = self.window_path(view, node)

        if node in ('browse', 'homevideos', 'photos', 'books', 'playlists'):
            window_path = path
        else:
            window_path = "ActivateWindow(Videos,%s,return)" % path

        node_label = translate(node_label) if type(node_label) == int else node_label
        node_label = node_label or view['Name']

        if node == 'all':

            window_prop = "Jellyfin.wnodes.%s" % index
            window('%s.index' % window_prop, path.replace('all.xml', ""))  # dir
            window('%s.title' % window_prop, view['Name'])
        elif node == 'browse':

            window_prop = "Jellyfin.wnodes.%s" % index
            window('%s.title' % window_prop, view['Name'])
        else:
            window_prop = "Jellyfin.wnodes.%s.%s" % (index, node)
            window('%s.title' % window_prop, node_label)
        window('%s.content' % window_prop, path)

        window('%s.id' % window_prop, view['Id'])
        window('%s.path' % window_prop, window_path)
        window('%s.type' % window_prop, view['Media'])
        self.window_artwork(window_prop, view['Id'])

        LOG.debug("--[ wnode/%s/%s ] %s", index, window('%s.title' % window_prop), window('%s.artwork' % window_prop))

    def window_artwork(self, prop, view_id):

        if not self.server.logged_in:
            window('%s.artwork' % prop, clear=True)

        elif self.media_folders is not None:
            for library in self.media_folders:

                if library['Id'] == view_id and 'Primary' in library.get('ImageTags', {}):
                    server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
                    artwork = api.API(None, server_address).get_artwork(view_id, 'Primary')
                    window('%s.artwork' % prop, artwork)

                    break
            else:
                window('%s.artwork' % prop, clear=True)

    def window_path(self, view, node):
        return "library://video/jellyfin%s%s/%s.xml" % (view['Media'], view['Id'], node)

    def window_music(self, view):
        return "library://music/"

    def window_nextepisodes(self, view):

        params = {
            'id': view['Id'],
            'mode': "nextepisodes",
            'limit': self.limit
        }
        return "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))

    def window_browse(self, view, node=None):

        params = {
            'mode': "browse",
            'type': view['Media']
        }

        if view.get('Id'):
            params['id'] = view['Id']

        if node:
            params['folder'] = node

        return "%s?%s" % ("plugin://plugin.video.jellyfin/", urlencode(params))

    def window_clear(self, name=None):

        ''' Clearing window prop setup for Views.
        '''
        total = int(window((name or 'Jellyfin.nodes') + '.total') or 0)
        props = [

            "index", "id", "path", "artwork", "title", "content", "type"
            "inprogress.content", "inprogress.title",
            "inprogress.content", "inprogress.path",
            "nextepisodes.title", "nextepisodes.content",
            "nextepisodes.path", "unwatched.title",
            "unwatched.content", "unwatched.path",
            "recent.title", "recent.content", "recent.path",
            "recentepisodes.title", "recentepisodes.content",
            "recentepisodes.path", "inprogressepisodes.title",
            "inprogressepisodes.content", "inprogressepisodes.path"
        ]
        for i in range(total):
            for prop in props:
                window('Jellyfin.nodes.%s.%s' % (str(i), prop), clear=True)

        for prop in props:
            window('Jellyfin.nodes.%s' % prop, clear=True)

    def delete_playlist(self, path):

        xbmcvfs.delete(path)
        LOG.info("DELETE playlist %s", path)

    def delete_playlists(self):

        ''' Remove all jellyfin playlists.
        '''
        path = translate_path("special://profile/playlists/video/")
        _, files = xbmcvfs.listdir(path)
        for file in files:
            if file.startswith('jellyfin'):
                self.delete_playlist(os.path.join(path, file))

    def delete_playlist_by_id(self, view_id):

        ''' Remove playlist based on view_id.
        '''
        path = translate_path("special://profile/playlists/video/")
        _, files = xbmcvfs.listdir(path)
        for file in files:
            file = file

            if file.startswith('jellyfin') and file.endswith('%s.xsp' % view_id):
                self.delete_playlist(os.path.join(path, file))

    def delete_node(self, path):

        xbmcvfs.delete(path)
        LOG.info("DELETE node %s", path)

    def delete_nodes(self):

        ''' Remove node and children files.
        '''
        path = translate_path("special://profile/library/video/")
        dirs, files = xbmcvfs.listdir(path)

        for file in files:

            if file.startswith('jellyfin'):
                self.delete_node(os.path.join(path, file))

        for directory in dirs:

            if directory.startswith('jellyfin'):
                _, files = xbmcvfs.listdir(os.path.join(path, directory))

                for file in files:
                    self.delete_node(os.path.join(path, directory, file))

                xbmcvfs.rmdir(os.path.join(path, directory))

    def delete_node_by_id(self, view_id):

        ''' Remove node and children files based on view_id.
        '''
        path = translate_path("special://profile/library/video/")
        dirs, files = xbmcvfs.listdir(path)

        for directory in dirs:

            if directory.startswith('jellyfin') and directory.endswith(view_id):
                _, files = xbmcvfs.listdir(os.path.join(path, directory))

                for file in files:
                    self.delete_node(os.path.join(path, directory, file))

                xbmcvfs.rmdir(os.path.join(path, directory))
