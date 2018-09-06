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





"""
# -*- coding: utf-8 -*-

##################################################################################################

import logging
import sqlite3
import threading
from datetime import datetime, timedelta, time

import xbmc
import xbmcgui
import xbmcvfs

import api
import utils
import clientinfo
import database
import downloadutils
import itemtypes
import emby_api as mb
import embydb_functions as embydb
import read_embyserver as embyserver
import userclient
import views
from objects import Movies, MusicVideos, TVShows, Music
from utils import window, settings, language as lang, should_stop
from ga_client import GoogleAnalytics

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################

class LibrarySync(threading.Thread):

    _shared_state = {}

    isFastSync = False

    stop_thread = False
    suspend_thread = False

    # Track websocketclient updates
    addedItems = []
    updateItems = []
    userdataItems = []
    removeItems = []
    forceLibraryUpdate = False
    incremental_count = 0
    refresh_views = False


    def __init__(self):

        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()

        self.clientInfo = clientinfo.ClientInfo()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.user = userclient.UserClient()
        self.emby = embyserver.Read_EmbyServer()
        self.kodi_version = int(xbmc.getInfoLabel('System.BuildVersion')[:2])

        threading.Thread.__init__(self)


    def progressDialog(self, title):

        dialog = None

        dialog = xbmcgui.DialogProgressBG()
        dialog.create("Emby for Kodi", title)
        log.debug("Show progress dialog: %s" % title)

        return dialog

    def saveLastSync(self):

        # Save last sync time
        overlap = 2

        try: # datetime fails when used more than once, TypeError
            if self.isFastSync:
                result = self.doUtils("{server}/emby/Emby.Kodi.SyncQueue/GetServerDateTime?format=json")
                server_time = result['ServerDateTime']
                server_time = utils.convertDate(server_time)
            else:
                raise Exception("Fast sync server plugin is not enabled.")

        except Exception as e:
            # If the server plugin is not installed or an error happened.
            log.debug("An exception occurred: %s" % e)
            time_now = datetime.utcnow()-timedelta(minutes=overlap)
            lastSync = time_now.strftime('%Y-%m-%dT%H:%M:%SZ')
            log.info("New sync time: client time -%s min: %s" % (overlap, lastSync))

        else:
            lastSync = (server_time - timedelta(minutes=overlap)).strftime('%Y-%m-%dT%H:%M:%SZ')
            log.info("New sync time: server time -%s min: %s" % (overlap, lastSync))

        finally:
            settings('LastIncrementalSync', value=lastSync)


    def fullSync(self, manualrun=False, repair=False):
        # Only run once when first setting up. Can be run manually.
        music_enabled = settings('enableMusic') == "true"

        xbmc.executebuiltin('InhibitIdleShutdown(true)')
        screensaver = utils.getScreensaver()
        utils.setScreensaver(value="")
        window('emby_dbScan', value="true")
        # Add sources
        utils.sourcesXML()

        # use emby and video DBs
        with database.DatabaseConn('emby') as cursor_emby:
            with database.DatabaseConn('video') as cursor_video:
                # content sync: movies, tvshows, musicvideos, music

                if manualrun:
                    message = "Manual sync"
                elif repair:
                    message = "Repair sync"
                    repair_list = []
                    choices = ['all', 'movies', 'musicvideos', 'tvshows']
                    if music_enabled:
                        choices.append('music')

                    if self.kodi_version > 15:
                        # Jarvis or higher
                        types = xbmcgui.Dialog().multiselect(lang(33094), choices)
                        if types is None:
                            pass
                        elif 0 in types: # all
                            choices.pop(0)
                            repair_list.extend(choices)
                        else:
                            for index in types:
                                repair_list.append(choices[index])
                    else:
                        resp = xbmcgui.Dialog().select(lang(33094), choices)
                        if resp == 0: # all
                            choices.pop(resp)
                            repair_list.extend(choices)
                        else:
                            repair_list.append(choices[resp])

                    log.info("Repair queued for: %s", repair_list)
                else:
                    message = "Initial sync"
                    window('emby_initialScan', value="true")

                pDialog = self.progressDialog("%s" % message)
                starttotal = datetime.now()

                # Set views
                views.Views(cursor_emby, cursor_video).maintain()
                cursor_emby.connection.commit()
                #self.maintainViews(cursor_emby, cursor_video)

                # Sync video library
                process = {

                    'movies': self.movies,
                    'boxsets': self.boxsets,
                    'musicvideos': self.musicvideos,
                    'tvshows': self.tvshows
                }
                for itemtype in process:

                    if repair and itemtype not in repair_list:
                        continue

                    startTime = datetime.now()
                    completed = process[itemtype](cursor_emby, cursor_video, pDialog)
                    if not completed:
                        xbmc.executebuiltin('InhibitIdleShutdown(false)')
                        utils.setScreensaver(value=screensaver)
                        window('emby_dbScan', clear=True)
                        if pDialog:
                            pDialog.close()

                        return False
                    else:
                        elapsedTime = datetime.now() - startTime
                        log.info("SyncDatabase (finished %s in: %s)"
                            % (itemtype, str(elapsedTime).split('.')[0]))

                         
        # sync music
        # use emby and music
        if music_enabled:                   
            if repair and 'music' not in repair_list:
                pass
            else:
                with database.DatabaseConn('emby') as cursor_emby:
                    with database.DatabaseConn('music') as cursor_music:
                        startTime = datetime.now()
                        completed = self.music(cursor_emby, cursor_music, pDialog)
                        if not completed:
                            xbmc.executebuiltin('InhibitIdleShutdown(false)')
                            utils.setScreensaver(value=screensaver)
                            window('emby_dbScan', clear=True)
                            if pDialog:
                                pDialog.close()

                            return False
                        else:
                            elapsedTime = datetime.now() - startTime
                            log.info("SyncDatabase (finished music in: %s)"
                                % (str(elapsedTime).split('.')[0]))

        if pDialog:
            pDialog.close()

        with database.DatabaseConn('emby') as cursor_emby:
            emby_db = embydb.Embydb_Functions(cursor_emby)
            current_version = emby_db.get_version(self.clientInfo.get_version())
                
        window('emby_version', current_version)

        settings('SyncInstallRunDone', value="true")

        self.saveLastSync()
        xbmc.executebuiltin('UpdateLibrary(video)')
        elapsedtotal = datetime.now() - starttotal

        xbmc.executebuiltin('InhibitIdleShutdown(false)')
        utils.setScreensaver(value=screensaver)
        window('emby_dbScan', clear=True)
        window('emby_initialScan', clear=True)

        xbmcgui.Dialog().notification(
                    heading=lang(29999),
                    message="%s %s %s" %
                            (message, lang(33025), str(elapsedtotal).split('.')[0]),
                    icon="special://home/addons/plugin.video.emby/icon.png",
                    sound=False)
                    
        return True


    def refreshViews(self):
        
        with database.DatabaseConn('emby') as cursor_emby:
            with database.DatabaseConn() as cursor_video:
                # Compare views, assign correct tags to items
                views.Views(cursor_emby, cursor_video).maintain()

    def offline_mode_views(self):

        with database.DatabaseConn('emby') as cursor_emby:
            with database.DatabaseConn() as cursor_video:
                views.Views(cursor_emby, cursor_video).offline_mode()


    def compareDBVersion(self, current, minimum):
        # It returns True is database is up to date. False otherwise.
        log.info("current: %s minimum: %s" % (current, minimum))

        try:
            currMajor, currMinor, currPatch = current.split(".")
            minMajor, minMinor, minPatch = minimum.split(".")
        except ValueError as error:
            raise ValueError("Unable to compare versions: %s, %s" % (current, minimum))

        if currMajor > minMajor:
            return True
        elif currMajor == minMajor and (currMinor > minMinor or
                                       (currMinor == minMinor and currPatch >= minPatch)):
            return True
        else:
            # Database out of date.
            return False

    def run(self):

        try:
            self.run_internal()
        except Warning as e:
            if "restricted" in e:
                pass
            elif "401" in e:
                pass
        except Exception as e:
            ga = GoogleAnalytics()
            errStrings = ga.formatException()
            if not (hasattr(e, 'quiet') and e.quiet):
                ga.sendEventData("Exception", errStrings[0], errStrings[1])
            window('emby_dbScan', clear=True)
            log.exception(e)
            xbmcgui.Dialog().ok(
                        heading=lang(29999),
                        line1=(
                            "Library sync thread has exited! "
                            "You should restart Kodi now. "
                            "Please report this on the forum."),
                        line2=(errStrings[0] + " (" + errStrings[1] + ")"))

    def run_internal(self):

        dialog = xbmcgui.Dialog()

        startupComplete = False

        log.warn("---===### Starting LibrarySync ###===---")
        if utils.verify_advancedsettings():
            # Advancedsettings was modified, Kodi needs to restart
            log.warn("###===--- LibrarySync Aborted ---===###")
            return

        while not self.monitor.abortRequested():

            # In the event the server goes offline
            while self.suspend_thread:
                # Set in service.py
                if self.monitor.waitForAbort(5):
                    # Abort was requested while waiting. We should exit
                    break

            if (window('emby_dbCheck') != "true" and settings('SyncInstallRunDone') == "true"):
                # Verify the validity of the database
                log.info("Doing DB Version Check")
                with database.DatabaseConn('emby') as cursor:
                    emby_db = embydb.Embydb_Functions(cursor)
                    currentVersion = emby_db.get_version()
                    ###$ Begin migration $###
                    if not currentVersion:
                        currentVersion = emby_db.get_version(settings('dbCreatedWithVersion') or self.clientInfo.get_version())
                        log.info("Migration of database version completed")
                    ###$ End migration $###

                window('emby_version', value=currentVersion)

                minVersion = window('emby_minDBVersion')
                uptoDate = self.compareDBVersion(currentVersion, minVersion)

                if not uptoDate:
                    log.warn("Database version out of date: %s minimum version required: %s"
                        % (currentVersion, minVersion))

                    resp = dialog.yesno(lang(29999), lang(33022))
                    if not resp:
                        log.warn("Database version is out of date! USER IGNORED!")
                        dialog.ok(lang(29999), lang(33023))
                    else:
                        database.db_reset()

                    break

                window('emby_dbCheck', value="true")


            if not startupComplete:
                # Verify the video database can be found
                videoDb = database.video_database()
                if not xbmcvfs.exists(videoDb):
                    # Database does not exists
                    log.error(
                        "The current Kodi version is incompatible "
                        "with the Emby for Kodi add-on. Please visit "
                        "https://github.com/MediaBrowser/Emby.Kodi/wiki "
                        "to know which Kodi versions are supported.")

                    dialog.ok(
                            heading=lang(29999),
                            line1=lang(33024))
                    break                

                # Run start up sync
                log.warn("Database version: %s", window('emby_version'))
                log.info("SyncDatabase (started)")
                startTime = datetime.now()
                librarySync = self.startSync()
                elapsedTime = datetime.now() - startTime
                log.info("SyncDatabase (finished in: %s) %s"
                    % (str(elapsedTime).split('.')[0], librarySync))

                # Add other servers at this point
                # TODO: re-add once plugin listing is created
                # self.user.load_connect_servers()
                
                # Only try the initial sync once per kodi session regardless
                # This will prevent an infinite loop in case something goes wrong.
                startupComplete = True

            # Process updates
            if self.incremental_count > 5:
                self.incremental_count = 0
                window('emby_kodiScan', clear=True)

            if ((not xbmc.Player().isPlayingVideo() or xbmc.getCondVisibility('VideoPlayer.Content(livetv)')) and
                window('emby_dbScan') != "true" and window('emby_shouldStop') != "true"):
                
                self.incrementalSync()

            if window('emby_onWake') == "true" and window('emby_online') == "true":
                # Kodi is waking up
                # Set in kodimonitor.py
                window('emby_onWake', clear=True)
                if window('emby_syncRunning') != "true":
                    log.info("SyncDatabase onWake (started)")
                    librarySync = self.startSync()
                    log.info("SyncDatabase onWake (finished) %s" % librarySync)

            if self.stop_thread:
                # Set in service.py
                log.debug("Service terminated thread.")
                break

            if self.monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        log.warn("###===--- LibrarySync Stopped ---===###")

    def stopThread(self):
        self.stop_thread = True
        log.debug("Ending thread...")

    def suspendThread(self):
        self.suspend_thread = True
        log.debug("Pausing thread...")

    def resumeThread(self):
        self.suspend_thread = False
        log.debug("Resuming thread...")

class ManualSync(LibrarySync):


    def __init__(self):
        LibrarySync.__init__(self)

    def sync(self, mediatype=None):

        if mediatype in ('movies', 'boxsets', 'musicvideos', 'tvshows'):
            with database.DatabaseConn('emby') as cursor_emby:
                with database.DatabaseConn('video') as cursor_video:
                    pDialog = self.progressDialog("Manual Sync: %s" % mediatype)
                    if mediatype == 'movies':
                        self.movies(cursor_emby, cursor_video, pDialog)
                    elif mediatype == "boxsets":
                        self.boxsets(cursor_emby, cursor_video, pDialog)
                    elif mediatype =='musicvideos':
                        self.musicvideos(cursor_emby, cursor_video, pDialog)
                    elif mediatype == 'tvshows':
                        self.tvshows(cursor_emby, cursor_video, pDialog)

                    pDialog.close()
                    return

        elif mediatype == 'music':
            with database.DatabaseConn('emby') as cursor_emby:
                with database.DatabaseConn('music') as cursor_music:
                    pDialog = self.progressDialog("Manual Sync: %s" % mediatype)
                    self.music(cursor_emby, cursor_music, pDialog)
                    pDialog.close()
                    return
        else:
            return self.fullSync(manualrun=True)

    def movies(self, embycursor, kodicursor, pdialog):
        return Movies(embycursor, kodicursor, pdialog).compare_all()

    def boxsets(self, embycursor, kodicursor, pdialog):
        return Movies(embycursor, kodicursor, pdialog).force_refresh_boxsets()

    def musicvideos(self, embycursor, kodicursor, pdialog):
        return MusicVideos(embycursor, kodicursor, pdialog).compare_all()

    def tvshows(self, embycursor, kodicursor, pdialog):
        return TVShows(embycursor, kodicursor, pdialog).compare_all()

    def music(self, embycursor, kodicursor, pdialog):
        return Music(embycursor, kodicursor).compare_all()
"""
