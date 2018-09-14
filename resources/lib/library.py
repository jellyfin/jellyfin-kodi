# -*- coding: utf-8 -*-

##################################################################################################

import logging
import Queue
import threading
import sys
from datetime import datetime, timedelta

import xbmc

from objects import Movies, TVShows, MusicVideos, Music
from database import Database, emby_db, get_sync, save_sync
from full_sync import FullSync
from views import Views
from downloader import GetItemWorker
from helper import _, stop, settings, dialog, event, progress, LibraryException
from emby import Emby

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)
MEDIA = {
    'Movie': Movies,
    'BoxSet': Movies,
    'MusicVideo': MusicVideos,
    'Series': TVShows,
    'Season': TVShows,
    'Episode': TVShows,
    'MusicAlbum': Music,
    'MusicArtist': Music,
    'AlbumArtist': Music,
    'Audio': Music
}

##################################################################################################



class Library(threading.Thread):

    started = False
    stop_thread = False
    suspend = False
    pending_refresh = False


    def __init__(self, monitor):

        self.direct_path = settings('useDirectPaths') == "1"
        self.monitor = monitor
        self.server = Emby()
        self.updated_queue = Queue.Queue()
        self.userdata_queue = Queue.Queue()
        self.removed_queue = Queue.Queue()
        self.updated_output = self.__new_queues__()
        self.userdata_output = self.__new_queues__()
        self.removed_output = self.__new_queues__()

        self.emby_threads = []
        self.download_threads = []
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

        LOG.warn("--->[ library ]")

        if not self.startup():
            self.stop_client()

        while not self.stop_thread:

            try:
                self.service()
            except LibraryException as error:
                break
            except Exception as error:
                LOG.exception(error)

                break

            if self.monitor.waitForAbort(2):
                break

        LOG.warn("---<[ library ]")

    @stop()
    def service(self):
        
        ''' If error is encountered, it will rerun this function.
            Start new "daemon threads" to process library updates.
            (actual daemon thread is not supported in Kodi)
        '''
        active_queues = []

        for threads in (self.download_threads, self.writer_threads['updated'],
                        self.writer_threads['userdata'], self.writer_threads['removed']):
            for thread in threads:
                if thread.is_done:
                    threads.remove(thread)

        for queue in ((self.updated_queue, self.updated_output), (self.userdata_queue, self.userdata_output)):
            if queue[0].qsize() and len(self.download_threads) < 5:
                
                new_thread = GetItemWorker(self.server, queue[0], queue[1])
                new_thread.start()
                LOG.info("-->[ q:download/%s ]", id(new_thread))

        if self.removed_queue.qsize() and len(self.emby_threads) < 2:

            new_thread = SortWorker(self.removed_queue, self.removed_output)
            new_thread.start()
            LOG.info("-->[ q:sort/%s ]", id(new_thread))

        for queues in self.updated_output:
            queue = self.updated_output[queues]

            if queue.qsize() and len(self.writer_threads['updated']) < 4:

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UpdatedWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = UpdatedWorker(queue, self.database_lock, "video", self.server, self.direct_path)

                new_thread.start()
                LOG.info("-->[ q:updated/%s/%s ]", queues, id(new_thread))
                self.writer_threads['updated'].append(new_thread)
                self.pending_refresh = True

        for queues in self.userdata_output:
            queue = self.userdata_output[queues]

            if queue.qsize() and len(self.writer_threads['userdata']) < 4:

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = UserDataWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = UserDataWorker(queue, self.database_lock, "video", self.server, self.direct_path)

                new_thread.start()
                LOG.info("-->[ q:userdata/%s/%s ]", queues, id(new_thread))
                self.writer_threads['userdata'].append(new_thread)
                self.pending_refresh = True

        for queues in self.removed_output:
            queue = self.removed_output[queues]

            if queue.qsize() and len(self.writer_threads['removed']) < 2:

                if queues in ('Audio', 'MusicArtist', 'AlbumArtist', 'MusicAlbum'):
                    new_thread = RemovedWorker(queue, self.music_database_lock, "music", self.server, self.direct_path)
                else:
                    new_thread = RemovedWorker(queue, self.database_lock, "video", self.server, self.direct_path)
                
                new_thread.start()
                LOG.info("-->[ q:removed/%s/%s ]", queues, id(new_thread))
                self.writer_threads['removed'].append(new_thread)
                self.pending_refresh = True
        
        if (self.pending_refresh and not self.download_threads and not self.writer_threads['updated'] and
                                     not self.writer_threads['userdata'] and not self.writer_threads['removed']):
            self.pending_refresh = False
            self.save_last_sync()
            xbmc.executebuiltin('UpdateLibrary(video)')

            """
            if xbmc.getCondVisibility('Window.IsActive(home)'):
                xbmc.executebuiltin('UpdateLibrary(video)')
            else:
                xbmc.executebuiltin('Container.Refresh')
            """

    def stop_client(self):
        self.stop_thread = True

    def startup(self):

        ''' Run at startup. Will check for the server plugin.
        '''
        fast_sync = False
        Views().get_views()
        Views().get_nodes()

        try:
            if not settings('kodiCompanion.bool') and settings('SyncInstallRunDone.bool'):
                return True

            if settings('kodiCompanion.bool'):
                for plugin in self.server['api'].get_plugins():
                    if plugin['Name'] in ("Emby.Kodi Sync Queue", "Kodi companion"):
                        fast_sync = True

                        break
                else:
                    raise LibraryException('CompanionMissing')

            if settings('SyncInstallRunDone.bool'):
                if fast_sync and not self.fast_sync():
                    dialog("ok", heading="{emby}", line1=_(33128))

                    raise Exception("Failed to retrieve latest updates")
            else:
                FullSync(self)
                Views().get_nodes()

            return True

        except LibraryException as error:
            LOG.error(error.status)

            if error.status in 'SyncLibraryLater':

                dialog("ok", heading="{emby}", line1=_(33129))
                settings('SyncInstallRunDone.bool', True)
                sync = get_sync()
                sync['Libraries'] = []
                save_sync(sync)

                return True

            elif error.status == 'CompanionMissing':

                dialog("ok", heading="{emby}", line1=_(33099))
                settings('kodiCompanion.bool', False)

                return True

        except Exception as error:
            LOG.exception(error)

        return False

    def fast_sync(self):

        ''' Movie and userdata not provided by server yet.
        '''
        last_sync = settings('LastIncrementalSync')
        filters = ["tvshows", "boxsets", "musicvideos", "music", "movies"]
        sync = get_sync()
        LOG.info("--[ retrieve changes ] %s", last_sync)

        """
        for library in sync['Whitelist']:

            data = self.server['api'].get_date_modified(last_sync, library.replace('Mixed:', ""), "Series,Episode,BoxSet,Movie,MusicVideo,MusicArtist,MusicAlbum,Audio")
            [self.updated_output[query['Type']].put(query) for query in data['Items']]
        """
        try:
            for media in filters:
                result = self.server['api'].get_sync_queue(last_sync, ",".join([x for x in filters if x != media]))
                self.updated(result['ItemsAdded'])
                self.updated(result['ItemsUpdated'])
                self.userdata(result['UserDataChanged'])
                self.removed(result['ItemsRemoved'])

            """
            result = self.server['api'].get_sync_queue(last_sync)
            self.userdata(result['UserDataChanged'])
            self.removed(result['ItemsRemoved'])

            
            filters.extend(["tvshows", "boxsets", "musicvideos", "music"])

            # Get only movies.
            result = self.server['api'].get_sync_queue(last_sync, ",".join(filters))
            self.updated(result['ItemsAdded'])
            self.updated(result['ItemsUpdated'])
            self.userdata(result['UserDataChanged'])
            self.removed(result['ItemsRemoved'])
            """

        except Exception as error:
            LOG.exception(error)

            return False

        return True

    def save_last_sync(self):

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
            'AddLibrarySelection': 'SyncLibrary'
        }
        sync = get_sync()
        whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
        libraries = []

        with Database('emby') as embydb:
            db = emby_db.EmbyDatabase(embydb.cursor)

            if mode in ('SyncLibrarySelection', 'RepairLibrarySelection'):
                for library in sync['Whitelist']:

                    name = db.get_view_name(library.replace('Mixed:', ""))
                    libraries.append({'Id': library, 'Name': name})
            else:
                available = [x for x in sync['SortedViews'] if x not in whitelist]

                for library in available:
                    name, media  = db.get_view(library)

                    if media in ('movies', 'tvshows', 'musicvideos', 'mixed', 'music'):
                        libraries.append({'Id': library, 'Name': name})

        choices = [x['Name'] for x in libraries]
        choices.insert(0, _(33121))
        selection = dialog("multi", _(33120), choices)

        if selection is None:
            return

        if 0 in selection:
            selection = list(range(1, len(libraries) + 1))

        selected_libraries = []

        for x in selection:

            library = libraries[x - 1]
            selected_libraries.append(library['Id'])

        event(modes[mode], {'Id': ','.join([libraries[x - 1]['Id'] for x in selection])})

    def add_library(self, library_id):

        try:
            FullSync(self, library_id)
        except Exception as error:
            LOG.exception(error)

            return False

        Views().get_nodes()

        return True

    @progress(_(33144))
    def remove_library(self, library_id, dialog):
        
        try:
            with Database('emby') as embydb:

                db = emby_db.EmbyDatabase(embydb.cursor)
                library = db.get_view(library_id)
                items = db.get_item_by_media_folder(library_id)
                media = 'music' if library[1] == 'music' else 'video'

                if media == 'music':
                    settings('MusicRescan.bool', False)

                if items:
                    count = 0

                    with self.music_database_lock if media == 'music' else self.database_lock:
                        with Database(media) as kodidb:

                            if library[1] == 'mixed':
                                movies = [x for x in items if x[1] == 'Movie']
                                tvshows = [x for x in items if x[1] == 'Series']

                                obj = MEDIA['Movie'](self.server, embydb, kodidb, self.direct_path)['Remove']

                                for item in movies:
                                    obj(item[0])
                                    dialog.update(int((float(count) / float(len(items))*100)), heading="%s: %s" % (_('addon_name'), library[0]))
                                    count += 1

                                obj = MEDIA['Series'](self.server, embydb, kodidb, self.direct_path)['Remove']

                                for item in tvshows:
                                    obj(item[0])
                                    dialog.update(int((float(count) / float(len(items))*100)), heading="%s: %s" % (_('addon_name'), library[0]))
                                    count += 1
                            else:
                                obj = MEDIA[items[0][1]](self.server, embydb, kodidb, self.direct_path)['Remove']

                                for item in items:
                                    obj(item[0])
                                    dialog.update(int((float(count) / float(len(items))*100)), heading="%s: %s" % (_('addon_name'), library[0]))
                                    count += 1

            sync = get_sync()

            if library_id in sync['Whitelist']:
                sync['Whitelist'].remove(library_id)
            elif 'Mixed:%s' % library_id in sync['Whitelist']:
                sync['Whitelist'].remove('Mixed:%s' % library_id)

            save_sync(sync)
            Views().remove_library(library_id)
        except Exception as error:

            LOG.exception(error)
            dialog.close()

            return False

        Views().get_views()
        Views().get_nodes()

        return True


    def userdata(self, data):

        ''' Add item_id to userdata queue.
        '''
        if not data:
            return

        for item in data:

            if item in list(self.userdata_queue.queue):
                continue

            self.userdata_queue.put(item['ItemId'])

        LOG.info("---[ userdata:%s ]", self.userdata_queue.qsize())

    def updated(self, data):

        ''' Add item_id to updated queue.
        '''
        if not data:
            return

        for item in data:

            if item in list(self.updated_queue.queue):
                continue

            self.updated_queue.put(item)

        LOG.info("---[ updated:%s ]", self.updated_queue.qsize())

    def removed(self, data):

        ''' Add item_id to removed queue.
        '''
        if not data:
            return

        for item in data:

            if item in list(self.removed_queue.queue):
                continue

            self.removed_queue.put(item)

        LOG.info("---[ removed:%s ]", self.removed_queue.qsize())


class UpdatedWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, *args):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.args = args
        threading.Thread.__init__(self)

    def run(self):

        with self.lock:
            with self.database as kodidb:
                with Database('emby') as embydb:

                    while True:

                        try:
                            item = self.queue.get(timeout=3)
                        except Queue.Empty:

                            LOG.info("--<[ q:updated/%s ]", id(self))
                            self.is_done = True

                            break

                        obj = MEDIA[item['Type']](self.args[0], embydb, kodidb, self.args[1])[item['Type']]

                        try:
                            obj(item)
                            self.queue.task_done()
                        except LibraryException as error:
                            if error.status == 'StopCalled':
                                break
                        except Exception as error:
                            LOG.exception(error)

                        if xbmc.Monitor().abortRequested():
                            break

class UserDataWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, *args):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.args = args
        threading.Thread.__init__(self)

    def run(self):

        with self.lock:
            with self.database as kodidb:
                with Database('emby') as embydb:

                    while True:

                        try:
                            item = self.queue.get(timeout=3)
                        except Queue.Empty:

                            LOG.info("--<[ q:userdata/%s ]", id(self))
                            self.is_done = True

                            break

                        obj = MEDIA[item['Type']](self.args[0], embydb, kodidb, self.args[1])['UserData']

                        try:
                            obj(item)
                            self.queue.task_done()
                        except LibraryException as error:
                            if error.status == 'StopCalled':
                                break
                        except Exception as error:
                            LOG.exception(error)

                        if xbmc.Monitor().abortRequested():
                            break

class SortWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, output, *args):

        self.queue = queue
        self.output = output
        self.args = args
        threading.Thread.__init__(self)

    def run(self):

        with Database('emby') as embydb:
            database = emby_db.EmbyDatabase(embydb.cursor)

            while True:

                try:
                    item_id = self.queue.get(timeout=1)
                except Queue.Empty:

                    self.is_done = True
                    LOG.info("--<[ q:sort/%s ]", id(self))

                    return

                try:
                    media = database.get_media_by_id(item_id)
                    self.output[media].put({'Id': item_id, 'Type': media})
                except Exception:
                    items = database.get_media_by_parent_id(item_id)

                    if not items:
                        LOG.info("Could not find media %s in the emby database.", item_id)
                    else:
                        for item in items:
                            self.output[item[1]].put({'Id': item[0], 'Type': item[1]})

                self.queue.task_done()

                if xbmc.Monitor().abortRequested():
                    break

class RemovedWorker(threading.Thread):

    is_done = False

    def __init__(self, queue, lock, database, *args):

        self.queue = queue
        self.lock = lock
        self.database = Database(database)
        self.args = args
        threading.Thread.__init__(self)

    def run(self):

        with self.lock:
            with self.database as kodidb:
                with Database('emby') as embydb:

                    while True:

                        try:
                            item = self.queue.get(timeout=3)
                        except Queue.Empty:

                            LOG.info("--<[ q:removed/%s ]", id(self))
                            self.is_done = True

                            break

                        obj = MEDIA[item['Type']](self.args[0], embydb, kodidb, self.args[1])['Remove']

                        try:
                            obj(item['Id'])
                            self.queue.task_done()
                        except LibraryException as error:
                            if error.status == 'StopCalled':
                                break
                        except Exception as error:
                            LOG.exception(error)

                        if xbmc.Monitor().abortRequested():
                            break

class NotifyWorker(threading.Thread):

    is_done = False

    def __init__(self, queue):
        self.queue = queue

    def run(self):

        while True:

            try:
                item = self.queue.get(timeout=3)
            except Queue.Empty:

                LOG.info("--<[ q:notify/%s ]", id(self))
                self.is_done = True

                break

            self.queue.task_done()

            if xbmc.Monitor().abortRequested():
                break

        if not self.pdialog and self.content_msg and self.new_time and (not xbmc.Player().isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)')):
            dialog("notification", heading="{emby}", message="%s %s" % (lang(33049), name),
                   icon="{emby}", time=self.new_time, sound=False)
