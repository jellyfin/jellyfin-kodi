# -*- coding: utf-8 -*-

##################################################################################################

import datetime
import json
import logging
import os

import xbmc
import xbmcvfs

import downloader as server
import helper.xmls as xmls
from database import Database, get_sync, save_sync, emby_db
from helper import _, settings, window, progress, dialog, LibraryException
from helper.utils import get_screensaver, set_screensaver
from views import Views

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class FullSync(object):

    ''' This should be called like a context.
        i.e. with FullSync('emby') as sync:
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
            dialog("ok", heading="{emby}", line1=_(33197))

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
        window('emby_sync.bool', True)

        return self


    def libraries(self, library_id=None, update=False):

        ''' Map the syncing process and start the sync. Ensure only one sync is running.
        '''
        self.direct_path = settings('useDirectPaths') == "1"
        self.update_library = update
        self.sync = get_sync()

        if library_id:
            libraries = library_id.split(',')

            for selected in libraries:

                if selected not in [x.replace('Mixed:', "") for x in self.sync['Libraries']]:
                    library = self.get_libraries(selected)

                    if library:

                        self.sync['Libraries'].append("Mixed:%s" % selected if library[1] == 'mixed' else selected)

                        if library[1] in ('mixed', 'movies'):
                            self.sync['Libraries'].append('Boxsets:%s' % selected)
                    else:
                        self.sync['Libraries'].append(selected)
        else:
            self.mapping()

        xmls.sources()

        if not xmls.advanced_settings() and self.sync['Libraries']:
            self.start()

    def get_libraries(self, library_id=None):

        with Database('emby') as embydb:
            if library_id is None:
                return emby_db.EmbyDatabase(embydb.cursor).get_views()
            else:
                return emby_db.EmbyDatabase(embydb.cursor).get_view(library_id)

    def mapping(self):

        ''' Load the mapping of the full sync.
            This allows us to restore a previous sync.
        '''
        if self.sync['Libraries']:

            if not dialog("yesno", heading="{emby}", line1=_(33102)):

                if not dialog("yesno", heading="{emby}", line1=_(33173)):
                    dialog("ok", heading="{emby}", line1=_(33122))

                    raise LibraryException("ProgressStopped")
                else:
                    self.sync['Libraries'] = []
                    self.sync['RestorePoint'] = {}
        else:
            LOG.info("generate full sync")
            libraries = []

            for library in self.get_libraries():

                if library[2] in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed'):
                    libraries.append({'Id': library[0], 'Name': library[1], 'Media': library[2]})

            libraries = self.select_libraries(libraries)

            if [x['Media'] for x in libraries if x['Media'] in ('movies', 'mixed')]:
                self.sync['Libraries'].append("Boxsets:")

        save_sync(self.sync)

    def select_libraries(self, libraries):

        ''' Select all or certain libraries to be whitelisted.
        '''
        if dialog("yesno", heading="{emby}", line1=_(33125), nolabel=_(33127), yeslabel=_(33126)):
            LOG.info("Selected sync later.")

            raise LibraryException('SyncLibraryLater')

        choices = [x['Name'] for x in libraries]
        choices.insert(0, _(33121))
        selection = dialog("multi", _(33120), choices)

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
        dialog("notification", heading="{emby}", message="%s %s" % (_(33025), str(elapsed).split('.')[0]),
               icon="{emby}", sound=False)
        LOG.info("Full sync completed in: %s", str(elapsed).split('.')[0])

    def process_library(self, library_id):

        ''' Add a library by it's id. Create a node and a playlist whenever appropriate.
        '''
        media = {
            'movies': self.movies,
            'musicvideos': self.musicvideos,
            'tvshows': self.tvshows,
            'music': self.music
        }
        try:
            if library_id.startswith('Boxsets:'):

                if library_id.endswith('Refresh'):
                    self.refresh_boxsets()
                else:
                    self.boxsets(library_id.split('Boxsets:')[1] if len(library_id) > len('Boxsets:') else None)

                return

            library = self.server['api'].get_item(library_id.replace('Mixed:', ""))

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

        except Exception as error:

            if not 'Failed to validate path' in error:

                dialog("ok", heading="{emby}", line1=_(33119))
                LOG.error("full sync exited unexpectedly")
                save_sync(self.sync)

            raise

    @progress()
    def movies(self, library, dialog):

        ''' Process movies from a single library.
        '''
        Movies = self.library.media['Movies']

        with self.library.database_lock:
            with Database() as videodb:
                with Database('emby') as embydb:

                    obj = Movies(self.server, embydb, videodb, self.direct_path)

                    for items in server.get_items(library['Id'], "Movie", False, self.sync['RestorePoint'].get('params')):
                        
                        self.sync['RestorePoint'] = items['RestorePoint']
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, movie in enumerate(items['Items']):

                            dialog.update(int((float(start_index + index) / float(items['TotalRecordCount']))*100),
                                          heading="%s: %s" % (_('addon_name'), library['Name']),
                                          message=movie['Name'])
                            obj.movie(movie, library=library)

                    if self.update_library:
                        self.movies_compare(library, obj, embydb)

    def movies_compare(self, library, obj, embydb):

        ''' Compare entries from library to what's in the embydb. Remove surplus
        '''
        db = emby_db.EmbyDatabase(embydb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'Movie':
                obj.remove(x[0])

    @progress()
    def tvshows(self, library, dialog):

        ''' Process tvshows and episodes from a single library.
        '''
        TVShows = self.library.media['TVShows']

        with self.library.database_lock:
            with Database() as videodb:
                with Database('emby') as embydb:
                    obj = TVShows(self.server, embydb, videodb, self.direct_path, True)

                    for items in server.get_items(library['Id'], "Series", False, self.sync['RestorePoint'].get('params')):

                        self.sync['RestorePoint'] = items['RestorePoint']
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, show in enumerate(items['Items']):

                            percent = int((float(start_index + index) / float(items['TotalRecordCount']))*100)
                            message = show['Name']
                            dialog.update(percent, heading="%s: %s" % (_('addon_name'), library['Name']), message=message)

                            if obj.tvshow(show, library=library) != False:

                                for episodes in server.get_episode_by_show(show['Id']):
                                    for episode in episodes['Items']:

                                        dialog.update(percent, message="%s/%s" % (message, episode['Name'][:10]))
                                        obj.episode(episode)

                    if self.update_library:
                        self.tvshows_compare(library, obj, embydb)

    def tvshows_compare(self, library, obj, embydb):

        ''' Compare entries from library to what's in the embydb. Remove surplus
        '''
        db = emby_db.EmbyDatabase(embydb.cursor)

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
        MusicVideos = self.library.media['MusicVideos']

        with self.library.database_lock:
            with Database() as videodb:
                with Database('emby') as embydb:
                    obj = MusicVideos(self.server, embydb, videodb, self.direct_path)

                    for items in server.get_items(library['Id'], "MusicVideo", False, self.sync['RestorePoint'].get('params')):

                        self.sync['RestorePoint'] = items['RestorePoint']
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, mvideo in enumerate(items['Items']):

                            dialog.update(int((float(start_index + index) / float(items['TotalRecordCount']))*100),
                                          heading="%s: %s" % (_('addon_name'), library['Name']),
                                          message=mvideo['Name'])
                            obj.musicvideo(mvideo, library=library)

                    if self.update_library:
                        self.musicvideos_compare(library, obj, embydb)

    def musicvideos_compare(self, library, obj, embydb):

        ''' Compare entries from library to what's in the embydb. Remove surplus
        '''
        db = emby_db.EmbyDatabase(embydb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'MusicVideo':
                obj.remove(x[0])

    @progress()
    def music(self, library, dialog):

        ''' Process artists, album, songs from a single library.
        '''
        Music = self.library.media['Music']

        with self.library.music_database_lock:
            with Database('music') as musicdb:
                with Database('emby') as embydb:
                    obj = Music(self.server, embydb, musicdb, self.direct_path)

                    for items in server.get_artists(library['Id'], False, self.sync['RestorePoint'].get('params')):

                        self.sync['RestorePoint'] = items['RestorePoint']
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, artist in enumerate(items['Items']):

                            percent = int((float(start_index + index) / float(items['TotalRecordCount']))*100)
                            message = artist['Name']
                            dialog.update(percent, heading="%s: %s" % (_('addon_name'), library['Name']), message=message)
                            obj.artist(artist, library=library)

                            for albums in server.get_albums_by_artist(artist['Id']):
                                
                                for album in albums['Items']:
                                    obj.album(album)

                                    for songs in server.get_items(album['Id'], "Audio"):
                                        for song in songs['Items']:

                                            dialog.update(percent,
                                                          message="%s/%s/%s" % (message, album['Name'][:7], song['Name'][:7]))
                                            obj.song(song)

                            for songs in server.get_songs_by_artist(artist['Id']):
                                for song in songs['Items']:

                                    dialog.update(percent, message="%s/%s" % (message, song['Name']))
                                    obj.song(song)


                    if self.update_library:
                        self.music_compare(library, obj, embydb)

    def music_compare(self, library, obj, embydb):

        ''' Compare entries from library to what's in the embydb. Remove surplus
        '''
        db = emby_db.EmbyDatabase(embydb.cursor)

        items = db.get_item_by_media_folder(library['Id'])
        for x in list(items):
            items.extend(obj.get_child(x[0]))

        current = obj.item_ids

        for x in items:
            if x[0] not in current and x[1] == 'MusicArtist':
                obj.remove(x[0])

    @progress(_(33018))
    def boxsets(self, library_id=None, dialog=None):

        ''' Process all boxsets.
        '''
        Movies = self.library.media['Movies']

        with self.library.database_lock:
            with Database() as videodb:
                with Database('emby') as embydb:
                    obj = Movies(self.server, embydb, videodb, self.direct_path)

                    for items in server.get_items(library_id, "BoxSet", False, self.sync['RestorePoint'].get('params')):

                        self.sync['RestorePoint'] = items['RestorePoint']
                        start_index = items['RestorePoint']['params']['StartIndex']

                        for index, boxset in enumerate(items['Items']):

                            dialog.update(int((float(start_index + index) / float(items['TotalRecordCount']))*100),
                                          heading="%s: %s" % (_('addon_name'), _('boxsets')),
                                          message=boxset['Name'])
                            obj.boxset(boxset)

    def refresh_boxsets(self):

        ''' Delete all exisitng boxsets and re-add.
        '''
        Movies = self.library.media['Movies']

        with self.library.database_lock:
            with Database() as videodb:
                with Database('emby') as embydb:

                    obj = Movies(self.server, embydb, videodb, self.direct_path)
                    obj.boxsets_reset()

        self.boxsets(None)

    @progress(_(33144))
    def remove_library(self, library_id, dialog):

        ''' Remove library by their id from the Kodi database.
        '''
        MEDIA = self.library.MEDIA
        direct_path = self.library.direct_path

        with Database('emby') as embydb:

            db = emby_db.EmbyDatabase(embydb.cursor)
            library = db.get_view(library_id.replace('Mixed:', ""))
            items = db.get_item_by_media_folder(library_id.replace('Mixed:', ""))
            media = 'music' if library[1] == 'music' else 'video'

            if media == 'music':
                settings('MusicRescan.bool', False)

            if items:
                count = 0

                with self.library.music_database_lock if media == 'music' else self.library.database_lock:
                    with Database(media) as kodidb:

                        if library[1] == 'mixed':

                            movies = [x for x in items if x[1] == 'Movie']
                            tvshows = [x for x in items if x[1] == 'Series']

                            obj = MEDIA['Movie'](self.server, embydb, kodidb, direct_path)['Remove']

                            for item in movies:

                                obj(item[0])
                                dialog.update(int((float(count) / float(len(items))*100)), heading="%s: %s" % (_('addon_name'), library[0]))
                                count += 1

                            obj = MEDIA['Series'](self.server, embydb, kodidb, direct_path)['Remove']

                            for item in tvshows:

                                obj(item[0])
                                dialog.update(int((float(count) / float(len(items))*100)), heading="%s: %s" % (_('addon_name'), library[0]))
                                count += 1
                        else:
                            obj = MEDIA[items[0][1]](self.server, embydb, kodidb, direct_path)['Remove']

                            for item in items:

                                obj(item[0])
                                dialog.update(int((float(count) / float(len(items))*100)), heading="%s: %s" % (_('addon_name'), library[0]))
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
        window('emby_sync', clear=True)

        if not settings('dbSyncScreensaver.bool') and self.screensaver is not None:

            xbmc.executebuiltin('InhibitIdleShutdown(false)')
            set_screensaver(value=self.screensaver)

        LOG.info("--<[ fullsync ]")
