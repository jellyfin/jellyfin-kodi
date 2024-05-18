# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

import threading
from datetime import datetime, timedelta

from six.moves import queue as Queue

from kodi_six import xbmc, xbmcgui

from .objects import Movies, TVShows, MusicVideos, Music
from .objects.kodi import Movies as KodiDb
from .database import Database, jellyfin_db, get_sync, save_sync
from .full_sync import FullSync
from .views import Views
from .downloader import GetItemWorker
from .helper import translate, api, stop, settings, window, dialog, event, LazyLogger
from .helper.utils import split_list, set_screensaver, get_screensaver
from .helper.exceptions import LibraryException
from .jellyfin import Jellyfin

##################################################################################################

LOG = LazyLogger(__name__)
LIMIT = int(settings('limitIndex') or 15)
DTHREADS = int(settings('limitThreads') or 3)
TARGET_DB_VERSION = 1

##################################################################################################


class Library(threading.Thread):

    started = False
    stop_thread = False
    suspend = False
    pending_refresh = False
    screensaver = None
    progress_updates = None
    total_updates = 0

    def __init__(self, monitor):

        self.direct_path = settings('useDirectPaths') == "1"
        self.progress_display = int(settings('syncProgress') or 50)
        self.monitor = monitor
        self.player = monitor.monitor.player
        self.server = Jellyfin().get_client()
        self.updated_queue = Queue.Queue()
        self.userdata_queue = Queue.Queue()
        self.removed_queue = Queue.Queue()
        self.updated_output = self.__new_queues__()
        self.userdata_output = self.__new_queues__()
        self.removed_output = self.__new_queues__()
        self.notify_output = Queue.Queue()

        self.jellyfin_threads = []
        self.download_threads = []
        self.notify_threads = []
        self.writer_threads = {'updated': [], 'userdata': [], 'removed': []}
        self.database_lock = threading.Lock()
        self.music_database_lock = threading.Lock()

        threading.Thread.__init__(self)

    def __new_queues__(self):
        return {
            'Movie': Queue.Queue(),
            'BoxSet': Queue.Queue(),
            'MusicVideo': Queue.Queue(),
            'Series': Queue.Queue(),
            'Season': Queue.Queue(),
            'Episode': Queue.Queue(),
            'MusicAlbum': Queue.Queue(),
            'MusicArtist': Queue.Queue(),
            'AlbumArtist': Queue.Queue(),
            'Audio': Queue.Queue()
        }

    def run(self):

        LOG.info("--->[ library ]")

        if not self.startup():
            self.stop_client()

        window('jellyfin_startup.bool', True)

        while not self.stop_thread:

            try:
                self.service()
            except LibraryException:
                break
            except Exception as error:
                LOG.exception(error)

                break

            if self.monitor.waitForAbort(2):
                break

        LOG.info("---<[ library ]")

    def test_databases(self):

        ''' Open the databases to test if the file exists.
        '''
        with Database('video'), Database('music'):
            pass

    def check_version(self):
        '''
        Checks database version and triggers any required data migrations
        '''
        with Database('jellyfin') as jellyfindb:
            db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)
            db_version = db.get_version()

            if not db_version:
                # Make sure we always have a version in the database
                db.add_version((TARGET_DB_VERSION))

        # Video Database Migrations
        with Database('video') as videodb:
            vid_db = KodiDb(videodb.cursor)
            if vid_db.migrations():
                LOG.info('changes detected, reloading skin')
                xbmc.executebuiltin('UpdateLibrary(video)')
                xbmc.executebuiltin('ReloadSkin()')

    @stop
    def service(self):

        ''' If error is encountered, it will rerun this function.
            Start new "daemon threads" to process library updates.
            (actual daemon thread is not supported in Kodi)
        '''
        self.download_threads = [thread for thread in self.download_threads if not thread.is_done]
        self.writer_threads['updated'] = [thread for thread in self.writer_threads['updated'] if not thread.is_done]
        self.writer_threads['userdata'] = [thread for thread in self.writer_threads['userdata'] if not thread.is_done]
        self.writer_threads['removed'] = [thread for thread in self.writer_threads['removed'] if not thread.is_done]

        if not self.player.isPlayingVideo() or settings('syncDuringPlay.bool') or xbmc.getCondVisibility('VideoPlayer.Content(livetv)'):

            self.worker_downloads()
            self.worker_sort()

            self.worker_updates()
            self.worker_userdata()
            self.worker_remove()
            self.worker_notify()

        if self.pending_refresh:
            window('jellyfin_sync.bool', True)

            if self.total_updates > self.progress_display:
                queue_size = self.worker_queue_size()

                if self.progress_updates is None:

                    self.progress_updates = xbmcgui.DialogProgressBG()
                    self.progress_updates.create(translate('addon_name'), translate(33178))
                    self.progress_updates.update(int((float(self.total_updates - queue_size) / float(self.total_updates)) * 100), message="%s: %s" % (translate(33178), queue_size))
                elif queue_size:
                    self.progress_updates.update(int((float(self.total_updates - queue_size) / float(self.total_updates)) * 100), message="%s: %s" % (translate(33178), queue_size))
                else:
                    self.progress_updates.update(int((float(self.total_updates - queue_size) / float(self.total_updates)) * 100), message=translate(33178))

            if not settings('dbSyncScreensaver.bool') and self.screensaver is None:

                xbmc.executebuiltin('InhibitIdleShutdown(true)')
                self.screensaver = get_screensaver()
                set_screensaver(value="")

        if (self.pending_refresh and not self.download_threads and not self.writer_threads['updated'] and not self.writer_threads['userdata'] and not self.writer_threads['removed']):
            self.pending_refresh = False
            self.save_last_sync()
            self.total_updates = 0
            window('jellyfin_sync', clear=True)

            if self.progress_updates:

                self.progress_updates.close()
                self.progress_updates = None

            if not settings('dbSyncScreensaver.bool') and self.screensaver is not None:

                xbmc.executebuiltin('InhibitIdleShutdown(false)')
                set_screensaver(value=self.screensaver)
                self.screensaver = None

            if xbmc.getCondVisibility('Container.Content(musicvideos)'):  # Prevent cursor from moving
                xbmc.executebuiltin('Container.Refresh')
            else:  # Update widgets
                xbmc.executebuiltin('UpdateLibrary(video)')

                if xbmc.getCondVisibility('Window.IsMedia'):
                    xbmc.executebuiltin('Container.Refresh')

    def stop_client(self):
        self.stop_thread = True

    def enable_pending_refresh(self):

        ''' When there's an active thread. Let the main thread know.
        '''
        self.pending_refresh = True
        window('jellyfin_sync.bool', True)

    def worker_queue_size(self):

        ''' Get how many items are queued up for worker threads.
        '''
        total = 0

        for queues in self.updated_output:
            total += self.updated_output[queues].qsize()

        for queues in self.userdata_output:
            total += self.userdata_output[queues].qsize()

        for queues in self.removed_output:
            total += self.removed_output[queues].qsize()

        return total

    def worker_downloads(self):

        ''' Get items from jellyfin and place them in the appropriate queues.
        '''
        for queue in ((self.updated_queue, self.updated_output), (self.userdata_queue, self.userdata_output)):
            if queue[0].qsize() and len(self.download_threads) < DTHREADS:

                new_thread = GetItemWorker(self.server, queue[0], queue[1])
                new_thread.start()
                LOG.info("-->[ q:download/%s ]", id(new_thread))
                self.download_threads.append(new_thread)

    def worker_sort(self):

        ''' Get items based on the local jellyfin database and place item in appropriate queues.
        '''
        if self.removed_queue.qsize() and len(self.jellyfin_threads) < 2:

            new_thread = SortWorker(self.removed_queue, self.removed_output)
            new_thread.start()
            LOG.info("-->[ q:sort/%s ]", id(new_thread))

    def worker_updates(self):

        ''' Update items in the Kodi database.
        '''
        for queues in self.updated_output:
            queue = self.updated_output[queues]

            if queue.qsize() and not len(self.writer_threads['updated']):

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UpdateWorker(queue, self.notify_output, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = UpdateWorker(queue, self.notify_output, self.database_lock, "video", self.server, self.direct_path)

                new_thread.start()
                LOG.info("-->[ q:updated/%s/%s ]", queues, id(new_thread))
                self.writer_threads['updated'].append(new_thread)
                self.enable_pending_refresh()

    def worker_userdata(self):

        ''' Update userdata in the Kodi database.
        '''
        for queues in self.userdata_output:
            queue = self.userdata_output[queues]

            if queue.qsize() and not len(self.writer_threads['userdata']):

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UserDataWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = UserDataWorker(queue, self.database_lock, "video", self.server, self.direct_path)

                new_thread.start()
                LOG.info("-->[ q:userdata/%s/%s ]", queues, id(new_thread))
                self.writer_threads['userdata'].append(new_thread)
                self.enable_pending_refresh()

    def worker_remove(self):

        ''' Remove items from the Kodi database.
        '''
        for queues in self.removed_output:
            queue = self.removed_output[queues]

            if queue.qsize() and not len(self.writer_threads['removed']):

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = RemovedWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = RemovedWorker(queue, self.database_lock, "video", self.server, self.direct_path)

                new_thread.start()
                LOG.info("-->[ q:removed/%s/%s ]", queues, id(new_thread))
                self.writer_threads['removed'].append(new_thread)
                self.enable_pending_refresh()

    def worker_notify(self):

        ''' Notify the user of new additions.
        '''
        if self.notify_output.qsize() and not len(self.notify_threads):

            new_thread = NotifyWorker(self.notify_output, self.player)
            new_thread.start()
            LOG.info("-->[ q:notify/%s ]", id(new_thread))
            self.notify_threads.append(new_thread)

    def startup(self):

        ''' Run at startup.
            Check databases.
            Check for the server plugin.
        '''
        self.test_databases()
        self.check_version()

        Views().get_views()
        Views().get_nodes()

        try:
            if get_sync()['Libraries']:

                try:
                    with FullSync(self, self.server) as sync:
                        sync.libraries()

                    Views().get_nodes()
                except Exception as error:
                    LOG.exception(error)

            elif not settings('SyncInstallRunDone.bool'):

                with FullSync(self, self.server) as sync:
                    sync.libraries()

                Views().get_nodes()

                return True

            if settings('SyncInstallRunDone.bool') and settings(
                'kodiCompanion.bool'
            ):
                # None == Unknown
                if self.server.jellyfin.check_companion_enabled() is not False:

                    if not self.fast_sync():
                        dialog("ok", "{jellyfin}", translate(33128))

                        raise Exception("Failed to retrieve latest updates")

                    LOG.info("--<[ retrieve changes ]")

                # is False
                else:
                    dialog("ok", "{jellyfin}", translate(33099))
                    settings("kodiCompanion.bool", False)
                    return True

            return True
        except LibraryException as error:
            LOG.error(error.status)

            if error.status in 'SyncLibraryLater':

                dialog("ok", "{jellyfin}", translate(33129))
                settings('SyncInstallRunDone.bool', True)
                sync = get_sync()
                sync['Libraries'] = []
                save_sync(sync)

                return True

        except Exception as error:
            LOG.exception(error)

        return False

    def fast_sync(self):

        ''' Movie and userdata not provided by server yet.
        '''
        last_sync = settings('LastIncrementalSync')
        include = []
        filters = ["tvshows", "boxsets", "musicvideos", "music", "movies"]
        sync = get_sync()
        whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
        LOG.info("--[ retrieve changes ] %s", last_sync)

        # Get the item type of each synced library and build list of types to request
        for item_id in whitelist:
            library = self.server.jellyfin.get_item(item_id)
            library_type = library.get('CollectionType')
            if library_type in filters:
                include.append(library_type)

        # Include boxsets if movies are synced
        if 'movies' in include:
            include.append('boxsets')

        # Filter down to the list of library types we want to exclude
        query_filter = list(set(filters) - set(include))

        try:
            # Get list of updates from server for synced library types and populate work queues
            result = self.server.jellyfin.get_sync_queue(last_sync, ",".join([x for x in query_filter]))

            if result is None:
                return True

            updated = []
            userdata = []
            removed = []

            updated.extend(result['ItemsAdded'])
            updated.extend(result['ItemsUpdated'])
            userdata.extend(result['UserDataChanged'])
            removed.extend(result['ItemsRemoved'])

            total = len(updated) + len(userdata)

            if total > int(settings('syncIndicator') or 99):

                ''' Inverse yes no, in case the dialog is forced closed by Kodi.
                '''
                if dialog("yesno", "{jellyfin}", translate(33172).replace('{number}', str(total)), nolabel=translate(107), yeslabel=translate(106)):
                    LOG.warning("Large updates skipped.")

                    return True

            self.updated(updated)
            self.userdata(userdata)
            self.removed(removed)

        except Exception as error:
            LOG.exception(error)

            return False

        return True

    def save_last_sync(self):

        try:
            time_now = datetime.strptime(self.server.config.data['server-time'].split(', ', 1)[1], '%d %b %Y %H:%M:%S GMT') - timedelta(minutes=2)
        except Exception as error:

            LOG.exception(error)
            time_now = datetime.utcnow() - timedelta(minutes=2)

        last_sync = time_now.strftime('%Y-%m-%dT%H:%M:%Sz')
        settings('LastIncrementalSync', value=last_sync)
        LOG.info("--[ sync/%s ]", last_sync)

    def select_libraries(self, mode=None):

        ''' Select from libraries synced. Either update or repair libraries.
            Send event back to service.py
        '''
        modes = {
            'SyncLibrarySelection': 'SyncLibrary',
            'RepairLibrarySelection': 'RepairLibrary',
            'AddLibrarySelection': 'SyncLibrary',
            'RemoveLibrarySelection': 'RemoveLibrary'
        }
        sync = get_sync()
        whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
        libraries = []

        with Database('jellyfin') as jellyfindb:
            db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)

            if mode in ('SyncLibrarySelection', 'RepairLibrarySelection', 'RemoveLibrarySelection'):
                for library in sync['Whitelist']:

                    name = db.get_view_name(library.replace('Mixed:', ""))
                    libraries.append({'Id': library, 'Name': name})
            else:
                available = [x for x in sync['SortedViews'] if x not in whitelist]

                for library in available:
                    view = db.get_view(library)

                    if view.media_type in ('movies', 'tvshows', 'musicvideos', 'mixed', 'music'):
                        libraries.append({'Id': view.view_id, 'Name': view.view_name})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, translate(33121))

        titles = {
            "RepairLibrarySelection": 33199,
            "SyncLibrarySelection": 33198,
            "RemoveLibrarySelection": 33200,
            "AddLibrarySelection": 33120
        }
        title = titles.get(mode, "Failed to get title {}".format(mode))

        selection = dialog("multi", translate(title), choices)

        if selection is None:
            return

        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        selected_libraries = []

        for x in selection:

            library = libraries[x - 1]
            selected_libraries.append(library['Id'])

        event(modes[mode], {'Id': ','.join([libraries[x - 1]['Id'] for x in selection]), 'Update': mode == 'SyncLibrarySelection'})

    def add_library(self, library_id, update=False):

        try:
            with FullSync(self, server=self.server) as sync:
                sync.libraries(library_id, update)
        except Exception as error:
            LOG.exception(error)

            return False

        Views().get_nodes()

        return True

    def remove_library(self, library_id):

        try:
            with FullSync(self, self.server) as sync:
                sync.remove_library(library_id)

            Views().remove_library(library_id)
        except Exception as error:
            LOG.exception(error)

            return False

        Views().get_views()
        Views().get_nodes()

        return True

    def userdata(self, data):

        ''' Add item_id to userdata queue.
        '''
        if not data:
            return

        items = [x['ItemId'] for x in data]

        for item in split_list(items, LIMIT):
            self.userdata_queue.put(item)

        self.total_updates += len(items)
        LOG.info("---[ userdata:%s ]", len(items))

    def updated(self, data):

        ''' Add item_id to updated queue.
        '''
        if not data:
            return

        for item in split_list(data, LIMIT):
            self.updated_queue.put(item)

        self.total_updates += len(data)
        LOG.info("---[ updated:%s ]", len(data))

    def removed(self, data):

        ''' Add item_id to removed queue.
        '''
        if not data:
            return

        for item in data:

            if item in list(self.removed_queue.queue):
                continue

            self.removed_queue.put(item)

        self.total_updates += len(data)
        LOG.info("---[ removed:%s ]", len(data))


class UpdateWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, notify, lock, database, server=None, direct_path=None, *args):
        self.queue = queue
        self.notify_output = notify
        self.notify = settings('newContent.bool')
        self.lock = lock
        self.database = Database(database)
        self.args = args
        self.server = server
        self.direct_path = direct_path
        threading.Thread.__init__(self)

    def run(self):
        with self.lock, self.database as kodidb, Database('jellyfin') as jellyfindb:
            default_args = (self.server, jellyfindb, kodidb, self.direct_path)
            if kodidb.db_file == "video":
                movies = Movies(*default_args)
                tvshows = TVShows(*default_args)
                musicvideos = MusicVideos(*default_args)
            elif kodidb.db_file == "music":
                music = Music(*default_args)
            else:
                # this should not happen
                LOG.error('"{}" is not a valid Kodi library type.'.format(kodidb.db_file))
                return

            while True:

                try:
                    item = self.queue.get(timeout=1)
                except Queue.Empty:
                    break

                try:
                    LOG.debug('{} - {}'.format(item['Type'], item['Name']))
                    if item['Type'] == 'Movie':
                        movies.movie(item)
                    elif item['Type'] == 'BoxSet':
                        movies.boxset(item)
                    elif item['Type'] == 'Series':
                        tvshows.tvshow(item)
                    elif item['Type'] == 'Season':
                        tvshows.season(item)
                    elif item['Type'] == 'Episode':
                        tvshows.episode(item)
                    elif item['Type'] == 'MusicVideo':
                        musicvideos.musicvideo(item)
                    elif item['Type'] == 'MusicAlbum':
                        music.album(item)
                    elif item['Type'] == 'MusicArtist':
                        music.artist(item)
                    elif item['Type'] == 'AlbumArtist':
                        music.albumartist(item)
                    elif item['Type'] == 'Audio':
                        music.song(item)

                    if self.notify:
                        self.notify_output.put((item['Type'], api.API(item).get_naming()))
                except LibraryException as error:
                    if error.status == 'StopCalled':
                        break
                except Exception as error:
                    LOG.exception(error)

                self.queue.task_done()

                if window('jellyfin_should_stop.bool'):
                    break

        LOG.info("--<[ q:updated/%s ]", id(self))
        self.is_done = True


class UserDataWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, server, direct_path):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.server = server
        self.direct_path = direct_path

        threading.Thread.__init__(self)

    def run(self):

        with self.lock, self.database as kodidb, Database('jellyfin') as jellyfindb:
            default_args = (self.server, jellyfindb, kodidb, self.direct_path)
            if kodidb.db_file == "video":
                movies = Movies(*default_args)
                tvshows = TVShows(*default_args)
            elif kodidb.db_file == "music":
                music = Music(*default_args)
            else:
                # this should not happen
                LOG.error('"{}" is not a valid Kodi library type.'.format(kodidb.db_file))
                return

            while True:

                try:
                    item = self.queue.get(timeout=1)
                except Queue.Empty:
                    break

                try:
                    if item['Type'] == 'Movie':
                        movies.userdata(item)
                    elif item['Type'] in ['Series', 'Season', 'Episode']:
                        tvshows.userdata(item)
                    elif item['Type'] == 'MusicAlbum':
                        music.album(item)
                    elif item['Type'] == 'MusicArtist':
                        music.artist(item)
                    elif item['Type'] == 'AlbumArtist':
                        music.albumartist(item)
                    elif item['Type'] == 'Audio':
                        music.userdata(item)
                except LibraryException as error:
                    if error.status == 'StopCalled':
                        break
                except Exception as error:
                    LOG.exception(error)

                self.queue.task_done()

                if window('jellyfin_should_stop.bool'):
                    break

        LOG.info("--<[ q:userdata/%s ]", id(self))
        self.is_done = True


class SortWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, output, *args):

        self.queue = queue
        self.output = output
        self.args = args
        threading.Thread.__init__(self)

    def run(self):

        with Database('jellyfin') as jellyfindb:
            database = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)

            while True:

                try:
                    item_id = self.queue.get(timeout=1)
                except Queue.Empty:
                    break

                try:
                    media = database.get_media_by_id(item_id)
                    if media:
                        self.output[media].put({'Id': item_id, 'Type': media})
                    else:
                        items = database.get_media_by_parent_id(item_id)

                        if not items:
                            LOG.info("Could not find media %s in the jellyfin database.", item_id)
                        else:
                            for item in items:
                                self.output[item[1]].put({'Id': item[0], 'Type': item[1]})
                except Exception as error:
                    LOG.exception(error)

                self.queue.task_done()

                if window('jellyfin_should_stop.bool'):
                    break

        LOG.info("--<[ q:sort/%s ]", id(self))
        self.is_done = True


class RemovedWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, server, direct_path):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.server = server
        self.direct_path = direct_path
        threading.Thread.__init__(self)

    def run(self):

        with self.lock, self.database as kodidb, Database('jellyfin') as jellyfindb:
            default_args = (self.server, jellyfindb, kodidb, self.direct_path)
            if kodidb.db_file == "video":
                movies = Movies(*default_args)
                tvshows = TVShows(*default_args)
                musicvideos = MusicVideos(*default_args)
            elif kodidb.db_file == "music":
                music = Music(*default_args)
            else:
                # this should not happen
                LOG.error('"{}" is not a valid Kodi library type.'.format(kodidb.db_file))
                return

            while True:

                try:
                    item = self.queue.get(timeout=1)
                except Queue.Empty:
                    break

                if item['Type'] == 'Movie':
                    obj = movies.remove
                elif item['Type'] in ['Series', 'Season', 'Episode']:
                    obj = tvshows.remove
                elif item['Type'] in ['MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio']:
                    obj = music.remove
                elif item['Type'] == 'MusicVideo':
                    obj = musicvideos.remove

                try:
                    obj(item['Id'])
                except LibraryException as error:
                    if error.status == 'StopCalled':
                        break
                except Exception as error:
                    LOG.exception(error)
                finally:
                    self.queue.task_done()

                if window('jellyfin_should_stop.bool'):
                    break

        LOG.info("--<[ q:removed/%s ]", id(self))
        self.is_done = True


class NotifyWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, player):

        self.queue = queue
        self.video_time = int(settings('newvideotime')) * 1000
        self.music_time = int(settings('newmusictime')) * 1000
        self.player = player
        threading.Thread.__init__(self)

    def run(self):

        while True:

            try:
                item = self.queue.get(timeout=3)
            except Queue.Empty:
                break

            time = self.music_time if item[0] == 'Audio' else self.video_time

            if time and (not self.player.isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)')):
                dialog("notification", heading="%s %s" % (translate(33049), item[0]), message=item[1],
                       icon="{jellyfin}", time=time, sound=False)

            self.queue.task_done()

            if window('jellyfin_should_stop.bool'):
                break

        LOG.info("--<[ q:notify/%s ]", id(self))
        self.is_done = True
