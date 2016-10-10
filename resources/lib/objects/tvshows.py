# -*- coding: utf-8 -*-

##################################################################################################

import logging
import urllib
from ntpath import dirname

import api
import common
import embydb_functions as embydb
import kodidb_functions as kodidb
from utils import window, settings, language as lang, catch_except

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class TVShows(common.Items):


    def __init__(self, embycursor, kodicursor, pdialog=None):

        self.embycursor = embycursor
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodicursor = kodicursor
        self.kodi_db = kodidb.Kodidb_Functions(self.kodicursor)
        self.pdialog = pdialog

        self.new_time = int(settings('newvideotime'))*1000

        common.Items.__init__(self)

    def _get_func(self, item_type, action):

        if item_type == "Series":
            actions = {
                'added': self.added,
                'update': self.add_update,
                'userdata': self.updateUserdata,
                'remove': self.remove
            }
        elif item_type == "Season":
            actions = {
                'added': self.added_season,
                'update': self.add_updateSeason,
                'remove': self.remove
            }
        elif item_type == "Episode":
            actions = {
                'added': self.added_episode,
                'update': self.add_updateEpisode,
                'userdata': self.updateUserdata,
                'remove': self.remove
            }
        else:
            log.info("Unsupported item_type: %s", item_type)
            actions = {}

        return actions.get(action)

    def compare_all(self):
        # Pull the list of movies and boxsets in Kodi
        pdialog = self.pdialog
        views = self.emby_db.getView_byType('tvshows')
        views += self.emby_db.getView_byType('mixed')
        log.info("Media folders: %s", views)

        # Pull the list of tvshows and episodes in Kodi
        try:
            all_koditvshows = dict(self.emby_db.get_checksum('Series'))
        except ValueError:
            all_koditvshows = {}

        log.info("all_koditvshows = %s", all_koditvshows)

        try:
            all_kodiepisodes = dict(self.emby_db.get_checksum('Episode'))
        except ValueError:
            all_kodiepisodes = {}

        all_embytvshowsIds = set()
        all_embyepisodesIds = set()
        updatelist = []


        for view in views:

            if self.should_stop():
                return False

            # Get items per view
            viewId = view['id']
            viewName = view['name']

            if pdialog:
                pdialog.update(
                        heading=lang(29999),
                        message="%s %s..." % (lang(33029), viewName))

            all_embytvshows = self.emby.getShows(viewId, basic=True, dialog=pdialog)
            for embytvshow in all_embytvshows['Items']:

                if self.should_stop():
                    return False

                API = api.API(embytvshow)
                itemid = embytvshow['Id']
                all_embytvshowsIds.add(itemid)


                if all_koditvshows.get(itemid) != API.get_checksum():
                    # Only update if movie is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log.info("TVShows to update for %s: %s", viewName, updatelist)
            embytvshows = self.emby.getFullItems(updatelist)
            self.total = len(updatelist)
            del updatelist[:]


            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, self.total))

            self.count = 0
            for embytvshow in embytvshows:
                # Process individual show
                if self.should_stop():
                    return False

                itemid = embytvshow['Id']
                title = embytvshow['Name']
                all_embytvshowsIds.add(itemid)
                self.update_pdialog()

                self.add_update(embytvshow, view)
                self.count += 1

            else:
                # Get all episodes in view
                if pdialog:
                    pdialog.update(
                            heading=lang(29999),
                            message="%s %s..." % (lang(33030), viewName))

                all_embyepisodes = self.emby.getEpisodes(viewId, basic=True, dialog=pdialog)
                for embyepisode in all_embyepisodes['Items']:

                    if self.should_stop():
                        return False

                    API = api.API(embyepisode)
                    itemid = embyepisode['Id']
                    all_embyepisodesIds.add(itemid)
                    if "SeriesId" in embyepisode:
                        all_embytvshowsIds.add(embyepisode['SeriesId'])

                    if all_kodiepisodes.get(itemid) != API.get_checksum():
                        # Only update if movie is not in Kodi or checksum is different
                        updatelist.append(itemid)

                log.info("Episodes to update for %s: %s", viewName, updatelist)
                embyepisodes = self.emby.getFullItems(updatelist)
                self.total = len(updatelist)
                del updatelist[:]

                self.count = 0
                for episode in embyepisodes:

                    # Process individual episode
                    if self.should_stop():
                        return False
                    self.title = "%s - %s" % (episode.get('SeriesName', "Unknown"), episode['Name'])
                    self.add_updateEpisode(episode)
                    self.count += 1

        ##### PROCESS DELETES #####

        log.info("all_embytvshowsIds = %s ", all_embytvshowsIds)

        for koditvshow in all_koditvshows:
            if koditvshow not in all_embytvshowsIds:
                self.remove(koditvshow)

        log.info("TVShows compare finished.")

        for kodiepisode in all_kodiepisodes:
            if kodiepisode not in all_embyepisodesIds:
                self.remove(kodiepisode)

        log.info("Episodes compare finished.")

        return True


    def added(self, items, total=None, view=None):

        for item in super(TVShows, self).added(items, total):
            if self.add_update(item, view):
                # Add episodes
                all_episodes = self.emby.getEpisodesbyShow(item['Id'])
                self.added_episode(all_episodes['Items'])

    def added_season(self, items, total=None, view=None):

        update = True if not self.total else False

        for item in super(TVShows, self).added(items, total, update):
            self.title = "%s - %s" % (item.get('SeriesName', "Unknown"), self.title)

            if self.add_updateSeason(item):
                # Add episodes
                all_episodes = self.emby.getEpisodesbySeason(item['Id'])
                self.added_episode(all_episodes['Items'])

    def added_episode(self, items, total=None, view=None):

        update = True if not self.total else False

        for item in super(TVShows, self).added(items, total, update):
            self.title = "%s - %s" % (item.get('SeriesName', "Unknown"), self.title)

            if self.add_updateEpisode(item):
                self.content_pop(self.title)

    @catch_except()
    def add_update(self, item, view=None):
        # Process single tvshow
        kodicursor = self.kodicursor
        emby = self.emby
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        if settings('syncEmptyShows') == "false" and not item.get('RecursiveItemCount'):
            log.info("Skipping empty show: %s", item['Name'])
            return
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        force_episodes = False
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            showid = emby_dbitem[0]
            pathid = emby_dbitem[2]
            log.info("showid: %s pathid: %s", showid, pathid)

        except TypeError:
            update_item = False
            log.debug("showid: %s not found", itemid)
            kodicursor.execute("select coalesce(max(idShow),0) from tvshow")
            showid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM tvshow WHERE idShow = ?"
            kodicursor.execute(query, (showid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                log.info("showid: %s missing from Kodi, repairing the entry", showid)
                # Force re-add episodes after the show is re-created.
                force_episodes = True


        if view is None:
            # Get view tag from emby
            viewtag, viewid, mediatype = emby.getView_embyId(itemid)
            log.debug("View tag found: %s", viewtag)
        else:
            viewtag = view['name']
            viewid = view['id']

        # fileId information
        checksum = API.get_checksum()
        userdata = API.get_userdata()

        # item details
        genres = item['Genres']
        title = item['Name']
        plot = API.get_overview()
        rating = item.get('CommunityRating')
        premieredate = API.get_premiere_date()
        tvdb = API.get_provider('Tvdb')
        sorttitle = item['SortName']
        mpaa = API.get_mpaa()
        genre = " / ".join(genres)
        studios = API.get_studios()
        studio = " / ".join(studios)

        # Verify series pooling
        if not update_item and tvdb:
            query = "SELECT idShow FROM tvshow WHERE C12 = ?"
            kodicursor.execute(query, (tvdb,))
            try:
                temp_showid = kodicursor.fetchone()[0]
            except TypeError:
                pass
            else:
                emby_other = emby_db.getItem_byKodiId(temp_showid, "tvshow")
                if emby_other and viewid == emby_other[2]:
                    log.info("Applying series pooling for %s", title)
                    emby_other_item = emby_db.getItem_byId(emby_other[0])
                    showid = emby_other_item[0]
                    pathid = emby_other_item[2]
                    log.info("showid: %s pathid: %s", showid, pathid)
                    # Create the reference in emby table
                    emby_db.addReference(itemid, showid, "Series", "tvshow", pathid=pathid,
                                         checksum=checksum, mediafolderid=viewid)
                    update_item = True


        ##### GET THE FILE AND PATH #####
        playurl = API.get_file_path()

        if self.direct_path:
            # Direct paths is set the Kodi way
            if "\\" in playurl:
                # Local path
                path = "%s\\" % playurl
                toplevelpath = "%s\\" % dirname(dirname(path))
            else:
                # Network path
                path = "%s/" % playurl
                toplevelpath = "%s/" % dirname(dirname(path))

            if not self.path_validation(path):
                return False

            window('emby_pathverified', value="true")
        else:
            # Set plugin path
            toplevelpath = "plugin://plugin.video.emby.tvshows/"
            path = "%s%s/" % (toplevelpath, itemid)


        ##### UPDATE THE TVSHOW #####
        if update_item:
            log.info("UPDATE tvshow itemid: %s - Title: %s", itemid, title)

            # Update the tvshow entry
            query = ' '.join((

                "UPDATE tvshow",
                "SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?,",
                    "c12 = ?, c13 = ?, c14 = ?, c15 = ?",
                "WHERE idShow = ?"
            ))
            kodicursor.execute(query, (title, plot, rating, premieredate, genre, title,
                                       tvdb, mpaa, studio, sorttitle, showid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE TVSHOW #####
        else:
            log.info("ADD tvshow itemid: %s - Title: %s", itemid, title)

            # Add top path
            toppathid = self.kodi_db.addPath(toplevelpath)
            query = ' '.join((

                "UPDATE path",
                "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
                "WHERE idPath = ?"
            ))
            kodicursor.execute(query, (toplevelpath, "tvshows", "metadata.local", 1, toppathid))

            # Add path
            pathid = self.kodi_db.addPath(path)

            # Create the tvshow entry
            query = (
                '''
                INSERT INTO tvshow(idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14, c15)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (showid, title, plot, rating, premieredate, genre,
                                       title, tvdb, mpaa, studio, sorttitle))

            # Link the path
            query = "INSERT INTO tvshowlinkpath(idShow, idPath) values(?, ?)"
            kodicursor.execute(query, (showid, pathid))

            # Create the reference in emby table
            emby_db.addReference(itemid, showid, "Series", "tvshow", pathid=pathid,
                                 checksum=checksum, mediafolderid=viewid)

        # Update the path
        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        kodicursor.execute(query, (path, None, None, 1, pathid))

        # Process cast
        people = artwork.get_people_artwork(item['People'])
        self.kodi_db.addPeople(showid, people, "tvshow")
        # Process genres
        self.kodi_db.addGenres(showid, genres, "tvshow")
        # Process artwork
        artwork.add_artwork(artwork.get_all_artwork(item), showid, "tvshow", kodicursor)
        # Process studios
        self.kodi_db.addStudios(showid, studios, "tvshow")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite tvshows")
        self.kodi_db.addTags(showid, tags, "tvshow")
        # Process seasons
        all_seasons = emby.getSeasons(itemid)
        for season in all_seasons['Items']:
            self.add_updateSeason(season, showid=showid)
        else:
            # Finally, refresh the all season entry
            seasonid = self.kodi_db.addSeason(showid, -1)
            # Process artwork
            artwork.add_artwork(artwork.get_all_artwork(item), seasonid, "season", kodicursor)

        if force_episodes:
            # We needed to recreate the show entry. Re-add episodes now.
            log.info("Repairing episodes for showid: %s %s", showid, title)
            all_episodes = emby.getEpisodesbyShow(itemid)
            self.added_episode(all_episodes['Items'], None)

        return True

    def add_updateSeason(self, item, showid=None):

        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork

        seasonnum = item.get('IndexNumber', 1)

        if showid is None:
            try:
                seriesId = item['SeriesId']
                showid = emby_db.getItem_byId(seriesId)[0]
            except KeyError:
                return
            except TypeError:
                # Show is missing, update show instead.
                show = self.emby.getItem(seriesId)
                self.add_update(show)
                return

        seasonid = self.kodi_db.addSeason(showid, seasonnum, item['Name'])

        if item['LocationType'] != "Virtual":
            # Create the reference in emby table
            emby_db.addReference(item['Id'], seasonid, "Season", "season", parentid=showid)

        # Process artwork
        artwork.add_artwork(artwork.get_all_artwork(item), seasonid, "season", kodicursor)

        return True

    @catch_except()
    def add_updateEpisode(self, item):
        # Process single episode
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        if item.get('LocationType') == "Virtual": # TODO: Filter via api instead
            log.info("Skipping virtual episode: %s", item['Name'])
            return

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            episodeid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("episodeid: %s fileid: %s pathid: %s", episodeid, fileid, pathid)

        except TypeError:
            update_item = False
            log.debug("episodeid: %s not found", itemid)
            # episodeid
            kodicursor.execute("select coalesce(max(idEpisode),0) from episode")
            episodeid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM episode WHERE idEpisode = ?"
            kodicursor.execute(query, (episodeid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                log.info("episodeid: %s missing from Kodi, repairing the entry", episodeid)

        # fileId information
        checksum = API.get_checksum()
        dateadded = API.get_date_created()
        userdata = API.get_userdata()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        people = API.get_people()
        writer = " / ".join(people['Writer'])
        director = " / ".join(people['Director'])
        title = item['Name']
        plot = API.get_overview()
        rating = item.get('CommunityRating')
        runtime = API.get_runtime()
        premieredate = API.get_premiere_date()

        # episode details
        try:
            seriesId = item['SeriesId']
        except KeyError:
            # Missing seriesId, skip
            log.error("Skipping: %s. SeriesId is missing.", itemid)
            return False

        season = item.get('ParentIndexNumber')
        episode = item.get('IndexNumber', -1)

        if season is None:
            if item.get('AbsoluteEpisodeNumber'):
                # Anime scenario
                season = 1
                episode = item['AbsoluteEpisodeNumber']
            else:
                season = -1 if "Specials" not in item['Path'] else 0

        # Specials ordering within season
        if item.get('AirsAfterSeasonNumber'):
            airsBeforeSeason = item['AirsAfterSeasonNumber']
            airsBeforeEpisode = 4096 # Kodi default number for afterseason ordering
        else:
            airsBeforeSeason = item.get('AirsBeforeSeasonNumber')
            airsBeforeEpisode = item.get('AirsBeforeEpisodeNumber')

        # Append multi episodes to title
        if item.get('IndexNumberEnd'):
            title = "| %02d | %s" % (item['IndexNumberEnd'], title)

        # Get season id
        show = emby_db.getItem_byId(seriesId)
        try:
            showid = show[0]
        except TypeError:
            # Show is missing from database
            show = self.emby.getItem(seriesId)
            self.add_update(show)
            show = emby_db.getItem_byId(seriesId)
            try:
                showid = show[0]
            except TypeError:
                log.error("Skipping: %s. Unable to add series: %s", itemid, seriesId)
                return False

        seasonid = self.kodi_db.addSeason(showid, season)


        ##### GET THE FILE AND PATH #####
        playurl = API.get_file_path()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.direct_path:
            # Direct paths is set the Kodi way
            if not self.path_validation(playurl):
                return False

            path = playurl.replace(filename, "")
            window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.emby.tvshows/%s/" % seriesId
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': episodeid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE EPISODE #####
        if update_item:
            log.info("UPDATE episode itemid: %s - Title: %s", itemid, title)

            # Update the movie entry
            if self.kodi_version in (16, 17):
                # Kodi Jarvis, Krypton
                query = ' '.join((

                    "UPDATE episode",
                    "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                        "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idSeason = ?, idShow = ?",
                    "WHERE idEpisode = ?"
                ))
                kodicursor.execute(query, (title, plot, rating, writer, premieredate, runtime,
                                           director, season, episode, title, airsBeforeSeason,
                                           airsBeforeEpisode, seasonid, showid, episodeid))
            else:
                query = ' '.join((

                    "UPDATE episode",
                    "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                        "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idShow = ?",
                    "WHERE idEpisode = ?"
                ))
                kodicursor.execute(query, (title, plot, rating, writer, premieredate, runtime,
                                           director, season, episode, title, airsBeforeSeason,
                                           airsBeforeEpisode, showid, episodeid))
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
            # Update parentid reference
            emby_db.updateParentId(itemid, seasonid)

        ##### OR ADD THE EPISODE #####
        else:
            log.info("ADD episode itemid: %s - Title: %s", itemid, title)

            # Add path
            pathid = self.kodi_db.addPath(path)
            # Add the file
            fileid = self.kodi_db.addFile(filename, pathid)

            # Create the episode entry
            if self.kodi_version in (16, 17):
                # Kodi Jarvis, Krypton
                query = (
                    '''
                    INSERT INTO episode(
                        idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                        idShow, c15, c16, idSeason)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (episodeid, fileid, title, plot, rating, writer,
                                           premieredate, runtime, director, season, episode, title,
                                           showid, airsBeforeSeason, airsBeforeEpisode, seasonid))
            else:
                query = (
                    '''
                    INSERT INTO episode(
                        idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                        idShow, c15, c16)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (episodeid, fileid, title, plot, rating, writer,
                                           premieredate, runtime, director, season, episode, title,
                                           showid, airsBeforeSeason, airsBeforeEpisode))

            # Create the reference in emby table
            emby_db.addReference(itemid, episodeid, "Episode", "episode", fileid, pathid,
                                 seasonid, checksum)

        # Update the path
        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        kodicursor.execute(query, (path, None, None, 1, pathid))

        # Update the file
        query = ' '.join((

            "UPDATE files",
            "SET idPath = ?, strFilename = ?, dateAdded = ?",
            "WHERE idFile = ?"
        ))
        kodicursor.execute(query, (pathid, filename, dateadded, fileid))

        # Process cast
        people = artwork.get_people_artwork(item['People'])
        self.kodi_db.addPeople(episodeid, people, "episode")
        # Process artwork
        artworks = artwork.get_all_artwork(item)
        artwork.add_update_art(artworks['Primary'], episodeid, "episode", "thumb", kodicursor)
        # Process stream details
        streams = API.get_media_streams()
        self.kodi_db.addStreams(fileid, streams, runtime)
        # Process playstates
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        if not self.direct_path and resume:
            # Create additional entry for widgets. This is only required for plugin/episode.
            temppathid = self.kodi_db.getPath("plugin://plugin.video.emby.tvshows/")
            tempfileid = self.kodi_db.addFile(filename, temppathid)
            query = ' '.join((

                "UPDATE files",
                "SET idPath = ?, strFilename = ?, dateAdded = ?",
                "WHERE idFile = ?"
            ))
            kodicursor.execute(query, (temppathid, filename, dateadded, tempfileid))
            self.kodi_db.addPlaystate(tempfileid, resume, total, playcount, dateplayed)

        return True

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        API = api.API(item)

        # Get emby information
        itemid = item['Id']
        checksum = API.get_checksum()
        userdata = API.get_userdata()
        runtime = API.get_runtime()
        dateadded = API.get_date_created()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            mediatype = emby_dbitem[4]
            log.info("Update playstate for %s: %s fileid: %s", mediatype, item['Name'], fileid)
        except TypeError:
            return

        # Process favorite tags
        if mediatype == "tvshow":
            if userdata['Favorite']:
                self.kodi_db.addTag(kodiid, "Favorite tvshows", "tvshow")
            else:
                self.kodi_db.removeTag(kodiid, "Favorite tvshows", "tvshow")
        elif mediatype == "episode":
            # Process playstates
            playcount = userdata['PlayCount']
            dateplayed = userdata['LastPlayedDate']
            resume = API.adjust_resume(userdata['Resume'])
            total = round(float(runtime), 6)

            log.debug("%s New resume point: %s", itemid, resume)

            self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
            if not self.direct_path and not resume:
                # Make sure there's no other bookmarks created by widget.
                filename = self.kodi_db.getFile(fileid)
                self.kodi_db.removeFile("plugin://plugin.video.emby.tvshows/", filename)

            if not self.direct_path and resume:
                # Create additional entry for widgets. This is only required for plugin/episode.
                filename = self.kodi_db.getFile(fileid)
                temppathid = self.kodi_db.getPath("plugin://plugin.video.emby.tvshows/")
                tempfileid = self.kodi_db.addFile(filename, temppathid)
                query = ' '.join((

                    "UPDATE files",
                    "SET idPath = ?, strFilename = ?, dateAdded = ?",
                    "WHERE idFile = ?"
                ))
                self.kodicursor.execute(query, (temppathid, filename, dateadded, tempfileid))
                self.kodi_db.addPlaystate(tempfileid, resume, total, playcount, dateplayed)

        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove showid, fileid, pathid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            parentid = emby_dbitem[3]
            mediatype = emby_dbitem[4]
            log.info("Removing %s kodiid: %s fileid: %s", mediatype, kodiid, fileid)
        except TypeError:
            return

        ##### PROCESS ITEM #####

        # Remove the emby reference
        emby_db.removeItem(itemid)

        ##### IF EPISODE #####

        if mediatype == "episode":
            # Delete kodi episode and file, verify season and tvshow
            self.removeEpisode(kodiid, fileid)

            # Season verification
            season = emby_db.getItem_byKodiId(parentid, "season")
            try:
                showid = season[1]
            except TypeError:
                return

            season_episodes = emby_db.getItem_byParentId(parentid, "episode")
            if not season_episodes:
                self.removeSeason(parentid)
                emby_db.removeItem(season[0])

            # Show verification
            show = emby_db.getItem_byKodiId(showid, "tvshow")
            query = ' '.join((

                "SELECT totalCount",
                "FROM tvshowcounts",
                "WHERE idShow = ?"
            ))
            kodicursor.execute(query, (showid,))
            result = kodicursor.fetchone()
            if result and result[0] is None:
                # There's no episodes left, delete show and any possible remaining seasons
                seasons = emby_db.getItem_byParentId(showid, "season")
                for season in seasons:
                    self.removeSeason(season[1])
                else:
                    # Delete emby season entries
                    emby_db.removeItems_byParentId(showid, "season")
                self.removeShow(showid)
                emby_db.removeItem(show[0])

        ##### IF TVSHOW #####

        elif mediatype == "tvshow":
            # Remove episodes, seasons, tvshow
            seasons = emby_db.getItem_byParentId(kodiid, "season")
            for season in seasons:
                seasonid = season[1]
                season_episodes = emby_db.getItem_byParentId(seasonid, "episode")
                for episode in season_episodes:
                    self.removeEpisode(episode[1], episode[2])
                else:
                    # Remove emby episodes
                    emby_db.removeItems_byParentId(seasonid, "episode")
            else:
                # Remove emby seasons
                emby_db.removeItems_byParentId(kodiid, "season")

            # Remove tvshow
            self.removeShow(kodiid)

        ##### IF SEASON #####

        elif mediatype == "season":
            # Remove episodes, season, verify tvshow
            season_episodes = emby_db.getItem_byParentId(kodiid, "episode")
            for episode in season_episodes:
                self.removeEpisode(episode[1], episode[2])
            else:
                # Remove emby episodes
                emby_db.removeItems_byParentId(kodiid, "episode")

            # Remove season
            self.removeSeason(kodiid)

            # Show verification
            seasons = emby_db.getItem_byParentId(parentid, "season")
            if not seasons:
                # There's no seasons, delete the show
                self.removeShow(parentid)
                emby_db.removeItem_byKodiId(parentid, "tvshow")

        log.info("Deleted %s: %s from kodi database", mediatype, itemid)

    def removeShow(self, kodiid):
        
        kodicursor = self.kodicursor
        self.artwork.delete_artwork(kodiid, "tvshow", kodicursor)
        kodicursor.execute("DELETE FROM tvshow WHERE idShow = ?", (kodiid,))
        log.debug("Removed tvshow: %s", kodiid)

    def removeSeason(self, kodiid):
        
        kodicursor = self.kodicursor

        self.artwork.delete_artwork(kodiid, "season", kodicursor)
        kodicursor.execute("DELETE FROM seasons WHERE idSeason = ?", (kodiid,))
        log.debug("Removed season: %s", kodiid)

    def removeEpisode(self, kodiid, fileid):

        kodicursor = self.kodicursor

        self.artwork.delete_artwork(kodiid, "episode", kodicursor)
        kodicursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodiid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        log.debug("Removed episode: %s", kodiid)
