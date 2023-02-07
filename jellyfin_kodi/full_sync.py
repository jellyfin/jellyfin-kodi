# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from contextlib import contextmanager
import datetime

from kodi_six import xbmc

from . import downloader as server
from .objects import Movies, TVShows, MusicVideos, Music
from .database import Database, get_sync, save_sync, jellyfin_db
from .helper import translate, settings, window, progress, dialog, LazyLogger, xmls
from .helper.utils import get_screensaver, set_screensaver
from .helper.exceptions import LibraryException, PathValidationException

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class FullSync(object):

    ''' This should be called like a context.
        i.e. with FullSync('jellyfin') as sync:
            sync.libraries()
    '''
    # Borg - multiple instances, shared state
    _shared_state = {}
    sync = None
    running = False
    screensaver = None

    def __init__(self, library, server):

        ''' You can call all big syncing methods here.
            Initial, update, repair, remove.
        '''
        self.__dict__ = self._shared_state

        if self.running:
            dialog("ok", "{jellyfin}", translate(33197))

            raise Exception("Sync is already running.")

        self.library = library
        self.server = server

    def __enter__(self):

        ''' Do everything we need before the sync
        '''
        LOG.info("-->[ fullsync ]")

        if not settings('dbSyncScreensaver.bool'):

            xbmc.executebuiltin('InhibitIdleShutdown(true)')
            self.screensaver = get_screensaver()
            set_screensaver(value="")

        self.running = True
        window('jellyfin_sync.bool', True)

        return self

    def libraries(self, libraries=None, update=False):

        ''' Map the syncing process and start the sync. Ensure only one sync is running.
        '''
        self.direct_path = settings('useDirectPaths') == "1"
        self.update_library = update
        self.sync = get_sync()

        if libraries:
            # Can be a single ID or a comma separated list
            libraries = libraries.split(',')
            for library_id in libraries:
                # Look up library in local Jellyfin database
                library = self.get_library(library_id)

                if library:
                    if library.media_type == 'mixed':
                        self.sync['Libraries'].append("Mixed:%s" % library_id)
                        # Include boxsets library
                        libraries = self.get_libraries()
                        boxsets = [row.view_id for row in libraries if row.media_type == 'boxsets']
                        if boxsets:
                            self.sync['Libraries'].append('Boxsets:%s' % boxsets[0])
                    elif library.media_type == 'movies':
                        self.sync['Libraries'].append(library_id)
                        # Include boxsets library
                        libraries = self.get_libraries()
                        boxsets = [row.view_id for row in libraries if row.media_type == 'boxsets']
                        # Verify we're only trying to sync boxsets once
                        if boxsets and boxsets[0] not in self.sync['Libraries']:
                            self.sync['Libraries'].append('Boxsets:%s' % boxsets[0])
                    else:
                        # Only called if the library isn't already known about
                        self.sync['Libraries'].append(library_id)
                else:
                    self.sync['Libraries'].append(library_id)
        else:
            self.mapping()

        if not xmls.advanced_settings() and self.sync['Libraries']:
            self.start()

    def get_libraries(self):
        with Database('jellyfin') as jellyfindb:
            return jellyfin_db.JellyfinDatabase(jellyfindb.cursor).get_views()

    def get_library(self, library_id):
        with Database('jellyfin') as jellyfindb:
            return jellyfin_db.JellyfinDatabase(jellyfindb.cursor).get_view(library_id)

    def mapping(self):

        ''' Load the mapping of the full sync.
            This allows us to restore a previous sync.
        '''
        if self.sync['Libraries']:

            if not dialog("yesno", "{jellyfin}", translate(33102)):

                if not dialog("yesno", "{jellyfin}", translate(33173)):
                    dialog("ok", "{jellyfin}", translate(33122))

                    raise LibraryException("ProgressStopped")
                else:
                    self.sync['Libraries'] = []
                    self.sync['RestorePoint'] = {}
        else:
            LOG.info("generate full sync")
            libraries = []

            for library in self.get_libraries():
                if library.media_type in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed'):
                    libraries.append({'Id': library.view_id, 'Name': library.view_name, 'Media': library.media_type})

            libraries = self.select_libraries(libraries)

            if [x['Media'] for x in libraries if x['Media'] in ('movies', 'mixed')]:
                self.sync['Libraries'].append("Boxsets:")

        save_sync(self.sync)

    def select_libraries(self, libraries):

        ''' Select all or certain libraries to be whitelisted.
        '''

        choices = [x['Name'] for x in libraries]
        choices.insert(0, translate(33121))
        selection = dialog("multi", translate(33120), choices)

        if selection is None:
            raise LibraryException('LibrarySelection')
        elif not selection:
            LOG.info("Nothing was selected.")

            raise LibraryException('SyncLibraryLater')

        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        selected_libraries = []

        for x in selection:
            library = libraries[x - 1]

            if library['Media'] != 'mixed':
                selected_libraries.append(library['Id'])
            else:
                selected_libraries.append("Mixed:%s" % library['Id'])

        self.sync['Libraries'] = selected_libraries

        return [libraries[x - 1] for x in selection]

    def start(self):

        ''' Main sync process.
        '''
        LOG.info("starting sync with %s", self.sync['Libraries'])
        save_sync(self.sync)
        start_time = datetime.datetime.now()

        for library in list(self.sync['Libraries']):

            self.process_library(library)

            if not library.startswith('Boxsets:') and library not in self.sync['Whitelist']:
                self.sync['Whitelist'].append(library)

            self.sync['Libraries'].pop(self.sync['Libraries'].index(library))
            self.sync['RestorePoint'] = {}

        elapsed = datetime.datetime.now() - start_time
        settings('SyncInstallRunDone.bool', True)
        self.library.save_last_sync()
        save_sync(self.sync)

        xbmc.executebuiltin('UpdateLibrary(video)')
        dialog("notification", heading="{jellyfin}", message="%s %s" % (translate(33025), str(elapsed).split('.')[0]),
               icon="{jellyfin}", sound=False)
        LOG.info("Full sync completed in: %s", str(elapsed).split('.')[0])

    def process_library(self, library_id):

        ''' Add a library by its id. Create a node and a playlist whenever appropriate.
        '''
        media = {
            'movies': self.movies,
            'musicvideos': self.musicvideos,
            'tvshows': self.tvshows,
            'music': self.music
        }
        try:
            if library_id.startswith('Boxsets:'):
                boxset_library = {}

                # Initial library sync is 'Boxsets:'
                # Refresh from the addon menu is 'Boxsets:Refresh'
                # Incremental syncs are 'Boxsets:$library_id'
                sync_id = library_id.split(':')[1]

                if not sync_id or sync_id == 'Refresh':
                    libraries = self.get_libraries()
                else:
                    _lib = self.get_library(sync_id)
                    libraries = [_lib] if _lib else []

                for entry in libraries:
                    if entry.media_type == 'boxsets':
                        boxset_library = {'Id': entry.view_id, 'Name': entry.view_name}
                        break

                if boxset_library:
                    if sync_id == 'Refresh':
                        self.refresh_boxsets(boxset_library)
                    else:
                        self.boxsets(boxset_library)

                return

            library = self.server.jellyfin.get_item(library_id.replace('Mixed:', ""))

            if library_id.startswith('Mixed:'):
                for mixed in ('movies', 'tvshows'):

                    media[mixed](library)
                    self.sync['RestorePoint'] = {}
            else:
                if library['CollectionType']:
                    settings('enableMusic.bool', True)

                media[library['CollectionType']](library)
        except LibraryException as error:

            if error.status == 'StopCalled':
                save_sync(self.sync)

                raise

        except PathValidationException:
            raise

        except Exception as error:
            dialog("ok", "{jellyfin}", translate(33119))

            LOG.error("full sync exited unexpectedly")
            LOG.exception(error)

            save_sync(self.sync)

            raise

    @contextmanager
    def video_database_locks(self):
        with self.library.database_lock:
            with Database() as videodb:
                with Database('jellyfin') as jellyfindb:
                    yield videodb, jellyfindb

    @progress()
    def movies(self, library, dialog):

        ''' Process movies from a single library.
        '''
        processed_ids = []

        for items in server.get_items(library['Id'], "Movie", False, self.sync['RestorePoint'].get('params')):

            with self.video_database_locks() as (videodb, jellyfindb):
                obj = Movies(self.server, jellyfindb, videodb, self.direct_path, library)

                self.sync['RestorePoint'] = items['RestorePoint']
                start_index = items['RestorePoint']['params']['StartIndex']

                for index, movie in enumerate(items['Items']):

                    dialog.update(int((float(start_index + index) / float(items['TotalRecordCount'])) * 100),
                                  heading="%s: %s" % (translate('addon_name'), library['Name']),
                                  message=movie['Name'])
                    obj.movie(movie)
                    processed_ids.append(movie['Id'])

        with self.video_database_locks() as (videodb, jellyfindb):
            obj = Movies(self.server, jellyfindb, videodb, self.direct_path, library)
            obj.item_ids = processed_ids

            if self.update_library:
                self.movies_compare(library, obj, jellyfindb)

    def movies_compare(self, library, obj, jellyfinydb):

        ''' Compare entries from library to what's in the jellyfindb. Remove surplus
        '''
        db = jellyfin_db.JellyfinDatabase(jellyfinydb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'Movie':
                obj.remove(x[0])

    @progress()
    def tvshows(self, library, dialog):

        ''' Process tvshows and episodes from a single library.
        '''
        processed_ids = []

        for items in server.get_items(library['Id'], "Series", False, self.sync['RestorePoint'].get('params')):

            with self.video_database_locks() as (videodb, jellyfindb):
                obj = TVShows(self.server, jellyfindb, videodb, self.direct_path, library, True)

                self.sync['RestorePoint'] = items['RestorePoint']
                start_index = items['RestorePoint']['params']['StartIndex']

                for index, show in enumerate(items['Items']):

                    percent = int((float(start_index + index) / float(items['TotalRecordCount'])) * 100)
                    message = show['Name']
                    dialog.update(percent, heading="%s: %s" % (translate('addon_name'), library['Name']), message=message)

                    if obj.tvshow(show) is not False:

                        for episodes in server.get_episode_by_show(show['Id']):
                            for episode in episodes['Items']:
                                if episode.get('Path'):
                                    dialog.update(percent, message="%s/%s" % (message, episode['Name'][:10]))
                                    obj.episode(episode)
                    processed_ids.append(show['Id'])

        with self.video_database_locks() as (videodb, jellyfindb):
            obj = TVShows(self.server, jellyfindb, videodb, self.direct_path, library, True)
            obj.item_ids = processed_ids
            if self.update_library:
                self.tvshows_compare(library, obj, jellyfindb)

    def tvshows_compare(self, library, obj, jellyfindb):

        ''' Compare entries from library to what's in the jellyfindb. Remove surplus
        '''
        db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        for x in list(items):
            items.extend(obj.get_child(x[0]))

        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'Series':
                obj.remove(x[0])

    @progress()
    def musicvideos(self, library, dialog):

        ''' Process musicvideos from a single library.
        '''
        processed_ids = []

        for items in server.get_items(library['Id'], "MusicVideo", False, self.sync['RestorePoint'].get('params')):

            with self.video_database_locks() as (videodb, jellyfindb):
                obj = MusicVideos(self.server, jellyfindb, videodb, self.direct_path, library)

                self.sync['RestorePoint'] = items['RestorePoint']
                start_index = items['RestorePoint']['params']['StartIndex']

                for index, mvideo in enumerate(items['Items']):

                    dialog.update(int((float(start_index + index) / float(items['TotalRecordCount'])) * 100),
                                  heading="%s: %s" % (translate('addon_name'), library['Name']),
                                  message=mvideo['Name'])
                    obj.musicvideo(mvideo)
                    processed_ids.append(mvideo['Id'])

        with self.video_database_locks() as (videodb, jellyfindb):
            obj = MusicVideos(self.server, jellyfindb, videodb, self.direct_path, library)
            obj.item_ids = processed_ids
            if self.update_library:
                self.musicvideos_compare(library, obj, jellyfindb)

    def musicvideos_compare(self, library, obj, jellyfindb):

        ''' Compare entries from library to what's in the jellyfindb. Remove surplus
        '''
        db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'MusicVideo':
                obj.remove(x[0])

    @progress()
    def music(self, library, dialog):

        ''' Process artists, album, songs from a single library.
        '''
        with self.library.music_database_lock:
            with Database('music') as musicdb:
                with Database('jellyfin') as jellyfindb:
                    obj = Music(self.server, jellyfindb, musicdb, self.direct_path, library)

                    library_id = library['Id']

                    total_items = server.get_item_count(library_id, 'MusicArtist,MusicAlbum,Audio')
                    count = 0

                    '''
                    Music database syncing.  Artists must be in the database
                    before albums, albums before songs.  Pulls batches of items
                    in sizes of setting "Paging - Max items".  'artists',
                    'albums', and 'songs' are generators containing a dict of
                    api responses
                    '''
                    artists = server.get_artists(library_id)
                    for batch in artists:
                        for item in batch['Items']:
                            LOG.debug('Artist: {}'.format(item.get('Name')))
                            percent = int((float(count) / float(total_items)) * 100)
                            dialog.update(percent, message='Artist: {}'.format(item.get('Name')))
                            obj.artist(item)
                            count += 1

                    albums = server.get_items(library_id, item_type='MusicAlbum', params={'SortBy': 'AlbumArtist'})
                    for batch in albums:
                        for item in batch['Items']:
                            LOG.debug('Album: {}'.format(item.get('Name')))
                            percent = int((float(count) / float(total_items)) * 100)
                            dialog.update(percent, message='Album: {} - {}'.format(item.get('AlbumArtist', ''), item.get('Name')))
                            obj.album(item)
                            count += 1

                    songs = server.get_items(library_id, item_type='Audio', params={'SortBy': 'AlbumArtist'})
                    for batch in songs:
                        for item in batch['Items']:
                            LOG.debug('Song: {}'.format(item.get('Name')))
                            percent = int((float(count) / float(total_items)) * 100)
                            dialog.update(percent, message='Track: {} - {}'.format(item.get('AlbumArtist', ''), item.get('Name')))
                            obj.song(item)
                            count += 1

                    if self.update_library:
                        self.music_compare(library, obj, jellyfindb)

    def music_compare(self, library, obj, jellyfindb):

        ''' Compare entries from library to what's in the jellyfindb. Remove surplus
        '''
        db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        for x in list(items):
            items.extend(obj.get_child(x[0]))

        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'MusicArtist':
                obj.remove(x[0])

    @progress(translate(33018))
    def boxsets(self, library, dialog=None):

        ''' Process all boxsets.
        '''
        for items in server.get_items(library['Id'], "BoxSet", False, self.sync['RestorePoint'].get('params')):

            with self.video_database_locks() as (videodb, jellyfindb):
                obj = Movies(self.server, jellyfindb, videodb, self.direct_path, library)

                self.sync['RestorePoint'] = items['RestorePoint']
                start_index = items['RestorePoint']['params']['StartIndex']

                for index, boxset in enumerate(items['Items']):

                    dialog.update(int((float(start_index + index) / float(items['TotalRecordCount'])) * 100),
                                  heading="%s: %s" % (translate('addon_name'), translate('boxsets')),
                                  message=boxset['Name'])
                    obj.boxset(boxset)

    def refresh_boxsets(self, library):

        ''' Delete all existing boxsets and re-add.
        '''
        with self.video_database_locks() as (videodb, jellyfindb):
            obj = Movies(self.server, jellyfindb, videodb, self.direct_path, library)
            obj.boxsets_reset()

        self.boxsets(library)

    @progress(translate(33144))
    def remove_library(self, library_id, dialog):

        ''' Remove library by their id from the Kodi database.
        '''
        direct_path = self.library.direct_path

        with Database('jellyfin') as jellyfindb:

            db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)
            library = db.get_view(library_id.replace('Mixed:', ""))
            items = db.get_item_by_media_folder(library_id.replace('Mixed:', ""))
            media = 'music' if library.media_type == 'music' else 'video'

            if media == 'music':
                settings('MusicRescan.bool', False)

            if items:
                with self.library.music_database_lock if media == 'music' else self.library.database_lock:
                    with Database(media) as kodidb:

                        count = 0

                        if library.media_type == 'mixed':

                            movies = [x for x in items if x[1] == 'Movie']
                            tvshows = [x for x in items if x[1] == 'Series']

                            obj = Movies(self.server, jellyfindb, kodidb, direct_path, library).remove

                            for item in movies:

                                obj(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (translate('addon_name'), library.view_name))
                                count += 1

                            obj = TVShows(self.server, jellyfindb, kodidb, direct_path, library).remove

                            for item in tvshows:

                                obj(item[0])
                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (translate('addon_name'), library.view_name))
                                count += 1
                        else:
                            default_args = (self.server, jellyfindb, kodidb, direct_path)
                            for item in items:
                                if item[1] in ('Series', 'Season', 'Episode'):
                                    TVShows(*default_args).remove(item[0])
                                elif item[1] in ('Movie', 'BoxSet'):
                                    Movies(*default_args).remove(item[0])
                                elif item[1] in ('MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                                    Music(*default_args).remove(item[0])
                                elif item[1] == 'MusicVideo':
                                    MusicVideos(*default_args).remove(item[0])

                                dialog.update(int((float(count) / float(len(items)) * 100)), heading="%s: %s" % (translate('addon_name'), library[0]))
                                count += 1

        self.sync = get_sync()

        if library_id in self.sync['Whitelist']:
            self.sync['Whitelist'].remove(library_id)

        elif 'Mixed:%s' % library_id in self.sync['Whitelist']:
            self.sync['Whitelist'].remove('Mixed:%s' % library_id)

        save_sync(self.sync)

    def __exit__(self, exc_type, exc_val, exc_tb):

        ''' Exiting sync
        '''
        self.running = False
        window('jellyfin_sync', clear=True)

        if not settings('dbSyncScreensaver.bool') and self.screensaver is not None:

            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            set_screensaver(value=self.screensaver)

        LOG.info("--<[ fullsync ]")
