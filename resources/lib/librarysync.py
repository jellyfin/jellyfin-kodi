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
import downloadutils
import itemtypes
import embydb_functions as embydb
import read_embyserver as embyserver
import userclient
import views
from objects import Movies, MusicVideos, TVShows, Music
from utils import window, settings, language as lang, should_stop
from ga_client import GoogleAnalytics
from database import DatabaseConn, db_reset
from contextlib import closing

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

    def startSync(self):

        ga = GoogleAnalytics()
    
        # Run at start up - optional to use the server plugin
        if settings('SyncInstallRunDone') == "true":
            # Validate views
            self.refreshViews()
            completed = False
            # Verify if server plugin is installed.
            if settings('serverSync') == "true":
                # Try to use fast start up
                url = "{server}/emby/Plugins?format=json"
                result = self.doUtils(url)

                for plugin in result:
                    if plugin['Name'] == "Emby.Kodi Sync Queue":
                        log.debug("Found server plugin.")
                        self.isFastSync = True
                        ga.sendEventData("SyncAction", "FastSync")
                        completed = self.fastSync()
                        break

            if not completed:
                # Fast sync failed or server plugin is not found
                ga.sendEventData("SyncAction", "Sync")
                completed = ManualSync().sync()
        else:
            # Install sync is not completed
            ga.sendEventData("SyncAction", "FullSync")
            completed = self.fullSync()

        return completed

    def fastSync(self):

        lastSync = settings('LastIncrementalSync')
        if not lastSync:
            lastSync = "2010-01-01T00:00:00Z"

        lastSyncTime = utils.convertDate(lastSync)
        log.info("Last sync run: %s" % lastSyncTime)

        # get server RetentionDateTime
        result = self.doUtils("{server}/emby/Emby.Kodi.SyncQueue/GetServerDateTime?format=json")
        try:
            retention_time = result['RetentionDateTime']
        except (TypeError, KeyError):
            retention_time = "2010-01-01T00:00:00Z"

        retention_time = utils.convertDate(retention_time)
        log.info("RetentionDateTime: %s" % retention_time)

        # if last sync before retention time do a full sync
        if retention_time > lastSyncTime:
            log.info("Fast sync server retention insufficient, fall back to full sync")
            return False

        params = {'LastUpdateDT': lastSync}
        if settings('enableMusic') != "true":
            params['filter'] = "music"
        url = "{server}/emby/Emby.Kodi.SyncQueue/{UserId}/GetItems?format=json"
        result = self.doUtils(url, parameters=params)

        try:
            processlist = {

                'added': result['ItemsAdded'],
                'update': result['ItemsUpdated'],
                'userdata': result['UserDataChanged'],
                'remove': result['ItemsRemoved']
            }

        except (KeyError, TypeError):
            log.error("Failed to retrieve latest updates using fast sync.")
            return False

        else:
            log.info("Fast sync changes: %s" % result)
            for action in processlist:
                self.triage_items(action, processlist[action])

            return True

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

    def dbCommit(self, connection):
        # Central commit, verifies if Kodi database update is running
        kodidb_scan = window('emby_kodiScan') == "true"
        count = 0

        while kodidb_scan:

            log.info("Kodi scan is running. Waiting...")
            kodidb_scan = window('emby_kodiScan') == "true"

            if count == 10:
                log.info("Flag still active, but will try to commit")
                window('emby_kodiScan', clear=True)

            if should_stop():
                log.info("Commit unsuccessful. Sync terminated.")
                break

            if self.monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                log.info("Commit unsuccessful.")
                break

            count += 1
        
        try:
            connection.commit()
            log.info("Commit successful.")
        except sqlite3.OperationalError as error:
            log.error(error)
            if "database is locked" in error:
                log.info("retrying...")
                window('emby_kodiScan', value="true")
                self.dbCommit(connection)

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
        with DatabaseConn('emby') as conn_emby, DatabaseConn('video') as conn_video:
            with closing(conn_emby.cursor()) as cursor_emby, closing(conn_video.cursor()) as cursor_video:        
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
                conn_emby.commit()
                #self.maintainViews(cursor_emby, cursor_video)

                # Sync video library
                process = {

                    'movies': self.movies,
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
                with DatabaseConn('emby') as conn_emby, DatabaseConn('music') as conn_music:
                    with closing(conn_emby.cursor()) as cursor_emby, closing(conn_music.cursor()) as cursor_music:
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

        with DatabaseConn('emby') as conn_emby:
            with closing(conn_emby.cursor()) as cursor_emby:
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
        
        with DatabaseConn('emby') as conn_emby, DatabaseConn() as conn_video:
            with closing(conn_emby.cursor()) as cursor_emby, closing(conn_video.cursor()) as cursor_video:
                # Compare views, assign correct tags to items
                views.Views(cursor_emby, cursor_video).maintain()

    def movies(self, embycursor, kodicursor, pdialog):

        # Get movies from emby
        emby_db = embydb.Embydb_Functions(embycursor)
        movies = Movies(embycursor, kodicursor, pdialog)

        views = emby_db.getView_byType('movies')
        views += emby_db.getView_byType('mixed')
        log.info("Media folders: %s" % views)

        ##### PROCESS MOVIES #####
        for view in views:

            log.info("Processing: %s", view)
            view_name = view['name']

            # Get items per view
            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33017), view_name))

            all_movies = self.emby.getMovies(view['id'], dialog=pdialog)
            movies.add_all("Movie", all_movies, view)

        log.debug("Movies finished.")

        ##### PROCESS BOXSETS #####
        if pdialog:
            pdialog.update(heading=lang(29999), message=lang(33018))

        boxsets = self.emby.getBoxset(dialog=pdialog)
        movies.add_all("BoxSet", boxsets)
        log.debug("Boxsets finished.")

        return True

    def musicvideos(self, embycursor, kodicursor, pdialog):

        # Get musicvideos from emby
        emby_db = embydb.Embydb_Functions(embycursor)
        mvideos = MusicVideos(embycursor, kodicursor, pdialog)

        views = emby_db.getView_byType('musicvideos')
        log.info("Media folders: %s" % views)

        for view in views:
            log.info("Processing: %s", view)

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33019), viewName))

            # Initial or repair sync
            all_mvideos = self.emby.getMusicVideos(viewId, dialog=pdialog)
            mvideos.add_all("MusicVideo", all_mvideos, view)

        else:
            log.debug("MusicVideos finished.")

        return True

    def tvshows(self, embycursor, kodicursor, pdialog):

        # Get shows from emby
        emby_db = embydb.Embydb_Functions(embycursor)
        tvshows = TVShows(embycursor, kodicursor, pdialog)

        views = emby_db.getView_byType('tvshows')
        views += emby_db.getView_byType('mixed')
        log.info("Media folders: %s" % views)

        for view in views:

            # Get items per view
            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33020), view['name']))

            all_tvshows = self.emby.getShows(view['id'], dialog=pdialog)
            tvshows.add_all("Series", all_tvshows, view)

        else:
            log.debug("TVShows finished.")

        return True

    def music(self, embycursor, kodicursor, pdialog):
        # Get music from emby
        emby_db = embydb.Embydb_Functions(embycursor)
        music = Music(embycursor, kodicursor, pdialog)

        views = emby_db.getView_byType('music')
        log.info("Media folders: %s", views)

        # Add music artists and everything will fall into place
        if pdialog:
            pdialog.update(heading=lang(29999),
                           message="%s Music..." % lang(33021))

        for view in views:
            all_artists = self.emby.getArtists(view['id'], dialog=pdialog)
            music.add_all("MusicArtist", all_artists)

        log.debug("Finished syncing music")

        return True

    # Reserved for websocket_client.py and fast start
    def triage_items(self, process, items):

        processlist = {

            'added': self.addedItems,
            'update': self.updateItems,
            'userdata': self.userdataItems,
            'remove': self.removeItems
        }
        if items:
            if process == "userdata":
                itemids = []
                for item in items:
                    itemids.append(item['ItemId'])
                items = itemids

            log.info("Queue %s: %s" % (process, items))
            processlist[process].extend(items)

    def incrementalSync(self):

        update_embydb = False
        pDialog = None

        # do a view update if needed
        if self.refresh_views:
            self.refreshViews()
            self.refresh_views = False
            self.forceLibraryUpdate = True

        # do a lib update if any items in list
        totalUpdates = len(self.addedItems) + len(self.updateItems) + len(self.userdataItems) + len(self.removeItems)
        if totalUpdates > 0:
            with DatabaseConn('emby') as conn_emby, DatabaseConn('video') as conn_video:
                with closing(conn_emby.cursor()) as cursor_emby, closing(conn_video.cursor()) as cursor_video:

                    emby_db = embydb.Embydb_Functions(cursor_emby)

                    incSyncIndicator = int(settings('incSyncIndicator') or 10)
                    if incSyncIndicator != -1 and totalUpdates > incSyncIndicator:
                        # Only present dialog if we are going to process items
                        pDialog = self.progressDialog('Incremental sync')
                        log.info("incSyncIndicator=" + str(incSyncIndicator) + " totalUpdates=" + str(totalUpdates))

                    process = {

                        'added': self.addedItems,
                        'update': self.updateItems,
                        'userdata': self.userdataItems,
                        'remove': self.removeItems
                    }
                    for process_type in ['added', 'update', 'userdata', 'remove']:

                        if process[process_type] and window('emby_kodiScan') != "true":

                            listItems = list(process[process_type])
                            del process[process_type][:] # Reset class list

                            items_process = itemtypes.Items(cursor_emby, cursor_video)
                            update = False

                            # Prepare items according to process process_type
                            if process_type == "added":
                                items = self.emby.sortby_mediatype(listItems)

                            elif process_type in ("userdata", "remove"):
                                items = emby_db.sortby_mediaType(listItems, unsorted=False)

                            else:
                                items = emby_db.sortby_mediaType(listItems)
                                if items.get('Unsorted'):
                                    sorted_items = self.emby.sortby_mediatype(items['Unsorted'])
                                    doupdate = items_process.itemsbyId(sorted_items, "added", pDialog)
                                    if doupdate:
                                        embyupdate, kodiupdate_video = doupdate
                                        if embyupdate:
                                            update_embydb = True
                                        if kodiupdate_video:
                                            self.forceLibraryUpdate = True
                                    del items['Unsorted']

                            doupdate = items_process.itemsbyId(items, process_type, pDialog)
                            if doupdate:
                                embyupdate, kodiupdate_video = doupdate
                                if embyupdate:
                                    update_embydb = True
                                if kodiupdate_video:
                                    self.forceLibraryUpdate = True

        # if stuff happened then do some stuff
        if update_embydb:
            update_embydb = False
            log.info("Updating emby database.")
            self.saveLastSync()

        if self.forceLibraryUpdate:
            # Force update the Kodi library
            self.forceLibraryUpdate = False

            log.info("Updating video library.")
            window('emby_kodiScan', value="true")
            xbmc.executebuiltin('UpdateLibrary(video)')

        if pDialog:
            pDialog.close()


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

    def _verify_emby_database(self):
        # Create the tables for the emby database
        with DatabaseConn('emby') as conn:
            with closing(conn.cursor()) as cursor:
                # emby, view, version
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS emby(
                    emby_id TEXT UNIQUE, media_folder TEXT, emby_type TEXT, media_type TEXT,
                    kodi_id INTEGER, kodi_fileid INTEGER, kodi_pathid INTEGER, parent_id INTEGER,
                    checksum INTEGER)""")
                cursor.execute(
                    """CREATE TABLE IF NOT EXISTS view(
                    view_id TEXT UNIQUE, view_name TEXT, media_type TEXT, kodi_tagid INTEGER)""")
                cursor.execute("CREATE TABLE IF NOT EXISTS version(idVersion TEXT)")

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

        # Verify database structure, otherwise create it.
        self._verify_emby_database()

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
                with DatabaseConn('emby') as conn:
                    with closing(conn.cursor()) as cursor:                

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
                        db_reset()

                    break

                window('emby_dbCheck', value="true")


            if not startupComplete:
                # Verify the video database can be found
                videoDb = DatabaseConn()._SQL('video')
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
            if window('emby_dbScan') != "true" and window('emby_shouldStop') != "true":
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

    def sync(self):
        return self.fullSync(manualrun=True)

    def movies(self, embycursor, kodicursor, pdialog):
        return Movies(embycursor, kodicursor, pdialog).compare_all()

    def musicvideos(self, embycursor, kodicursor, pdialog):
        return MusicVideos(embycursor, kodicursor, pdialog).compare_all()

    def tvshows(self, embycursor, kodicursor, pdialog):
        return TVShows(embycursor, kodicursor, pdialog).compare_all()

    def music(self, embycursor, kodicursor, pdialog):
        return Music(embycursor, kodicursor).compare_all()
