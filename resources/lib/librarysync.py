# -*- coding: utf-8 -*-

##################################################################################################

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

##################################################################################################


class LibrarySync(threading.Thread):

    _shared_state = {}

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
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.user = userclient.UserClient()
        self.emby = embyserver.Read_EmbyServer()
        self.vnodes = videonodes.VideoNodes()

        threading.Thread.__init__(self)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def progressDialog(self, title, forced=False):

        dialog = None

        if utils.settings('dbSyncIndicator') == "true" or forced:
            dialog = xbmcgui.DialogProgressBG()
            dialog.create("Emby for Kodi", title)
            self.logMsg("Show progress dialog: %s" % title, 2)

        return dialog

    def startSync(self):

        settings = utils.settings
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
                        self.logMsg("Found server plugin.", 2)
                        completed = self.fastSync()
                        break

            if not completed:
                # Fast sync failed or server plugin is not found
                completed = ManualSync().sync()
        else:
            # Install sync is not completed
            completed = self.fullSync()

        return completed

    def fastSync(self):

        log = self.logMsg

        doUtils = self.doUtils

        lastSync = utils.settings('LastIncrementalSync')
        if not lastSync:
            lastSync = "2010-01-01T00:00:00Z"

        lastSyncTime = utils.convertdate(lastSync)
        log("Last sync run: %s" % lastSyncTime, 1)

        # get server RetentionDateTime
        url = "{server}/emby/Emby.Kodi.SyncQueue/GetServerDateTime?format=json"
        result = doUtils(url)
        retention_time = "2010-01-01T00:00:00Z"
        if result and result.get('RetentionDateTime'):
            retention_time = result['RetentionDateTime']

        #Try/except equivalent
        '''
        try:
            retention_time = result['RetentionDateTime']
        except (TypeError, KeyError):
            retention_time = "2010-01-01T00:00:00Z"
        '''

        retention_time = utils.convertdate(retention_time)
        log("RetentionDateTime: %s" % retention_time, 1)

        # if last sync before retention time do a full sync
        if retention_time > lastSyncTime:
            log("Fast sync server retention insufficient, fall back to full sync", 1)
            return False

        url = "{server}/emby/Emby.Kodi.SyncQueue/{UserId}/GetItems?format=json"
        params = {'LastUpdateDT': lastSync}
        result = doUtils(url, parameters=params)

        try:
            processlist = {

                'added': result['ItemsAdded'],
                'update': result['ItemsUpdated'],
                'userdata': result['UserDataChanged'],
                'remove': result['ItemsRemoved']
            }

        except (KeyError, TypeError):
            log("Failed to retrieve latest updates using fast sync.", 1)
            return False

        else:
            log("Fast sync changes: %s" % result, 1)
            for action in processlist:
                self.triage_items(action, processlist[action])

            return True

    def saveLastSync(self):

        log = self.logMsg
        # Save last sync time
        overlap = 2

        url = "{server}/emby/Emby.Kodi.SyncQueue/GetServerDateTime?format=json"
        result = self.doUtils(url)
        try: # datetime fails when used more than once, TypeError
            server_time = result['ServerDateTime']
            server_time = utils.convertdate(server_time)

        except Exception as e:
            # If the server plugin is not installed or an error happened.
            log("An exception occurred: %s" % e, 1)
            time_now = datetime.utcnow()-timedelta(minutes=overlap)
            lastSync = time_now.strftime('%Y-%m-%dT%H:%M:%SZ')
            log("New sync time: client time -%s min: %s" % (overlap, lastSync), 1)

        else:
            lastSync = (server_time - timedelta(minutes=overlap)).strftime('%Y-%m-%dT%H:%M:%SZ')
            log("New sync time: server time -%s min: %s" % (overlap, lastSync), 1)

        finally:
            utils.settings('LastIncrementalSync', value=lastSync)

    def shouldStop(self):
        # Checkpoint during the syncing process
        if self.monitor.abortRequested():
            return True
        elif utils.window('emby_shouldStop') == "true":
            return True
        else: # Keep going
            return False

    def dbCommit(self, connection):

        log = self.logMsg
        window = utils.window
        # Central commit, verifies if Kodi database update is running
        kodidb_scan = window('emby_kodiScan') == "true"

        while kodidb_scan:

            log("Kodi scan is running. Waiting...", 1)
            kodidb_scan = window('emby_kodiScan') == "true"

            if self.shouldStop():
                log("Commit unsuccessful. Sync terminated.", 1)
                break

            if self.monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                log("Commit unsuccessful.", 1)
                break
        else:
            connection.commit()
            log("Commit successful.", 1)

    def fullSync(self, manualrun=False, repair=False, forceddialog=False):

        log = self.logMsg
        window = utils.window
        settings = utils.settings
        # Only run once when first setting up. Can be run manually.
        emby = self.emby
        music_enabled = utils.settings('enableMusic') == "true"

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
            forceddialog = True
        else:
            message = "Initial sync"
            forceddialog = True
            window('emby_initialScan', value="true")

        pDialog = self.progressDialog("%s" % message, forced=forceddialog)
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
                log("SyncDatabase (finished %s in: %s)"
                    % (itemtype, str(elapsedTime).split('.')[0]), 1)
        else:
            # Close the Kodi cursor
            kodicursor.close()

        # sync music
        if music_enabled:

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
                log("SyncDatabase (finished music in: %s)"
                    % (str(elapsedTime).split('.')[0]), 1)
            musiccursor.close()

        if pDialog:
            pDialog.close()

        embycursor.close()

        settings('SyncInstallRunDone', value="true")
        settings("dbCreatedWithVersion", self.clientInfo.getVersion())
        self.saveLastSync()
        xbmc.executebuiltin('UpdateLibrary(video)')
        elapsedtotal = datetime.now() - starttotal

        xbmc.executebuiltin('InhibitIdleShutdown(false)')
        utils.setScreensaver(value=screensaver)
        window('emby_dbScan', clear=True)
        window('emby_initialScan', clear=True)
        if forceddialog:
            xbmcgui.Dialog().notification(
                        heading="Emby for Kodi",
                        message="%s %s %s" %
                                (message, utils.language(33025), str(elapsedtotal).split('.')[0]),
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

        log = self.logMsg
        # Compare the views to emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        kodi_db = kodidb.Kodidb_Functions(kodicursor)
        doUtils = self.doUtils
        vnodes = self.vnodes

        # Get views
        url = "{server}/emby/Users/{UserId}/Views?format=json"
        result = doUtils(url)
        grouped_views = result['Items']
        ordered_views = emby.getViews(sortedlist=True)
        all_views = []
        sorted_views = []
        for view in ordered_views:
            all_views.append(view['name'])
            if view['type'] == "music":
                continue

            if view['type'] == "mixed":
                sorted_views.append(view['name'])
            sorted_views.append(view['name'])
        log("Sorted views: %s" % sorted_views, 1)

        # total nodes for window properties
        vnodes.clearProperties()
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
        mediatypes = ['movies', 'tvshows', 'musicvideos', 'homevideos', 'music', 'photos']
        for mediatype in mediatypes:

            nodes = [] # Prevent duplicate for nodes of the same type
            playlists = [] # Prevent duplicate for playlists of the same type
            # Get media folders from server
            folders = emby.getViews(mediatype, root=True)
            for folder in folders:

                folderid = folder['id']
                foldername = folder['name']
                viewtype = folder['type']

                if foldername not in all_views:
                    # Media folders are grouped into userview
                    url = "{server}/emby/Users/{UserId}/Items?format=json"
                    params = {
                        'ParentId': folderid,
                        'Recursive': True,
                        'Limit': 1,
                        'IncludeItemTypes': emby_mediatypes[mediatype]
                    } # Get one item from server using the folderid
                    result = doUtils(url, parameters=params)
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
                                if emby.verifyView(grouped_view['Id'], verifyitem):
                                    # Take the name of the userview
                                    log("Found corresponding view: %s %s"
                                        % (grouped_view['Name'], grouped_view['Id']), 1)
                                    foldername = grouped_view['Name']
                                    break
                        else:
                            # Unable to find a match, add the name to our sorted_view list
                            sorted_views.append(foldername)
                            log("Couldn't find corresponding grouped view: %s" % sorted_views, 1)

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
                    log("Creating viewid: %s in Emby database." % folderid, 1)
                    tagid = kodi_db.createTag(foldername)
                    # Create playlist for the video library
                    if (foldername not in playlists and
                            mediatype in ('movies', 'tvshows', 'musicvideos')):
                        utils.playlistXSP(mediatype, foldername, folderid, viewtype)
                        playlists.append(foldername)
                    # Create the video node
                    if foldername not in nodes and mediatype not in ("musicvideos", "music"):
                        vnodes.viewNode(sorted_views.index(foldername), foldername, mediatype,
                            viewtype, folderid)
                        if viewtype == "mixed": # Change the value
                            sorted_views[sorted_views.index(foldername)] = "%ss" % foldername
                        nodes.append(foldername)
                        totalnodes += 1
                    # Add view to emby database
                    emby_db.addView(folderid, foldername, viewtype, tagid)

                else:
                    log(' '.join((

                        "Found viewid: %s" % folderid,
                        "viewname: %s" % current_viewname,
                        "viewtype: %s" % current_viewtype,
                        "tagid: %s" % current_tagid)), 2)

                    # View is still valid
                    try:
                        current_views.remove(folderid)
                    except ValueError:
                        # View was just created, nothing to remove
                        pass

                    # View was modified, update with latest info
                    if current_viewname != foldername:
                        log("viewid: %s new viewname: %s" % (folderid, foldername), 1)
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
                                    vnodes.viewNode(
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
                                vnodes.viewNode(sorted_views.index(foldername), foldername,
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
                                vnodes.viewNode(sorted_views.index(foldername), foldername,
                                    mediatype, viewtype, folderid)
                                if viewtype == "mixed": # Change the value
                                    sorted_views[sorted_views.index(foldername)] = "%ss" % foldername
                                nodes.append(foldername)
                                totalnodes += 1
        else:
            # Add video nodes listings
            vnodes.singleNode(totalnodes, "Favorite movies", "movies", "favourites")
            totalnodes += 1
            vnodes.singleNode(totalnodes, "Favorite tvshows", "tvshows", "favourites")
            totalnodes += 1
            vnodes.singleNode(totalnodes, "channels", "movies", "channels")
            totalnodes += 1
            # Save total
            utils.window('Emby.nodes.total', str(totalnodes))

            # Remove any old referenced views
            log("Removing views: %s" % current_views, 1)
            for view in current_views:
                emby_db.removeView(view)

    def movies(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        lang = utils.language
        # Get movies from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        movies = itemtypes.Movies(embycursor, kodicursor)

        views = emby_db.getView_byType('movies')
        views += emby_db.getView_byType('mixed')
        log("Media folders: %s" % views, 1)

        ##### PROCESS MOVIES #####
        for view in views:

            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (lang(33017), viewName))

            # Initial or repair sync
            all_embymovies = emby.getMovies(viewId, dialog=pdialog)
            total = all_embymovies['TotalRecordCount']
            embymovies = all_embymovies['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymovie in embymovies:
                # Process individual movies
                if self.shouldStop():
                    return False

                title = embymovie['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                movies.add_update(embymovie, viewName, viewId)
        else:
            log("Movies finished.", 2)


        ##### PROCESS BOXSETS #####
        if pdialog:
            pdialog.update(heading="Emby for Kodi", message=lang(33018))

        boxsets = emby.getBoxset(dialog=pdialog)
        total = boxsets['TotalRecordCount']
        embyboxsets = boxsets['Items']

        if pdialog:
            pdialog.update(heading="Processing Boxsets / %s items" % total)

        count = 0
        for boxset in embyboxsets:
            # Process individual boxset
            if self.shouldStop():
                return False

            title = boxset['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            movies.add_updateBoxset(boxset)
        else:
            log("Boxsets finished.", 2)

        return True

    def musicvideos(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        # Get musicvideos from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        mvideos = itemtypes.MusicVideos(embycursor, kodicursor)

        views = emby_db.getView_byType('musicvideos')
        log("Media folders: %s" % views, 1)

        for view in views:

            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (utils.language(33019), viewName))

            # Initial or repair sync
            all_embymvideos = emby.getMusicVideos(viewId, dialog=pdialog)
            total = all_embymvideos['TotalRecordCount']
            embymvideos = all_embymvideos['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymvideo in embymvideos:
                # Process individual musicvideo
                if self.shouldStop():
                    return False

                title = embymvideo['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                mvideos.add_update(embymvideo, viewName, viewId)
        else:
            log("MusicVideos finished.", 2)

        return True

    def tvshows(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        # Get shows from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        tvshows = itemtypes.TVShows(embycursor, kodicursor)

        views = emby_db.getView_byType('tvshows')
        views += emby_db.getView_byType('mixed')
        log("Media folders: %s" % views, 1)

        for view in views:

            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (utils.language(33020), viewName))

            all_embytvshows = emby.getShows(viewId, dialog=pdialog)
            total = all_embytvshows['TotalRecordCount']
            embytvshows = all_embytvshows['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embytvshow in embytvshows:
                # Process individual show
                if self.shouldStop():
                    return False

                itemid = embytvshow['Id']
                title = embytvshow['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                tvshows.add_update(embytvshow, viewName, viewId)

                # Process episodes
                all_episodes = emby.getEpisodesbyShow(itemid)
                for episode in all_episodes['Items']:

                    # Process individual show
                    if self.shouldStop():
                        return False

                    episodetitle = episode['Name']
                    if pdialog:
                        pdialog.update(percentage, message="%s - %s" % (title, episodetitle))
                    tvshows.add_updateEpisode(episode)
        else:
            log("TVShows finished.", 2)

        return True

    def music(self, embycursor, kodicursor, pdialog):
        # Get music from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        music = itemtypes.Music(embycursor, kodicursor)

        process = {

            'artists': [emby.getArtists, music.add_updateArtist],
            'albums': [emby.getAlbums, music.add_updateAlbum],
            'songs': [emby.getSongs, music.add_updateSong]
        }
        types = ['artists', 'albums', 'songs']
        for itemtype in types:

            if pdialog:
                pdialog.update(
                    heading="Emby for Kodi",
                    message="%s %s..." % (utils.language(33021), itemtype))

            all_embyitems = process[itemtype][0](dialog=pdialog)
            total = all_embyitems['TotalRecordCount']
            embyitems = all_embyitems['Items']

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (itemtype, total))

            count = 0
            for embyitem in embyitems:
                # Process individual item
                if self.shouldStop():
                    return False

                title = embyitem['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1

                process[itemtype][1](embyitem)
            else:
                self.logMsg("%s finished." % itemtype, 2)

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

            self.logMsg("Queue %s: %s" % (process, items), 1)
            processlist[process].extend(items)

    def incrementalSync(self):

        log = self.logMsg

        embyconn = utils.kodiSQL('emby')
        embycursor = embyconn.cursor()
        kodiconn = utils.kodiSQL('video')
        kodicursor = kodiconn.cursor()
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        pDialog = None
        update_embydb = False

        if self.refresh_views:
            # Received userconfig update
            self.refresh_views = False
            self.maintainViews(embycursor, kodicursor)
            self.forceLibraryUpdate = True
            update_embydb = True

        if self.addedItems or self.updateItems or self.userdataItems or self.removeItems:
            # Only present dialog if we are going to process items
            pDialog = self.progressDialog('Incremental sync')


        process = {

            'added': self.addedItems,
            'update': self.updateItems,
            'userdata': self.userdataItems,
            'remove': self.removeItems
        }
        types = ['added', 'update', 'userdata', 'remove']
        for type in types:

            if process[type] and utils.window('emby_kodiScan') != "true":

                listItems = list(process[type])
                del process[type][:] # Reset class list

                items_process = itemtypes.Items(embycursor, kodicursor)
                update = False

                # Prepare items according to process type
                if type == "added":
                    items = emby.sortby_mediatype(listItems)

                elif type in ("userdata", "remove"):
                    items = emby_db.sortby_mediaType(listItems, unsorted=False)

                else:
                    items = emby_db.sortby_mediaType(listItems)
                    if items.get('Unsorted'):
                        sorted_items = emby.sortby_mediatype(items['Unsorted'])
                        doupdate = items_process.itemsbyId(sorted_items, "added", pDialog)
                        if doupdate:
                            embyupdate, kodiupdate_video = doupdate
                            if embyupdate:
                                update_embydb = True
                            if kodiupdate_video:
                                self.forceLibraryUpdate = True
                        del items['Unsorted']

                doupdate = items_process.itemsbyId(items, type, pDialog)
                if doupdate:
                    embyupdate, kodiupdate_video = doupdate
                    if embyupdate:
                        update_embydb = True
                    if kodiupdate_video:
                        self.forceLibraryUpdate = True

        if update_embydb:
            update_embydb = False
            log("Updating emby database.", 1)
            embyconn.commit()
            self.saveLastSync()

        if self.forceLibraryUpdate:
            # Force update the Kodi library
            self.forceLibraryUpdate = False
            self.dbCommit(kodiconn)

            log("Updating video library.", 1)
            utils.window('emby_kodiScan', value="true")
            xbmc.executebuiltin('UpdateLibrary(video)')

        if pDialog:
            pDialog.close()

        kodicursor.close()
        embycursor.close()


    def compareDBVersion(self, current, minimum):
        # It returns True is database is up to date. False otherwise.
        self.logMsg("current: %s minimum: %s" % (current, minimum), 1)
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
        except Exception as e:
            utils.window('emby_dbScan', clear=True)
            xbmcgui.Dialog().ok(
                        heading="Emby for Kodi",
                        line1=(
                            "Library sync thread has exited! "
                            "You should restart Kodi now. "
                            "Please report this on the forum."))
            raise

    def run_internal(self):

        log = self.logMsg
        lang = utils.language
        window = utils.window
        settings = utils.settings
        dialog = xbmcgui.Dialog()

        startupComplete = False
        monitor = self.monitor

        log("---===### Starting LibrarySync ###===---", 0)

        while not monitor.abortRequested():

            # In the event the server goes offline
            while self.suspend_thread:
                # Set in service.py
                if monitor.waitForAbort(5):
                    # Abort was requested while waiting. We should exit
                    break

            if (window('emby_dbCheck') != "true" and settings('SyncInstallRunDone') == "true"):
                # Verify the validity of the database
                currentVersion = settings('dbCreatedWithVersion')
                minVersion = window('emby_minDBVersion')
                uptoDate = self.compareDBVersion(currentVersion, minVersion)

                if not uptoDate:
                    log("Database version out of date: %s minimum version required: %s"
                        % (currentVersion, minVersion), 0)

                    resp = dialog.yesno("Emby for Kodi", lang(33022))
                    if not resp:
                        log("Database version is out of date! USER IGNORED!", 0)
                        dialog.ok("Emby for Kodi", lang(33023))
                    else:
                        utils.reset()

                    break

                window('emby_dbCheck', value="true")


            if not startupComplete:
                # Verify the video database can be found
                videoDb = utils.getKodiVideoDBPath()
                if not xbmcvfs.exists(videoDb):
                    # Database does not exists
                    log(
                        "The current Kodi version is incompatible "
                        "with the Emby for Kodi add-on. Please visit "
                        "https://github.com/MediaBrowser/Emby.Kodi/wiki "
                        "to know which Kodi versions are supported.", 0)

                    dialog.ok(
                            heading="Emby for Kodi",
                            line1=lang(33024))
                    break

                # Run start up sync
                log("Database version: %s" % settings('dbCreatedWithVersion'), 0)
                log("SyncDatabase (started)", 1)
                startTime = datetime.now()
                librarySync = self.startSync()
                elapsedTime = datetime.now() - startTime
                log("SyncDatabase (finished in: %s) %s"
                    % (str(elapsedTime).split('.')[0], librarySync), 1)
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
                    log("SyncDatabase onWake (started)", 0)
                    librarySync = self.startSync()
                    log("SyncDatabase onWake (finished) %s" % librarySync, 0)

            if self.stop_thread:
                # Set in service.py
                log("Service terminated thread.", 2)
                break

            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        log("###===--- LibrarySync Stopped ---===###", 0)

    def stopThread(self):
        self.stop_thread = True
        self.logMsg("Ending thread...", 2)

    def suspendThread(self):
        self.suspend_thread = True
        self.logMsg("Pausing thread...", 0)

    def resumeThread(self):
        self.suspend_thread = False
        self.logMsg("Resuming thread...", 0)


class ManualSync(LibrarySync):


    def __init__(self):

        LibrarySync.__init__(self)

    def sync(self, dialog=False):

        return self.fullSync(manualrun=True, forceddialog=dialog)


    def movies(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        lang = utils.language
        # Get movies from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        movies = itemtypes.Movies(embycursor, kodicursor)

        views = emby_db.getView_byType('movies')
        views += emby_db.getView_byType('mixed')
        log("Media folders: %s" % views, 1)

        # Pull the list of movies and boxsets in Kodi
        try:
            all_kodimovies = dict(emby_db.getChecksum('Movie'))
        except ValueError:
            all_kodimovies = {}

        try:
            all_kodisets = dict(emby_db.getChecksum('BoxSet'))
        except ValueError:
            all_kodisets = {}

        all_embymoviesIds = set()
        all_embyboxsetsIds = set()
        updatelist = []

        ##### PROCESS MOVIES #####
        for view in views:

            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (lang(33026), viewName))

            all_embymovies = emby.getMovies(viewId, basic=True, dialog=pdialog)
            for embymovie in all_embymovies['Items']:

                if self.shouldStop():
                    return False

                API = api.API(embymovie)
                itemid = embymovie['Id']
                all_embymoviesIds.add(itemid)


                if all_kodimovies.get(itemid) != API.getChecksum():
                    # Only update if movie is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log("Movies to update for %s: %s" % (viewName, updatelist), 1)
            embymovies = emby.getFullItems(updatelist)
            total = len(updatelist)
            del updatelist[:]

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymovie in embymovies:
                # Process individual movies
                if self.shouldStop():
                    return False

                title = embymovie['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                movies.add_update(embymovie, viewName, viewId)

        ##### PROCESS BOXSETS #####

        boxsets = emby.getBoxset(dialog=pdialog)
        embyboxsets = []

        if pdialog:
            pdialog.update(heading="Emby for Kodi", message=lang(33027))

        for boxset in boxsets['Items']:

            if self.shouldStop():
                return False

            # Boxset has no real userdata, so using etag to compare
            checksum = boxset['Etag']
            itemid = boxset['Id']
            all_embyboxsetsIds.add(itemid)

            if all_kodisets.get(itemid) != checksum:
                # Only update if boxset is not in Kodi or checksum is different
                updatelist.append(itemid)
                embyboxsets.append(boxset)

        log("Boxsets to update: %s" % updatelist, 1)
        total = len(updatelist)

        if pdialog:
            pdialog.update(heading="Processing Boxsets / %s items" % total)

        count = 0
        for boxset in embyboxsets:
            # Process individual boxset
            if self.shouldStop():
                return False

            title = boxset['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            movies.add_updateBoxset(boxset)

        ##### PROCESS DELETES #####

        for kodimovie in all_kodimovies:
            if kodimovie not in all_embymoviesIds:
                movies.remove(kodimovie)
        else:
            log("Movies compare finished.", 1)

        for boxset in all_kodisets:
            if boxset not in all_embyboxsetsIds:
                movies.remove(boxset)
        else:
            log("Boxsets compare finished.", 1)

        return True

    def musicvideos(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        # Get musicvideos from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        mvideos = itemtypes.MusicVideos(embycursor, kodicursor)

        views = emby_db.getView_byType('musicvideos')
        log("Media folders: %s" % views, 1)

        # Pull the list of musicvideos in Kodi
        try:
            all_kodimvideos = dict(emby_db.getChecksum('MusicVideo'))
        except ValueError:
            all_kodimvideos = {}

        all_embymvideosIds = set()
        updatelist = []

        for view in views:

            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (utils.language(33028), viewName))

            all_embymvideos = emby.getMusicVideos(viewId, basic=True, dialog=pdialog)
            for embymvideo in all_embymvideos['Items']:

                if self.shouldStop():
                    return False

                API = api.API(embymvideo)
                itemid = embymvideo['Id']
                all_embymvideosIds.add(itemid)


                if all_kodimvideos.get(itemid) != API.getChecksum():
                    # Only update if musicvideo is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log("MusicVideos to update for %s: %s" % (viewName, updatelist), 1)
            embymvideos = emby.getFullItems(updatelist)
            total = len(updatelist)
            del updatelist[:]


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embymvideo in embymvideos:
                # Process individual musicvideo
                if self.shouldStop():
                    return False

                title = embymvideo['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                mvideos.add_update(embymvideo, viewName, viewId)

        ##### PROCESS DELETES #####

        for kodimvideo in all_kodimvideos:
            if kodimvideo not in all_embymvideosIds:
                mvideos.remove(kodimvideo)
        else:
            log("MusicVideos compare finished.", 1)

        return True

    def tvshows(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        lang = utils.language
        # Get shows from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        tvshows = itemtypes.TVShows(embycursor, kodicursor)

        views = emby_db.getView_byType('tvshows')
        views += emby_db.getView_byType('mixed')
        log("Media folders: %s" % views, 1)

        # Pull the list of tvshows and episodes in Kodi
        try:
            all_koditvshows = dict(emby_db.getChecksum('Series'))
        except ValueError:
            all_koditvshows = {}

        try:
            all_kodiepisodes = dict(emby_db.getChecksum('Episode'))
        except ValueError:
            all_kodiepisodes = {}

        all_embytvshowsIds = set()
        all_embyepisodesIds = set()
        updatelist = []


        for view in views:

            if self.shouldStop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (lang(33029), viewName))

            all_embytvshows = emby.getShows(viewId, basic=True, dialog=pdialog)
            for embytvshow in all_embytvshows['Items']:

                if self.shouldStop():
                    return False

                API = api.API(embytvshow)
                itemid = embytvshow['Id']
                all_embytvshowsIds.add(itemid)


                if all_koditvshows.get(itemid) != API.getChecksum():
                    # Only update if movie is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log("TVShows to update for %s: %s" % (viewName, updatelist), 1)
            embytvshows = emby.getFullItems(updatelist)
            total = len(updatelist)
            del updatelist[:]


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            count = 0
            for embytvshow in embytvshows:
                # Process individual show
                if self.shouldStop():
                    return False

                itemid = embytvshow['Id']
                title = embytvshow['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1
                tvshows.add_update(embytvshow, viewName, viewId)

            else:
                # Get all episodes in view
                if pdialog:
                    pdialog.update(
                            heading="Emby for Kodi",
                            message="%s %s..." % (lang(33030), viewName))

                all_embyepisodes = emby.getEpisodes(viewId, basic=True, dialog=pdialog)
                for embyepisode in all_embyepisodes['Items']:

                    if self.shouldStop():
                        return False

                    API = api.API(embyepisode)
                    itemid = embyepisode['Id']
                    all_embyepisodesIds.add(itemid)

                    if all_kodiepisodes.get(itemid) != API.getChecksum():
                        # Only update if movie is not in Kodi or checksum is different
                        updatelist.append(itemid)

                log("Episodes to update for %s: %s" % (viewName, updatelist), 1)
                embyepisodes = emby.getFullItems(updatelist)
                total = len(updatelist)
                del updatelist[:]

                count = 0
                for episode in embyepisodes:

                    # Process individual episode
                    if self.shouldStop():
                        return False

                    title = episode['SeriesName']
                    episodetitle = episode['Name']
                    if pdialog:
                        percentage = int((float(count) / float(total))*100)
                        pdialog.update(percentage, message="%s - %s" % (title, episodetitle))
                        count += 1
                    tvshows.add_updateEpisode(episode)

        ##### PROCESS DELETES #####

        for koditvshow in all_koditvshows:
            if koditvshow not in all_embytvshowsIds:
                tvshows.remove(koditvshow)
        else:
            log("TVShows compare finished.", 1)

        for kodiepisode in all_kodiepisodes:
            if kodiepisode not in all_embyepisodesIds:
                tvshows.remove(kodiepisode)
        else:
            log("Episodes compare finished.", 1)

        return True

    def music(self, embycursor, kodicursor, pdialog):

        log = self.logMsg
        # Get music from emby
        emby = self.emby
        emby_db = embydb.Embydb_Functions(embycursor)
        music = itemtypes.Music(embycursor, kodicursor)

        # Pull the list of artists, albums, songs
        try:
            all_kodiartists = dict(emby_db.getChecksum('MusicArtist'))
        except ValueError:
            all_kodiartists = {}

        try:
            all_kodialbums = dict(emby_db.getChecksum('MusicAlbum'))
        except ValueError:
            all_kodialbums = {}

        try:
            all_kodisongs = dict(emby_db.getChecksum('Audio'))
        except ValueError:
            all_kodisongs = {}

        all_embyartistsIds = set()
        all_embyalbumsIds = set()
        all_embysongsIds = set()
        updatelist = []

        process = {

            'artists': [emby.getArtists, music.add_updateArtist],
            'albums': [emby.getAlbums, music.add_updateAlbum],
            'songs': [emby.getSongs, music.add_updateSong]
        }
        types = ['artists', 'albums', 'songs']
        for type in types:

            if pdialog:
                pdialog.update(
                        heading="Emby for Kodi",
                        message="%s %s..." % (utils.language(33031), type))

            if type != "artists":
                all_embyitems = process[type][0](basic=True, dialog=pdialog)
            else:
                all_embyitems = process[type][0](dialog=pdialog)
            for embyitem in all_embyitems['Items']:

                if self.shouldStop():
                    return False

                API = api.API(embyitem)
                itemid = embyitem['Id']
                if type == "artists":
                    all_embyartistsIds.add(itemid)
                    if all_kodiartists.get(itemid) != API.getChecksum():
                        # Only update if artist is not in Kodi or checksum is different
                        updatelist.append(itemid)
                elif type == "albums":
                    all_embyalbumsIds.add(itemid)
                    if all_kodialbums.get(itemid) != API.getChecksum():
                        # Only update if album is not in Kodi or checksum is different
                        updatelist.append(itemid)
                else:
                    all_embysongsIds.add(itemid)
                    if all_kodisongs.get(itemid) != API.getChecksum():
                        # Only update if songs is not in Kodi or checksum is different
                        updatelist.append(itemid)

            log("%s to update: %s" % (type, updatelist), 1)
            embyitems = emby.getFullItems(updatelist)
            total = len(updatelist)
            del updatelist[:]

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (type, total))

            count = 0
            for embyitem in embyitems:
                # Process individual item
                if self.shouldStop():
                    return False

                title = embyitem['Name']
                if pdialog:
                    percentage = int((float(count) / float(total))*100)
                    pdialog.update(percentage, message=title)
                    count += 1

                process[type][1](embyitem)

        ##### PROCESS DELETES #####

        for kodiartist in all_kodiartists:
            if kodiartist not in all_embyartistsIds and all_kodiartists[kodiartist] is not None:
                music.remove(kodiartist)
        else:
            log("Artist compare finished.", 1)

        for kodialbum in all_kodialbums:
            if kodialbum not in all_embyalbumsIds:
                music.remove(kodialbum)
        else:
            log("Albums compare finished.", 1)

        for kodisong in all_kodisongs:
            if kodisong not in all_embysongsIds:
                music.remove(kodisong)
        else:
            log("Songs compare finished.", 1)

        return True