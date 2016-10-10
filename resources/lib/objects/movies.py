# -*- coding: utf-8 -*-

##################################################################################################

import logging
import urllib
from ntpath import dirname
from datetime import datetime

import api
import common
import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb
from utils import window, settings, language as lang, catch_except

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################

    
class Movies(common.Items):

    
    def __init__(self, embycursor, kodicursor, pdialog=None):
        
        self.embycursor = embycursor
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodicursor = kodicursor
        self.kodi_db = kodidb.Kodidb_Functions(self.kodicursor)
        self.pdialog = pdialog

        self.new_time = int(settings('newvideotime'))*1000
        
        common.Items.__init__(self)

    def _get_func(self, item_type, action):

        if item_type == "Movie":
            actions = {
                'added': self.added,
                'update': self.add_update,
                'userdata': self.updateUserdata,
                'remove': self.remove
            }
        elif item_type == "BoxSet":
            actions = {
                'added': self.add_updateBoxset,
                'update': self.add_updateBoxset,
                'remove': self.remove
            }
        else:
            log.info("Unsupported item_type: %s", item_type)
            actions = {}

        return actions.get(action)

    def compare_all(self):
        # Pull the list of movies and boxsets in Kodi
        pdialog = self.pdialog
        views = self.emby_db.getView_byType('movies')
        views += self.emby_db.getView_byType('mixed')
        log.info("Media folders: %s" % views)

        try:
            all_kodisets = dict(self.emby_db.get_checksum('BoxSet'))
        except ValueError:
            all_kodisets = {}

        try:
            all_kodimovies = dict(self.emby_db.get_checksum('Movie'))
        except ValueError:
            all_kodimovies = {}

        all_embymoviesIds = set()
        all_embyboxsetsIds = set()
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
                        message="%s %s..." % (lang(33026), viewName))

            all_embymovies = self.emby.getMovies(viewId, basic=True, dialog=pdialog)
            for embymovie in all_embymovies['Items']:

                if self.should_stop():
                    return False

                API = api.API(embymovie)
                itemid = embymovie['Id']
                all_embymoviesIds.add(itemid)


                if all_kodimovies.get(itemid) != API.get_checksum():
                    # Only update if movie is not in Kodi or checksum is different
                    updatelist.append(itemid)

            log.info("Movies to update for %s: %s" % (viewName, updatelist))
            embymovies = self.emby.getFullItems(updatelist)
            total = len(updatelist)
            del updatelist[:]

            if pdialog:
                pdialog.update(heading="Processing %s / %s items" % (viewName, total))

            self.added(embymovies, total, view)

        boxsets = self.emby.getBoxset(dialog=pdialog)
        embyboxsets = []

        if pdialog:
            pdialog.update(heading=lang(29999), message=lang(33027))

        for boxset in boxsets['Items']:

            if self.should_stop():
                return False

            # Boxset has no real userdata, so using etag to compare
            itemid = boxset['Id']
            all_embyboxsetsIds.add(itemid)

            if all_kodisets.get(itemid) != boxset['Etag']:
                # Only update if boxset is not in Kodi or boxset['Etag'] is different
                updatelist.append(itemid)
                embyboxsets.append(boxset)

        log.info("Boxsets to update: %s" % updatelist)
        self.total = len(updatelist)

        if pdialog:
            pdialog.update(heading="Processing Boxsets / %s items" % total)

        self.count = 0
        for boxset in embyboxsets:
            # Process individual boxset
            if self.should_stop():
                return False
            self.title = boxset['Name']
            self.update_pdialog()
            self.add_updateBoxset(boxset)
            self.count += 1

        ##### PROCESS DELETES #####

        for kodimovie in all_kodimovies:
            if kodimovie not in all_embymoviesIds:
                self.remove(kodimovie)
        else:
            log.info("Movies compare finished.")

        for boxset in all_kodisets:
            if boxset not in all_embyboxsetsIds:
                self.remove(boxset)
        else:
            log.info("Boxsets compare finished.")

        return True


    def added(self, items, total=None, view=None):

        for item in super(Movies, self).added(items, total):
            if self.add_update(item, view):
                self.content_pop()

    @catch_except()
    def add_update(self, item, view=None):
        # Process single movie
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            movieid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("movieid: %s fileid: %s pathid: %s" % (movieid, fileid, pathid))
        
        except TypeError:
            update_item = False
            log.debug("movieid: %s not found." % itemid)
            # movieid
            kodicursor.execute("select coalesce(max(idMovie),0) from movie")
            movieid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM movie WHERE idMovie = ?"
            kodicursor.execute(query, (movieid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                log.info("movieid: %s missing from Kodi, repairing the entry." % movieid)

        if not view:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            log.debug("View tag found: %s" % viewtag)
        else:
            viewtag = view['name']
            viewid = view['id']

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
        genres = item['Genres']
        title = item['Name']
        plot = API.get_overview()
        shortplot = item.get('ShortOverview')
        tagline = API.get_tagline()
        votecount = item.get('VoteCount')
        rating = item.get('CommunityRating')
        year = item.get('ProductionYear')
        imdb = API.get_provider('Imdb')
        sorttitle = item['SortName']
        runtime = API.get_runtime()
        mpaa = API.get_mpaa()
        genre = " / ".join(genres)
        country = API.get_country()
        studios = API.get_studios()
        try:
            studio = studios[0]
        except IndexError:
            studio = None

        if item.get('LocalTrailerCount'):
            # There's a local trailer
            url = (
                "{server}/emby/Users/{UserId}/Items/%s/LocalTrailers?format=json"
                % itemid
            )
            result = self.do_url(url)
            try:
                trailer = "plugin://plugin.video.emby/trailer/?id=%s&mode=play" % result[0]['Id']
            except IndexError:
                log.info("Failed to process local trailer.")
                trailer = None
        else:
            # Try to get the youtube trailer
            try:
                trailer = item['RemoteTrailers'][0]['Url']
            except (KeyError, IndexError):
                trailer = None
            else:    
                try:
                    trailerId = trailer.rsplit('=', 1)[1]
                except IndexError:
                    log.info("Failed to process trailer: %s" % trailer)
                    trailer = None
                else:
                    trailer = "plugin://plugin.video.youtube/play/?video_id=%s" % trailerId

        
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
            path = "plugin://plugin.video.emby.movies/"
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': movieid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE MOVIE #####
        if update_item:
            log.info("UPDATE movie itemid: %s - Title: %s" % (itemid, title))

            # Update the movie entry
            if self.kodi_version > 16:
                query = ' '.join((
                    
                    "UPDATE movie",
                    "SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?,",
                        "c07 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?,",
                        "c16 = ?, c18 = ?, c19 = ?, c21 = ?, premiered = ?",
                    "WHERE idMovie = ?"
                ))
                kodicursor.execute(query, (title, plot, shortplot, tagline, votecount, rating,
                    writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio,
                    trailer, country, year, movieid))
            else:
                query = ' '.join((
                    
                    "UPDATE movie",
                    "SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?,",
                        "c07 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?,",
                        "c16 = ?, c18 = ?, c19 = ?, c21 = ?",
                    "WHERE idMovie = ?"
                ))
                kodicursor.execute(query, (title, plot, shortplot, tagline, votecount, rating,
                    writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio,
                    trailer, country, movieid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE MOVIE #####
        else:
            log.info("ADD movie itemid: %s - Title: %s" % (itemid, title))
            
            # Add path
            pathid = self.kodi_db.addPath(path)
            # Add the file
            fileid = self.kodi_db.addFile(filename, pathid)
            
            # Create the movie entry
            if self.kodi_version > 16:
                query = (
                    '''
                    INSERT INTO movie(
                        idMovie, idFile, c00, c01, c02, c03, c04, c05, c06, c07, 
                        c09, c10, c11, c12, c14, c15, c16, c18, c19, c21, premiered)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (movieid, fileid, title, plot, shortplot, tagline,
                    votecount, rating, writer, year, imdb, sorttitle, runtime, mpaa, genre,
                    director, title, studio, trailer, country, year))
            else:
                query = (
                    '''
                    INSERT INTO movie(
                        idMovie, idFile, c00, c01, c02, c03, c04, c05, c06, c07, 
                        c09, c10, c11, c12, c14, c15, c16, c18, c19, c21)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (movieid, fileid, title, plot, shortplot, tagline,
                    votecount, rating, writer, year, imdb, sorttitle, runtime, mpaa, genre,
                    director, title, studio, trailer, country))

            # Create the reference in emby table
            emby_db.addReference(itemid, movieid, "Movie", "movie", fileid, pathid, None, checksum, viewid)

        # Update the path
        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        kodicursor.execute(query, (path, "movies", "metadata.local", 1, pathid))

        # Update the file
        query = ' '.join((

            "UPDATE files",
            "SET idPath = ?, strFilename = ?, dateAdded = ?",
            "WHERE idFile = ?"
        ))
        kodicursor.execute(query, (pathid, filename, dateadded, fileid))
        
        # Process countries
        if 'ProductionLocations' in item:
            self.kodi_db.addCountries(movieid, item['ProductionLocations'], "movie")
        # Process cast
        people = artwork.get_people_artwork(item['People'])
        self.kodi_db.addPeople(movieid, people, "movie")
        # Process genres
        self.kodi_db.addGenres(movieid, genres, "movie")
        # Process artwork
        artwork.add_artwork(artwork.get_all_artwork(item), movieid, "movie", kodicursor)
        # Process stream details
        streams = API.get_media_streams()
        self.kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        self.kodi_db.addStudios(movieid, studios, "movie")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite movies")
        log.info("Applied tags: %s", tags)
        self.kodi_db.addTags(movieid, tags, "movie")
        # Process playstates
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

        return True

    def add_updateBoxset(self, boxset):

        emby = self.emby
        emby_db = self.emby_db
        artwork = self.artwork

        boxsetid = boxset['Id']
        title = boxset['Name']
        checksum = boxset['Etag']
        emby_dbitem = emby_db.getItem_byId(boxsetid)
        try:
            setid = emby_dbitem[0]

        except TypeError:
            setid = self.kodi_db.createBoxset(title)

        # Process artwork
        artwork.add_artwork(artwork.get_all_artwork(boxset), setid, "set", self.kodicursor)
        
        # Process movies inside boxset
        current_movies = emby_db.getItemId_byParentId(setid, "movie")
        process = []
        try:
            # Try to convert tuple to dictionary
            current = dict(current_movies)
        except ValueError:
            current = {}

        # Sort current titles
        for current_movie in current:
            process.append(current_movie)

        # New list to compare
        for movie in emby.getMovies_byBoxset(boxsetid)['Items']:

            itemid = movie['Id']

            if not current.get(itemid):
                # Assign boxset to movie
                emby_dbitem = emby_db.getItem_byId(itemid)
                try:
                    movieid = emby_dbitem[0]
                except TypeError:
                    log.info("Failed to add: %s to boxset." % movie['Name'])
                    continue

                log.info("New addition to boxset %s: %s" % (title, movie['Name']))
                self.kodi_db.assignBoxset(setid, movieid)
                # Update emby reference
                emby_db.updateParentId(itemid, setid)
            else:
                # Remove from process, because the item still belongs
                process.remove(itemid)

        # Process removals from boxset
        for movie in process:
            movieid = current[movie]
            log.info("Remove from boxset %s: %s" % (title, movieid))
            self.kodi_db.removefromBoxset(movieid)
            # Update emby reference
            emby_db.updateParentId(movie, None)

        # Update the reference in the emby table
        emby_db.addReference(boxsetid, setid, "BoxSet", mediatype="set", checksum=checksum)

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

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            movieid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            log.info("Update playstate for movie: %s fileid: %s" % (item['Name'], fileid))
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            self.kodi_db.addTag(movieid, "Favorite movies", "movie")
        else:
            self.kodi_db.removeTag(movieid, "Favorite movies", "movie")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjust_resume(userdata['Resume'])
        total = round(float(runtime), 6)

        log.debug("%s New resume point: %s" % (itemid, resume))

        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove movieid, fileid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            mediatype = emby_dbitem[4]
            log.info("Removing %sid: %s fileid: %s" % (mediatype, kodiid, fileid))
        except TypeError:
            return

        # Remove the emby reference
        emby_db.removeItem(itemid)
        # Remove artwork
        artwork.delete_artwork(kodiid, mediatype, kodicursor)

        if mediatype == "movie":
            # Delete kodi movie and file
            kodicursor.execute("DELETE FROM movie WHERE idMovie = ?", (kodiid,))
            kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))

        elif mediatype == "set":
            # Delete kodi boxset
            boxset_movies = emby_db.getItem_byParentId(kodiid, "movie")
            for movie in boxset_movies:
                embyid = movie[0]
                movieid = movie[1]
                self.kodi_db.removefromBoxset(movieid)
                # Update emby reference
                emby_db.updateParentId(embyid, None)

            kodicursor.execute("DELETE FROM sets WHERE idSet = ?", (kodiid,))

        log.info("Deleted %s %s from kodi database" % (mediatype, itemid))
