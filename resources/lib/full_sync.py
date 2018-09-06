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
from database import Database, get_sync, save_sync
from objects import Movies, TVShows, MusicVideos, Music
from helper import _, settings, progress, dialog, LibraryException
from emby import Emby

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class FullSync(object):

    sync = None

    def __init__(self, library, library_id=None):

        self.library = library
        self.direct_path = settings('useDirectPaths') == "1"

        self.server = Emby()
        self.sync = get_sync()

        if library_id:
            self.sync['Libraries'].append(library_id)
        else:
            self.mapping()

        self.start()

    def mapping(self):

        ''' Load the mapping of the full sync.
            This allows us to restore a previous sync.
        '''
        if self.sync['Libraries']:

            if not dialog("yesno", heading="{emby}", line1=_(33102)):
                dialog("ok", heading="{emby}", line1=_(33122))

                raise LibraryException("ProgressStopped")

        else:
            LOG.info("generate full sync")
            libraries = []

            for library in self.server['api'].get_media_folders()['Items']:
                library['Media'] = library.get('OriginalCollectionType', library.get('CollectionType', "mixed"))

                if library['Type'] in ('Channel', 'PlaylistsFolder') or library['Media'] not in ('movies', 'tvshows', 'musicvideos', 'music', 'mixed'):
                    continue

                libraries.append(library)

            libraries = self.select_libraries(libraries)

            if [x['Media'] for x in libraries if x['Media'] in ('movies', 'mixed')]:
                self.sync['Libraries'].append("Boxsets:")

            save_sync(self.sync)

    def select_libraries(self, libraries):

        ''' Select all or whitelist libraries. Provides a new list.
        '''
        if not dialog("yesno", heading="{emby}", line1=_(33125), nolabel=_(33126), yeslabel=_(33127)):
            raise LibraryException('SyncLibraryLater')

        choices = [x['Name'] for x in libraries]
        choices.insert(0, _(33121))
        selection = dialog("multi", _(33120), choices)

        if selection is None:
            raise LibraryException('LibrarySelection')
        elif not selection:
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
        xmls.sources()
        start_time = datetime.datetime.now()

        for library in list(self.sync['Libraries']):

            self.process_library(library)

            if not library.startswith('Boxsets:'):
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
                    self.boxsets()

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

            dialog("ok", heading="{emby}", line1=_(33119))
            save_sync(self.sync)
            LOG.error("full sync exited unexpectedly")

            raise

    @progress()
    def movies(self, library, dialog):

        ''' Process movies from a single library.
        '''
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

    @progress()
    def tvshows(self, library, dialog):

        ''' Process tvshows and episodes from a single library.
        '''
        with Database() as videodb:
            with Database('emby') as embydb:
                obj = TVShows(self.server, embydb, videodb, self.direct_path)

                for items in server.get_items(library['Id'], "Series", False, self.sync['RestorePoint'].get('params')):

                    self.sync['RestorePoint'] = items['RestorePoint']
                    start_index = items['RestorePoint']['params']['StartIndex']

                    for index, show in enumerate(items['Items']):

                        percent = int((float(start_index + index) / float(items['TotalRecordCount']))*100)
                        message = show['Name']
                        dialog.update(percent, heading="%s: %s" % (_('addon_name'), library['Name']), message=message)

                        if obj.tvshow(show, library=library) != False:

                            for episodes in server.get_items(show['Id'], "Episode"):
                                for episode in episodes['Items']:

                                    dialog.update(percent, message="%s/%s" % (message, episode['Name'][:10]))
                                    obj.episode(episode)

    @progress()
    def musicvideos(self, library, dialog):

        ''' Process musicvideos from a single library.
        '''
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

    @progress()
    def music(self, library, dialog):

        ''' Process artists, album, songs from a single library.
        '''
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

    @progress(_(33018))
    def boxsets(self, dialog):

        ''' Process all boxsets.
        '''
        with Database() as videodb:
            with Database('emby') as embydb:
                obj = Movies(self.server, embydb, videodb, self.direct_path)

                for items in server.get_items(None, "BoxSet", False, self.sync['RestorePoint'].get('params')):

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
        with Database() as videodb:
            with Database('emby') as embydb:

                obj = Movies(self.server, embydb, videodb, self.direct_path)
                obj.boxsets_reset()

        self.boxsets()
