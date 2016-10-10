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
import kodidb_functions as kodidb
import read_embyserver as embyserver
import userclient
import videonodes
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
    refresh_views = False


    def __init__(self):

        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()

        self.clientInfo = clientinfo.ClientInfo()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.user = userclient.UserClient()
        self.emby = embyserver.Read_EmbyServer()
        self.vnodes = videonodes.VideoNodes()

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
        
            ga.sendEventData("SyncAction", "FastSync")
        
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
                        completed = self.fastSync()
                        break

            if not completed:
                # Fast sync failed or server plugin is not found
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

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        # Create the tables for the emby database
        # emby, view, version
        embycursor.execute(
            """CREATE TABLE IF NOT EXISTS emby(
            emby_id TEXT UNIQUE, media_folder TEXT, emby_type TEXT, media_type TEXT, kodi_id INTEGER,
            kodi_fileid INTEGER, kodi_pathid INTEGER, parent_id INTEGER, checksum INTEGER)""")
        embycursor.execute(
            """CREATE TABLE IF NOT EXISTS view(
            view_id TEXT UNIQUE, view_name TEXT, media_type TEXT, kodi_tagid INTEGER)""")
        embycursor.execute("CREATE TABLE IF NOT EXISTS version(idVersion TEXT)")
        embyconn.commit()

        # content sync: movies, tvshows, musicvideos, music
        kodiconn = utils.kodiSQL('video')
        kodicursor = kodiconn.cursor()

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
        self.maintainViews(embycursor, kodicursor)
        embyconn.commit()

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
            completed = process[itemtype](embycursor, kodicursor, pDialog)
            if not completed:
                xbmc.executebuiltin('InhibitIdleShutdown(false)')
                utils.setScreensaver(value=screensaver)
                window('emby_dbScan', clear=True)
                if pDialog:
                    pDialog.close()

                embycursor.close()
                kodicursor.close()
                return False
            else:
                self.dbCommit(kodiconn)
                embyconn.commit()
                elapsedTime = datetime.now() - startTime
                log.info("SyncDatabase (finished %s in: %s)"
                    % (itemtype, str(elapsedTime).split('.')[0]))
        else:
            # Close the Kodi cursor
            kodicursor.close()

        # sync music
        if music_enabled:

            if repair and 'music' not in repair_list:
                pass
            else:
                musicconn = utils.kodiSQL('music')
                musiccursor = musicconn.cursor()

                startTime = datetime.now()
                completed = self.music(embycursor, musiccursor, pDialog)
                if not completed:
                    xbmc.executebuiltin('InhibitIdleShutdown(false)')
                    utils.setScreensaver(value=screensaver)
                    window('emby_dbScan', clear=True)
                    if pDialog:
                        pDialog.close()

                    embycursor.close()
                    musiccursor.close()
                    return False
                else:
                    musicconn.commit()
                    embyconn.commit()
                    elapsedTime = datetime.now() - startTime
                    log.info("SyncDatabase (finished music in: %s)"
                        % (str(elapsedTime).split('.')[0]))
                musiccursor.close()

        if pDialog:
            pDialog.close()

        emby_db = embydb.Embydb_Functions(embycursor)
        current_version = emby_db.get_version(self.clientInfo.get_version())
        window('emby_version', current_version)
        embyconn.commit()
        embycursor.close()

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

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        kodiconn = utils.kodiSQL('video')
        kodicursor = kodiconn.cursor()

        # Compare views, assign correct tags to items
        self.maintainViews(embycursor, kodicursor)

        self.dbCommit(kodiconn)
        kodicursor.close()

        embyconn.commit()
        embycursor.close()

    def maintainViews(self, embycursor, kodicursor):

        # Compare the views to emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        kodi_db = kodidb.Kodidb_Functions(kodicursor)

        # Get views
        result = self.doUtils("{server}/emby/Users/{UserId}/Views?format=json")
        grouped_views = result['Items']
        ordered_views = self.emby.getViews(sortedlist=True)
        all_views = []
        sorted_views = []
        for view in ordered_views:
            all_views.append(view['name'])
            if view['type'] == "music":
                continue

            if view['type'] == "mixed":
                sorted_views.append(view['name'])
            sorted_views.append(view['name'])
        log.info("Sorted views: %s" % sorted_views)

        # total nodes for window properties
        self.vnodes.clearProperties()
        totalnodes = len(sorted_views) + 0

        current_views = emby_db.getViews()
        # Set views for supported media type
        emby_mediatypes = {

            'movies': "Movie",
            'tvshows': "Series",
            'musicvideos': "MusicVideo",
            'homevideos': "Video",
            'music': "Audio",
            'photos': "Photo"
        }
        for mediatype in ['movies', 'tvshows', 'musicvideos', 'homevideos', 'music', 'photos']:

            nodes = [] # Prevent duplicate for nodes of the same type
            playlists = [] # Prevent duplicate for playlists of the same type
            # Get media folders from server
            folders = self.emby.getViews(mediatype, root=True)
            for folder in folders:

                folderid = folder['id']
                foldername = folder['name']
                viewtype = folder['type']

                if foldername not in all_views:
                    # Media folders are grouped into userview
                    params = {
                        'ParentId': folderid,
                        'Recursive': True,
                        'Limit': 1,
                        'IncludeItemTypes': emby_mediatypes[mediatype]
                    } # Get one item from server using the folderid
                    url = "{server}/emby/Users/{UserId}/Items?format=json"
                    result = self.doUtils(url, parameters=params)
                    try:
                        verifyitem = result['Items'][0]['Id']
                    except (TypeError, IndexError):
                        # Something is wrong. Keep the same folder name.
                        # Could be the view is empty or the connection
                        pass
                    else:
                        for grouped_view in grouped_views:
                            # This is only reserved for the detection of grouped views
                            if (grouped_view['Type'] == "UserView" and
                                grouped_view.get('CollectionType') == mediatype):
                                # Take the userview, and validate the item belong to the view
                                if self.emby.verifyView(grouped_view['Id'], verifyitem):
                                    # Take the name of the userview
                                    log.info("Found corresponding view: %s %s"
                                        % (grouped_view['Name'], grouped_view['Id']))
                                    foldername = grouped_view['Name']
                                    break
                        else:
                            # Unable to find a match, add the name to our sorted_view list
                            sorted_views.append(foldername)
                            log.info("Couldn't find corresponding grouped view: %s" % sorted_views)

                # Failsafe
                try:
                    sorted_views.index(foldername)
                except ValueError:
                    sorted_views.append(foldername)

                # Get current media folders from emby database
                view = emby_db.getView_byId(folderid)
                try:
                    current_viewname = view[0]
                    current_viewtype = view[1]
                    current_tagid = view[2]

                except TypeError:
                    log.info("Creating viewid: %s in Emby database." % folderid)
                    tagid = kodi_db.createTag(foldername)
                    # Create playlist for the video library
                    if (foldername not in playlists and
                            mediatype in ('movies', 'tvshows', 'musicvideos')):
                        utils.playlistXSP(mediatype, foldername, folderid, viewtype)
                        playlists.append(foldername)
                    # Create the video node
                    if foldername not in nodes and mediatype not in ("musicvideos", "music"):
                        self.vnodes.viewNode(sorted_views.index(foldername), foldername, mediatype,
                            viewtype, folderid)
                        if viewtype == "mixed": # Change the value
                            sorted_views[sorted_views.index(foldername)] = "%ss" % foldername
                        nodes.append(foldername)
                        totalnodes += 1
                    # Add view to emby database
                    emby_db.addView(folderid, foldername, viewtype, tagid)

                else:
                    log.debug(' '.join((

                        "Found viewid: %s" % folderid,
                        "viewname: %s" % current_viewname,
                        "viewtype: %s" % current_viewtype,
                        "tagid: %s" % current_tagid)))

                    # View is still valid
                    try:
                        current_views.remove(folderid)
                    except ValueError:
                        # View was just created, nothing to remove
                        pass

                    # View was modified, update with latest info
                    if current_viewname != foldername:
                        log.info("viewid: %s new viewname: %s" % (folderid, foldername))
                        tagid = kodi_db.createTag(foldername)

                        # Update view with new info
                        emby_db.updateView(foldername, tagid, folderid)

                        if mediatype != "music":
                            if emby_db.getView_byName(current_viewname) is None:
                                # The tag could be a combined view. Ensure there's no other tags
                                # with the same name before deleting playlist.
                                utils.playlistXSP(
                                    mediatype, current_viewname, folderid, current_viewtype, True)
                                # Delete video node
                                if mediatype != "musicvideos":
                                    self.vnodes.viewNode(
                                        indexnumber=None,
                                        tagname=current_viewname,
                                        mediatype=mediatype,
                                        viewtype=current_viewtype,
                                        viewid=folderid,
                                        delete=True)
                            # Added new playlist
                            if (foldername not in playlists and
                                    mediatype in ('movies', 'tvshows', 'musicvideos')):
                                utils.playlistXSP(mediatype, foldername, folderid, viewtype)
                                playlists.append(foldername)
                            # Add new video node
                            if foldername not in nodes and mediatype != "musicvideos":
                                self.vnodes.viewNode(sorted_views.index(foldername), foldername,
                                    mediatype, viewtype, folderid)
                                if viewtype == "mixed": # Change the value
                                    sorted_views[sorted_views.index(foldername)] = "%ss" % foldername
                                nodes.append(foldername)
                                totalnodes += 1

                        # Update items with new tag
                        items = emby_db.getItem_byView(folderid)
                        for item in items:
                            # Remove the "s" from viewtype for tags
                            kodi_db.updateTag(
                                current_tagid, tagid, item[0], current_viewtype[:-1])
                    else:
                        # Validate the playlist exists or recreate it
                        if mediatype != "music":
                            if (foldername not in playlists and
                                    mediatype in ('movies', 'tvshows', 'musicvideos')):
                                utils.playlistXSP(mediatype, foldername, folderid, viewtype)
                                playlists.append(foldername)
                            # Create the video node if not already exists
                            if foldername not in nodes and mediatype != "musicvideos":
                                self.vnodes.viewNode(sorted_views.index(foldername), foldername,
                                    mediatype, viewtype, folderid)
                                if viewtype == "mixed": # Change the value
                                    sorted_views[sorted_views.index(foldername)] = "%ss" % foldername
                                nodes.append(foldername)
                                totalnodes += 1
        else:
            # Add video nodes listings
            self.vnodes.singleNode(totalnodes, "Favorite movies", "movies", "favourites")
            totalnodes += 1
            self.vnodes.singleNode(totalnodes, "Favorite tvshows", "tvshows", "favourites")
            totalnodes += 1
            self.vnodes.singleNode(totalnodes, "Favorite episodes", "episodes", "favourites")
            totalnodes += 1
            self.vnodes.singleNode(totalnodes, "channels", "movies", "channels")
            totalnodes += 1
            # Save total
            window('Emby.nodes.total', str(totalnodes))

            # Remove any old referenced views
            log.info("Removing views: %s" % current_views)
            for view in current_views:
                emby_db.removeView(view)

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
        total = boxsets['TotalRecordCount']

        movies.process_all("BoxSet", "added", boxsets['Items'], total)
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

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        kodiconn = utils.kodiSQL('video')
        kodicursor = kodiconn.cursor()
        emby_db = embydb.Embydb_Functions(embycursor)
        pDialog = None
        update_embydb = False

        if self.refresh_views:
            # Received userconfig update
            self.refresh_views = False
            self.maintainViews(embycursor, kodicursor)
            self.forceLibraryUpdate = True
            update_embydb = True

        incSyncIndicator = int(settings('incSyncIndicator'))
        totalUpdates = len(self.addedItems) + len(self.updateItems) + len(self.userdataItems) + len(self.removeItems)
        
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

                items_process = itemtypes.Items(embycursor, kodicursor)
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

        if update_embydb:
            update_embydb = False
            log.info("Updating emby database.")
            embyconn.commit()
            self.saveLastSync()

        if self.forceLibraryUpdate:
            # Force update the Kodi library
            self.forceLibraryUpdate = False
            self.dbCommit(kodiconn)

            log.info("Updating video library.")
            window('emby_kodiScan', value="true")
            xbmc.executebuiltin('UpdateLibrary(video)')

        if pDialog:
            pDialog.close()

        kodicursor.close()
        embycursor.close()


    def compareDBVersion(self, current, minimum):
        # It returns True is database is up to date. False otherwise.
        log.info("current: %s minimum: %s" % (current, minimum))

        currMajor, currMinor, currPatch = current.split(".")
        minMajor, minMinor, minPatch = minimum.split(".")

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

        while not self.monitor.abortRequested():

            # In the event the server goes offline
            while self.suspend_thread:
                # Set in service.py
                if self.monitor.waitForAbort(5):
                    # Abort was requested while waiting. We should exit
                    break

            if (window('emby_dbCheck') != "true" and settings('SyncInstallRunDone') == "true"):
                # Verify the validity of the database

                embyconn = utils.kodiSQL('emby')
                embycursor = embyconn.cursor()
                emby_db = embydb.Embydb_Functions(embycursor)
                currentVersion = emby_db.get_version()
                ###$ Begin migration $###
                if currentVersion is None:
                    currentVersion = emby_db.get_version(settings('dbCreatedWithVersion'))
                    embyconn.commit()
                    log.info("Migration of database version completed")
                ###$ End migration $###
                embycursor.close()
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
                        utils.reset()

                    break

                window('emby_dbCheck', value="true")


            if not startupComplete:
                # Verify the video database can be found
                videoDb = utils.getKodiVideoDBPath()
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
            if window('emby_dbScan') != "true":
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
