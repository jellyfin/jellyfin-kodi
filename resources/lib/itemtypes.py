# -*- coding: utf-8 -*-

##################################################################################################

import logging
import urllib
from ntpath import dirname
from datetime import datetime

import xbmc
import xbmcgui
import xbmcvfs

import api
import artwork
import clientinfo
import downloadutils
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver
import musicutils
from utils import window, settings, language as lang, kodiSQL

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Items(object):


    def __init__(self, embycursor, kodicursor):

        self.embycursor = embycursor
        self.kodicursor = kodicursor

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils()

        self.kodiversion = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        self.directpath = settings('useDirectPaths') == "1"
        self.music_enabled = settings('enableMusic') == "true"
        self.contentmsg = settings('newContent') == "true"
        self.newvideo_time = int(settings('newvideotime'))*1000
        self.newmusic_time = int(settings('newmusictime'))*1000

        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.emby_db = embydb.Embydb_Functions(embycursor)
        self.kodi_db = kodidb.Kodidb_Functions(kodicursor)


    def itemsbyId(self, items, process, pdialog=None):
        # Process items by itemid. Process can be added, update, userdata, remove
        emby = self.emby
        embycursor = self.embycursor
        kodicursor = self.kodicursor
        music_enabled = self.music_enabled
        
        itemtypes = {

            'Movie': Movies,
            'BoxSet': Movies,
            'Series': TVShows,
            'Season': TVShows,
            'Episode': TVShows,
            'MusicAlbum': Music,
            'MusicArtist': Music,
            'AlbumArtist': Music,
            'Audio': Music
        }

        update_videolibrary = False
        total = 0
        for item in items:
            total += len(items[item])

        if total == 0:
            return False

        log.info("Processing %s: %s" % (process, items))
        if pdialog:
            pdialog.update(heading="Processing %s: %s items" % (process, total))

        count = 0
        for itemtype in items:

            # Safety check
            if not itemtypes.get(itemtype):
                # We don't process this type of item
                continue

            itemlist = items[itemtype]
            if not itemlist:
                # The list to process is empty
                continue

            musicconn = None

            if itemtype in ('MusicAlbum', 'MusicArtist', 'AlbumArtist', 'Audio'):
                if music_enabled:
                    musicconn = kodiSQL('music')
                    musiccursor = musicconn.cursor()
                    items_process = itemtypes[itemtype](embycursor, musiccursor)
                else:
                    # Music is not enabled, do not proceed with itemtype
                    continue
            else:
                update_videolibrary = True
                items_process = itemtypes[itemtype](embycursor, kodicursor)

            if itemtype == "Movie":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "BoxSet":
                actions = {
                    'added': items_process.added_boxset,
                    'update': items_process.add_updateBoxset,
                    'remove': items_process.remove
                }
            elif itemtype == "MusicVideo":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "Series":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "Season":
                actions = {
                    'added': items_process.added_season,
                    'update': items_process.add_updateSeason,
                    'remove': items_process.remove
                }
            elif itemtype == "Episode":
                actions = {
                    'added': items_process.added_episode,
                    'update': items_process.add_updateEpisode,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype == "MusicAlbum":
                actions = {
                    'added': items_process.added_album,
                    'update': items_process.add_updateAlbum,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            elif itemtype in ("MusicArtist", "AlbumArtist"):
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_updateArtist,
                    'remove': items_process.remove
                }
            elif itemtype == "Audio":
                actions = {
                    'added': items_process.added_song,
                    'update': items_process.add_updateSong,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            else:
                log.info("Unsupported itemtype: %s." % itemtype)
                actions = {}

            if actions.get(process):

                if process == "remove":
                    for item in itemlist:
                        actions[process](item)

                elif process == "added":
                    actions[process](itemlist, pdialog)
            
                else:
                    processItems = emby.getFullItems(itemlist)
                    for item in processItems:

                        title = item['Name']

                        if itemtype == "Episode":
                            title = "%s - %s" % (item.get('SeriesName', "Unknown"), title)

                        if pdialog:
                            percentage = int((float(count) / float(total))*100)
                            pdialog.update(percentage, message=title)
                            count += 1

                        actions[process](item)


            if musicconn is not None:
                # close connection for special types
                log.info("Updating music database.")
                musicconn.commit()
                musiccursor.close()

        return (True, update_videolibrary)

    def pathValidation(self, path):
        # Verify if direct path is accessible or not
        if window('emby_pathverified') != "true" and not xbmcvfs.exists(path):
            resp = xbmcgui.Dialog().yesno(
                        heading=lang(29999),
                        line1="%s %s. %s" % (lang(33047), path, lang(33048)))
            if resp:
                window('emby_shouldStop', value="true")
                return False

        return True

    def contentPop(self, name, time=5000):
        
        if time: 
            # It's possible for the time to be 0. It should be considered disabled in this case.
            xbmcgui.Dialog().notification(
                    heading=lang(29999),
                    message="%s %s" % (lang(33049), name),
                    icon="special://home/addons/plugin.video.emby/icon.png",
                    time=time,
                    sound=False)


class Movies(Items):

    
    def __init__(self, embycursor, kodicursor):
        Items.__init__(self, embycursor, kodicursor)

    def added(self, items, pdialog):

        total = len(items)
        count = 0
        for movie in items:
                
            title = movie['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(movie)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newvideo_time)

    def added_boxset(self, items, pdialog):

        total = len(items)
        count = 0
        for boxset in items:

            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=boxset['Name'])
                count += 1
            self.add_updateBoxset(boxset)


    def add_update(self, item, viewtag=None, viewid=None):
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

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            log.debug("View tag found: %s" % viewtag)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        people = API.getPeople()
        writer = " / ".join(people['Writer'])
        director = " / ".join(people['Director'])
        genres = item['Genres']
        title = item['Name']
        plot = API.getOverview()
        shortplot = item.get('ShortOverview')
        tagline = API.getTagline()
        votecount = item.get('VoteCount')
        rating = item.get('CommunityRating')
        year = item.get('ProductionYear')
        imdb = API.getProvider('Imdb')
        sorttitle = item['SortName']
        runtime = API.getRuntime()
        mpaa = API.getMpaa()
        genre = " / ".join(genres)
        country = API.getCountry()
        studios = API.getStudios()
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
            result = self.doUtils.downloadUrl(url)
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
        playurl = API.getFilePath()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if not self.pathValidation(playurl):
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
            query = ' '.join((
                
                "UPDATE movie",
                "SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?,",
                    "c07 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?,",
                    "c16 = ?, c18 = ?, c19 = ?, c21 = ?",
                "WHERE idMovie = ?"
            ))
            kodicursor.execute(query, (title, plot, shortplot, tagline, votecount, rating, writer,
                year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio, trailer,
                country, movieid))

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
            query = (
                '''
                INSERT INTO movie(
                    idMovie, idFile, c00, c01, c02, c03, c04, c05, c06, c07, 
                    c09, c10, c11, c12, c14, c15, c16, c18, c19, c21)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (movieid, fileid, title, plot, shortplot, tagline, votecount,
                rating, writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title,
                studio, trailer, country))

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
        self.kodi_db.addCountries(movieid, item['ProductionLocations'], "movie")
        # Process cast
        people = artwork.getPeopleArtwork(item['People'])
        self.kodi_db.addPeople(movieid, people, "movie")
        # Process genres
        self.kodi_db.addGenres(movieid, genres, "movie")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), movieid, "movie", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        self.kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        self.kodi_db.addStudios(movieid, studios, "movie")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite movies")
        self.kodi_db.addTags(movieid, tags, "movie")
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

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
        artwork.addArtwork(artwork.getAllArtwork(boxset), setid, "set", self.kodicursor)
        
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
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()

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
        resume = API.adjustResume(userdata['Resume'])
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
        artwork.deleteArtwork(kodiid, mediatype, kodicursor)

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

class MusicVideos(Items):

    
    def __init__(self, embycursor, kodicursor):
        Items.__init__(self, embycursor, kodicursor)

    def added(self, items, pdialog):

        total = len(items)
        count = 0
        for mvideo in items:

            title = mvideo['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(mvideo)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newvideo_time)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single music video
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
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("mvideoid: %s fileid: %s pathid: %s" % (mvideoid, fileid, pathid))
        
        except TypeError:
            update_item = False
            log.debug("mvideoid: %s not found." % itemid)
            # mvideoid
            kodicursor.execute("select coalesce(max(idMVideo),0) from musicvideo")
            mvideoid = kodicursor.fetchone()[0] + 1

        else:
            # Verification the item is still in Kodi
            query = "SELECT * FROM musicvideo WHERE idMVideo = ?"
            kodicursor.execute(query, (mvideoid,))
            try:
                kodicursor.fetchone()[0]
            except TypeError:
                # item is not found, let's recreate it.
                update_item = False
                log.info("mvideoid: %s missing from Kodi, repairing the entry." % mvideoid)

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            log.debug("View tag found: %s" % viewtag)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        runtime = API.getRuntime()
        plot = API.getOverview()
        title = item['Name']
        year = item.get('ProductionYear')
        genres = item['Genres']
        genre = " / ".join(genres)
        studios = API.getStudios()
        studio = " / ".join(studios)
        artist = " / ".join(item.get('Artists'))
        album = item.get('Album')
        track = item.get('Track')
        people = API.getPeople()
        director = " / ".join(people['Director'])

        
        ##### GET THE FILE AND PATH #####
        playurl = API.getFilePath()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if not self.pathValidation(playurl):
                return False
            
            path = playurl.replace(filename, "")
            window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.emby.musicvideos/"
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': mvideoid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE MUSIC VIDEO #####
        if update_item:
            log.info("UPDATE mvideo itemid: %s - Title: %s" % (itemid, title))
            
            # Update path
            query = "UPDATE path SET strPath = ? WHERE idPath = ?"
            kodicursor.execute(query, (path, pathid))

            # Update the filename
            query = "UPDATE files SET strFilename = ?, dateAdded = ? WHERE idFile = ?"
            kodicursor.execute(query, (filename, dateadded, fileid))

            # Update the music video entry
            query = ' '.join((
                
                "UPDATE musicvideo",
                "SET c00 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c08 = ?, c09 = ?, c10 = ?,",
                    "c11 = ?, c12 = ?"
                "WHERE idMVideo = ?"
            ))
            kodicursor.execute(query, (title, runtime, director, studio, year, plot, album,
                artist, genre, track, mvideoid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE MUSIC VIDEO #####
        else:
            log.info("ADD mvideo itemid: %s - Title: %s" % (itemid, title))
            
            # Add path
            query = ' '.join((

                "SELECT idPath",
                "FROM path",
                "WHERE strPath = ?"
            ))
            kodicursor.execute(query, (path,))
            try:
                pathid = kodicursor.fetchone()[0]
            except TypeError:
                kodicursor.execute("select coalesce(max(idPath),0) from path")
                pathid = kodicursor.fetchone()[0] + 1
                query = (
                    '''
                    INSERT OR REPLACE INTO path(
                        idPath, strPath, strContent, strScraper, noUpdate)

                    VALUES (?, ?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (pathid, path, "musicvideos", "metadata.local", 1))

            # Add the file
            kodicursor.execute("select coalesce(max(idFile),0) from files")
            fileid = kodicursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO files(
                    idFile, idPath, strFilename, dateAdded)

                VALUES (?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (fileid, pathid, filename, dateadded))
            
            # Create the musicvideo entry
            query = (
                '''
                INSERT INTO musicvideo(
                    idMVideo, idFile, c00, c04, c05, c06, c07, c08, c09, c10, c11, c12)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (mvideoid, fileid, title, runtime, director, studio,
                year, plot, album, artist, genre, track))

            # Create the reference in emby table
            emby_db.addReference(itemid, mvideoid, "MusicVideo", "musicvideo", fileid, pathid,
                checksum=checksum, mediafolderid=viewid)

        
        # Process cast
        people = item['People']
        artists = item['ArtistItems']
        for artist in artists:
            artist['Type'] = "Artist"
        people.extend(artists)
        people = artwork.getPeopleArtwork(people)
        self.kodi_db.addPeople(mvideoid, people, "musicvideo")
        # Process genres
        self.kodi_db.addGenres(mvideoid, genres, "musicvideo")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), mvideoid, "musicvideo", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        self.kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        self.kodi_db.addStudios(mvideoid, studios, "musicvideo")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite musicvideos")
        self.kodi_db.addTags(mvideoid, tags, "musicvideo")
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        API = api.API(item)
        
        # Get emby information
        itemid = item['Id']
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            log.info(
                "Update playstate for musicvideo: %s fileid: %s"
                % (item['Name'], fileid))
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            self.kodi_db.addTag(mvideoid, "Favorite musicvideos", "musicvideo")
        else:
            self.kodi_db.removeTag(mvideoid, "Favorite musicvideos", "musicvideo")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)

        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove mvideoid, fileid, pathid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            mvideoid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("Removing mvideoid: %s fileid: %s" % (mvideoid, fileid, pathid))
        except TypeError:
            return

        # Remove artwork
        query = ' '.join((

            "SELECT url, type",
            "FROM art",
            "WHERE media_id = ?",
            "AND media_type = 'musicvideo'"
        ))
        kodicursor.execute(query, (mvideoid,))
        for row in kodicursor.fetchall():
            
            url = row[0]
            imagetype = row[1]
            if imagetype in ("poster", "fanart"):
                artwork.deleteCachedArtwork(url)

        kodicursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (mvideoid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        if self.directpath:
            kodicursor.execute("DELETE FROM path WHERE idPath = ?", (pathid,))
        self.embycursor.execute("DELETE FROM emby WHERE emby_id = ?", (itemid,))

        log.info("Deleted musicvideo %s from kodi database" % itemid)

class TVShows(Items):


    def __init__(self, embycursor, kodicursor):
        Items.__init__(self, embycursor, kodicursor)

    def added(self, items, pdialog):
        
        total = len(items)
        count = 0
        for tvshow in items:

            title = tvshow['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(tvshow)
            # Add episodes
            all_episodes = self.emby.getEpisodesbyShow(tvshow['Id'])
            self.added_episode(all_episodes['Items'], pdialog)

    def added_season(self, items, pdialog):
        
        total = len(items)
        count = 0
        for season in items:

            title = "%s - %s" % (season.get('SeriesName', "Unknown"), season['Name'])
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateSeason(season)
            # Add episodes
            all_episodes = self.emby.getEpisodesbySeason(season['Id'])
            self.added_episode(all_episodes['Items'], pdialog)

    def added_episode(self, items, pdialog):
        
        total = len(items)
        count = 0
        for episode in items:
            title = "%s - %s" % (episode.get('SeriesName', "Unknown"), episode['Name'])
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateEpisode(episode)
            if not pdialog and self.contentmsg:
                self.contentPop(title, self.newvideo_time)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single tvshow
        kodicursor = self.kodicursor
        emby = self.emby
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        if settings('syncEmptyShows') == "false" and not item.get('RecursiveItemCount'):
            log.info("Skipping empty show: %s" % item['Name'])
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
            log.info("showid: %s pathid: %s" % (showid, pathid))
        
        except TypeError:
            update_item = False
            log.debug("showid: %s not found." % itemid)
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
                log.info("showid: %s missing from Kodi, repairing the entry." % showid)
                # Force re-add episodes after the show is re-created.
                force_episodes = True


        if viewtag is None or viewid is None:
            # Get view tag from emby
            viewtag, viewid, mediatype = emby.getView_embyId(itemid)
            log.debug("View tag found: %s" % viewtag)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        genres = item['Genres']
        title = item['Name']
        plot = API.getOverview()
        rating = item.get('CommunityRating')
        premieredate = API.getPremiereDate()
        tvdb = API.getProvider('Tvdb')
        sorttitle = item['SortName']
        mpaa = API.getMpaa()
        genre = " / ".join(genres)
        studios = API.getStudios()
        studio = " / ".join(studios)

        
        ##### GET THE FILE AND PATH #####
        playurl = API.getFilePath()

        if self.directpath:
            # Direct paths is set the Kodi way
            if "\\" in playurl:
                # Local path
                path = "%s\\" % playurl
                toplevelpath = "%s\\" % dirname(dirname(path))
            else:
                # Network path
                path = "%s/" % playurl
                toplevelpath = "%s/" % dirname(dirname(path))

            if not self.pathValidation(playurl):
                return False

            window('emby_pathverified', value="true")
        else:
            # Set plugin path
            toplevelpath = "plugin://plugin.video.emby.tvshows/"
            path = "%s%s/" % (toplevelpath, itemid)


        ##### UPDATE THE TVSHOW #####
        if update_item:
            log.info("UPDATE tvshow itemid: %s - Title: %s" % (itemid, title))

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
            log.info("ADD tvshow itemid: %s - Title: %s" % (itemid, title))
            
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
                INSERT INTO tvshow(
                    idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14, c15) 

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
        people = artwork.getPeopleArtwork(item['People'])
        self.kodi_db.addPeople(showid, people, "tvshow")
        # Process genres
        self.kodi_db.addGenres(showid, genres, "tvshow")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), showid, "tvshow", kodicursor)
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
            artwork.addArtwork(artwork.getAllArtwork(item), seasonid, "season", kodicursor)

        if force_episodes:
            # We needed to recreate the show entry. Re-add episodes now.
            log.info("Repairing episodes for showid: %s %s" % (showid, title))
            all_episodes = emby.getEpisodesbyShow(itemid)
            self.added_episode(all_episodes['Items'], None)

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
        
        seasonid = self.kodi_db.addSeason(showid, seasonnum)
        
        if item['LocationType'] != "Virtual":
            # Create the reference in emby table
            emby_db.addReference(item['Id'], seasonid, "Season", "season", parentid=showid)

        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), seasonid, "season", kodicursor)

    def add_updateEpisode(self, item):
        # Process single episode
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
            episodeid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            log.info("episodeid: %s fileid: %s pathid: %s" % (episodeid, fileid, pathid))
        
        except TypeError:
            update_item = False
            log.info("episodeid: %s not found." % itemid)
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
                log.info("episodeid: %s missing from Kodi, repairing the entry." % episodeid)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        people = API.getPeople()
        writer = " / ".join(people['Writer'])
        director = " / ".join(people['Director'])
        title = item['Name']
        plot = API.getOverview()
        rating = item.get('CommunityRating')
        runtime = API.getRuntime()
        premieredate = API.getPremiereDate()

        # episode details
        try:
            seriesId = item['SeriesId']
        except KeyError:
            # Missing seriesId, skip
            log.error("Skipping: %s. SeriesId is missing." % itemid)
            return False
            
        season = item.get('ParentIndexNumber')
        episode = item.get('IndexNumber', -1)
       
        if season is None:
            if item.get('AbsoluteEpisodeNumber'):
                # Anime scenario
                season = 1
                episode = item['AbsoluteEpisodeNumber']
            else:
                season = -1

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
                log.error("Skipping: %s. Unable to add series: %s." % (itemid, seriesId))
                return False

        seasonid = self.kodi_db.addSeason(showid, season)

        
        ##### GET THE FILE AND PATH #####
        playurl = API.getFilePath()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if not self.pathValidation(playurl):
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
            log.info("UPDATE episode itemid: %s - Title: %s" % (itemid, title))

            # Update the movie entry
            if self.kodiversion in (16, 17):
                # Kodi Jarvis, Krypton
                query = ' '.join((
                
                    "UPDATE episode",
                    "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                        "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idSeason = ?",
                    "WHERE idEpisode = ?"
                ))
                kodicursor.execute(query, (title, plot, rating, writer, premieredate,
                    runtime, director, season, episode, title, airsBeforeSeason,
                    airsBeforeEpisode, seasonid, episodeid))
            else:
                query = ' '.join((
                    
                    "UPDATE episode",
                    "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                        "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?",
                    "WHERE idEpisode = ?"
                ))
                kodicursor.execute(query, (title, plot, rating, writer, premieredate,
                    runtime, director, season, episode, title, airsBeforeSeason,
                    airsBeforeEpisode, episodeid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
            # Update parentid reference
            emby_db.updateParentId(itemid, seasonid)
        
        ##### OR ADD THE EPISODE #####
        else:
            log.info("ADD episode itemid: %s - Title: %s" % (itemid, title))
            
            # Add path
            pathid = self.kodi_db.addPath(path)
            # Add the file
            fileid = self.kodi_db.addFile(filename, pathid)
            
            # Create the episode entry
            if self.kodiversion in (16, 17):
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
                    premieredate, runtime, director, season, episode, title, showid,
                    airsBeforeSeason, airsBeforeEpisode, seasonid))
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
                    premieredate, runtime, director, season, episode, title, showid,
                    airsBeforeSeason, airsBeforeEpisode))

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
        people = artwork.getPeopleArtwork(item['People'])
        self.kodi_db.addPeople(episodeid, people, "episode")
        # Process artwork
        artworks = artwork.getAllArtwork(item)
        artwork.addOrUpdateArt(artworks['Primary'], episodeid, "episode", "thumb", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        self.kodi_db.addStreams(fileid, streams, runtime)
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        if not self.directpath and resume:
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

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        API = api.API(item)
        
        # Get emby information
        itemid = item['Id']
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()
        dateadded = API.getDateCreated()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            mediatype = emby_dbitem[4]
            log.info(
                "Update playstate for %s: %s fileid: %s"
                % (mediatype, item['Name'], fileid))
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
            resume = API.adjustResume(userdata['Resume'])
            total = round(float(runtime), 6)

            log.debug("%s New resume point: %s" % (itemid, resume))

            self.kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
            if not self.directpath and not resume:
                # Make sure there's no other bookmarks created by widget.
                filename = self.kodi_db.getFile(fileid)
                self.kodi_db.removeFile("plugin://plugin.video.emby.tvshows/", filename)

            if not self.directpath and resume:
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
        embycursor = self.embycursor
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            parentid = emby_dbitem[3]
            mediatype = emby_dbitem[4]
            log.info("Removing %s kodiid: %s fileid: %s" % (mediatype, kodiid, fileid))
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

        log.info("Deleted %s: %s from kodi database" % (mediatype, itemid))

    def removeShow(self, kodiid):
        
        kodicursor = self.kodicursor
        self.artwork.deleteArtwork(kodiid, "tvshow", kodicursor)
        kodicursor.execute("DELETE FROM tvshow WHERE idShow = ?", (kodiid,))
        log.debug("Removed tvshow: %s." % kodiid)

    def removeSeason(self, kodiid):
        
        kodicursor = self.kodicursor

        self.artwork.deleteArtwork(kodiid, "season", kodicursor)
        kodicursor.execute("DELETE FROM seasons WHERE idSeason = ?", (kodiid,))
        log.debug("Removed season: %s." % kodiid)

    def removeEpisode(self, kodiid, fileid):

        kodicursor = self.kodicursor

        self.artwork.deleteArtwork(kodiid, "episode", kodicursor)
        kodicursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodiid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        log.debug("Removed episode: %s." % kodiid)

class Music(Items):


    def __init__(self, embycursor, musiccursor):
        
        Items.__init__(self, embycursor, musiccursor)

        self.directstream = settings('streamMusic') == "true"
        self.enableimportsongrating = settings('enableImportSongRating') == "true"
        self.enableexportsongrating = settings('enableExportSongRating') == "true"
        self.enableupdatesongrating = settings('enableUpdateSongRating') == "true"
        self.userid = window('emby_currUser')
        self.server = window('emby_server%s' % self.userid)

    def added(self, items, pdialog):
        
        total = len(items)
        count = 0
        for artist in items:

            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=artist['Name'])
                count += 1
            self.add_updateArtist(artist)
            # Add albums
            all_albums = self.emby.getAlbumsbyArtist(artist['Id'])
            self.added_album(all_albums['Items'], pdialog)

    def added_album(self, items, pdialog):
        
        total = len(items)
        count = 0
        for album in items:

            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=album['Name'])
                count += 1
            self.add_updateAlbum(album)
            # Add songs
            all_songs = self.emby.getSongsbyAlbum(album['Id'])
            self.added_song(all_songs['Items'], pdialog)

    def added_song(self, items, pdialog):
        
        total = len(items)
        count = 0
        for song in items:

            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=song['Name'])
                count += 1
            self.add_updateSong(song)
            if not pdialog and self.contentmsg:
                self.contentPop(song['Name'], self.newmusic_time)

    def add_updateArtist(self, item, artisttype="MusicArtist"):
        # Process a single artist
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            artistid = emby_dbitem[0]
        except TypeError:
            update_item = False
            log.debug("artistid: %s not found." % itemid)

        ##### The artist details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API.getDateCreated()
        checksum = API.getChecksum()

        name = item['Name']
        musicBrainzId = API.getProvider('MusicBrainzArtist')
        genres = " / ".join(item.get('Genres'))
        bio = API.getOverview()

        # Associate artwork
        artworks = artwork.getAllArtwork(item, parentInfo=True)
        thumb = artworks['Primary']
        backdrops = artworks['Backdrop'] # List

        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb
        if backdrops:
            fanart = "<fanart>%s</fanart>" % backdrops[0]
        else:
            fanart = ""


        ##### UPDATE THE ARTIST #####
        if update_item:
            log.info("UPDATE artist itemid: %s - Name: %s" % (itemid, name))
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE ARTIST #####
        else:
            log.info("ADD artist itemid: %s - Name: %s" % (itemid, name))
            # safety checks: It looks like Emby supports the same artist multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the artist entries.
            artistid = self.kodi_db.addArtist(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, artistid, artisttype, "artist", checksum=checksum)
            

        # Process the artist
        if self.kodiversion in (16, 17):
            query = ' '.join((

                "UPDATE artist",
                "SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?,",
                    "lastScraped = ?",
                "WHERE idArtist = ?"
            ))
            kodicursor.execute(query, (genres, bio, thumb, fanart, lastScraped, artistid))
        else:
            query = ' '.join((

                "UPDATE artist",
                "SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?,",
                    "lastScraped = ?, dateAdded = ?",
                "WHERE idArtist = ?"
            ))
            kodicursor.execute(query, (genres, bio, thumb, fanart, lastScraped,
                    dateadded, artistid))


        # Update artwork
        artwork.addArtwork(artworks, artistid, "artist", kodicursor)

    def add_updateAlbum(self, item):
        # Process a single artist
        emby = self.emby
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            albumid = emby_dbitem[0]
        except TypeError:
            update_item = False
            log.debug("albumid: %s not found." % itemid)

        ##### The album details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        checksum = API.getChecksum()

        name = item['Name']
        musicBrainzId = API.getProvider('MusicBrainzAlbum')
        year = item.get('ProductionYear')
        genres = item.get('Genres')
        genre = " / ".join(genres)
        bio = API.getOverview()
        rating = userdata['UserRating']
        artists = item['AlbumArtists']
        if not artists:
            artists = item['ArtistItems']
        artistname = []
        for artist in artists:
            artistname.append(artist['Name'])
        artistname = " / ".join(artistname)

        # Associate artwork
        artworks = artwork.getAllArtwork(item, parentInfo=True)
        thumb = artworks['Primary']
        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb

        ##### UPDATE THE ALBUM #####
        if update_item:
            log.info("UPDATE album itemid: %s - Name: %s" % (itemid, name))
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE ALBUM #####
        else:
            log.info("ADD album itemid: %s - Name: %s" % (itemid, name))
            # safety checks: It looks like Emby supports the same artist multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the artist entries.
            albumid = self.kodi_db.addAlbum(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, albumid, "MusicAlbum", "album", checksum=checksum)


        # Process the album info
        if self.kodiversion == 17:
            # Kodi Krypton
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iUserrating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                "album", albumid))
        elif self.kodiversion == 16:
            # Kodi Jarvis
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                "album", albumid))
        elif self.kodiversion == 15:
            # Kodi Isengard
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, dateAdded = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                dateadded, "album", albumid))
        else:
            # Kodi Helix
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, dateAdded = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                dateadded, albumid))

        # Associate the parentid for emby reference
        parentId = item.get('ParentId')
        if parentId is not None:
            emby_dbartist = emby_db.getItem_byId(parentId)
            try:
                artistid = emby_dbartist[0]
            except TypeError:
                # Artist does not exist in emby database.
                artist = emby.getItem(parentId)
                # Item may not be an artist, verification necessary.
                if artist['Type'] == "MusicArtist":
                    # Update with the parentId, for remove reference
                    emby_db.addReference(parentId, parentId, "MusicArtist", "artist")
                    emby_db.updateParentId(itemid, parentId)
            else:
                # Update emby reference with the artistid
                emby_db.updateParentId(itemid, artistid)

        # Assign main artists to album
        for artist in artists:
            artistname = artist['Name']
            artistId = artist['Id']
            emby_dbartist = emby_db.getItem_byId(artistId)
            try:
                artistid = emby_dbartist[0]
            except TypeError:
                # Artist does not exist in emby database, create the reference
                artist = emby.getItem(artistId)
                self.add_updateArtist(artist, artisttype="AlbumArtist")
                emby_dbartist = emby_db.getItem_byId(artistId)
                artistid = emby_dbartist[0]
            else:
                # Best take this name over anything else.
                query = "UPDATE artist SET strArtist = ? WHERE idArtist = ?"
                kodicursor.execute(query, (artistname, artistid,))

            # Add artist to album
            query = (
                '''
                INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist)

                VALUES (?, ?, ?)
                '''
            )
            kodicursor.execute(query, (artistid, albumid, artistname))
            # Update discography
            query = (
                '''
                INSERT OR REPLACE INTO discography(idArtist, strAlbum, strYear)

                VALUES (?, ?, ?)
                '''
            )
            kodicursor.execute(query, (artistid, name, year))
            # Update emby reference with parentid
            emby_db.updateParentId(artistId, albumid)

        # Add genres
        self.kodi_db.addMusicGenres(albumid, genres, "album")
        # Update artwork
        artwork.addArtwork(artworks, albumid, "album", kodicursor)

    def add_updateSong(self, item):
        # Process single song
        kodicursor = self.kodicursor
        emby = self.emby
        emby_db = self.emby_db
        artwork = self.artwork
        API = api.API(item)

        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            songid = emby_dbitem[0]
            pathid = emby_dbitem[2]
            albumid = emby_dbitem[3]
        except TypeError:
            update_item = False
            log.debug("songid: %s not found." % itemid)
            
        ##### The song details #####
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        title = item['Name']
        musicBrainzId = API.getProvider('MusicBrainzTrackId')
        genres = item.get('Genres')
        genre = " / ".join(genres)
        artists = " / ".join(item['Artists'])
        tracknumber = item.get('IndexNumber', 0)
        disc = item.get('ParentIndexNumber', 1)
        if disc == 1:
            track = tracknumber
        else:
            track = disc*2**16 + tracknumber
        year = item.get('ProductionYear')
        duration = API.getRuntime()
        rating = userdata['UserRating']

        #if enabled, try to get the rating from file and/or emby
        if not self.directstream:
            rating, comment, hasEmbeddedCover = musicutils.getAdditionalSongTags(itemid, rating, API, kodicursor, emby_db, self.enableimportsongrating, self.enableexportsongrating, self.enableupdatesongrating)
        else:
            hasEmbeddedCover = False
            comment = API.getOverview()
            
            
        ##### GET THE FILE AND PATH #####
        if self.directstream:
            path = "%s/emby/Audio/%s/" % (self.server, itemid)
            filename = "stream.mp3"
        else:
            playurl = API.getFilePath()

            if "\\" in playurl:
                # Local path
                filename = playurl.rsplit("\\", 1)[1]
            else: # Network share
                filename = playurl.rsplit("/", 1)[1]

            # Direct paths is set the Kodi way
            if not self.pathValidation(playurl):
                return False
            
            path = playurl.replace(filename, "")
            window('emby_pathverified', value="true")

        ##### UPDATE THE SONG #####
        if update_item:
            log.info("UPDATE song itemid: %s - Title: %s" % (itemid, title))
            
            # Update path
            query = "UPDATE path SET strPath = ? WHERE idPath = ?"
            kodicursor.execute(query, (path, pathid))

            # Update the song entry
            query = ' '.join((
                
                "UPDATE song",
                "SET idAlbum = ?, strArtists = ?, strGenres = ?, strTitle = ?, iTrack = ?,",
                    "iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,",
                    "rating = ?, comment = ?",
                "WHERE idSong = ?"
            ))
            kodicursor.execute(query, (albumid, artists, genre, title, track, duration, year,
                filename, playcount, dateplayed, rating, comment, songid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE SONG #####
        else:
            log.info("ADD song itemid: %s - Title: %s" % (itemid, title))
            
            # Add path
            pathid = self.kodi_db.addPath(path)

            try:
                # Get the album
                emby_dbalbum = emby_db.getItem_byId(item['AlbumId'])
                albumid = emby_dbalbum[0]
            except KeyError:
                # Verify if there's an album associated.
                album_name = item.get('Album')
                if album_name:
                    log.info("Creating virtual music album for song: %s." % itemid)
                    albumid = self.kodi_db.addAlbum(album_name, API.getProvider('MusicBrainzAlbum'))
                    emby_db.addReference("%salbum%s" % (itemid, albumid), albumid, "MusicAlbum_", "album")
                else:
                    # No album Id associated to the song.
                    log.error("Song itemid: %s has no albumId associated." % itemid)
                    return False

            except TypeError:
                # No album found. Let's create it
                log.info("Album database entry missing.")
                emby_albumId = item['AlbumId']
                album = emby.getItem(emby_albumId)
                self.add_updateAlbum(album)
                emby_dbalbum = emby_db.getItem_byId(emby_albumId)
                try:
                    albumid = emby_dbalbum[0]
                    log.info("Found albumid: %s" % albumid)
                except TypeError:
                    # No album found, create a single's album
                    log.info("Failed to add album. Creating singles.")
                    kodicursor.execute("select coalesce(max(idAlbum),0) from album")
                    albumid = kodicursor.fetchone()[0] + 1
                    if self.kodiversion == 16:
                        # Kodi Jarvis
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, strReleaseType)

                            VALUES (?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, "single"))
                    elif self.kodiversion == 15:
                        # Kodi Isengard
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, dateAdded, strReleaseType)

                            VALUES (?, ?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, dateadded, "single"))
                    else:
                        # Kodi Helix
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, dateAdded)

                            VALUES (?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, dateadded))
            
            # Create the song entry
            kodicursor.execute("select coalesce(max(idSong),0) from song")
            songid = kodicursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO song(
                    idSong, idAlbum, idPath, strArtists, strGenres, strTitle, iTrack,
                    iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed,
                    rating)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (songid, albumid, pathid, artists, genre, title, track,
                duration, year, filename, musicBrainzId, playcount, dateplayed, rating))

            # Create the reference in emby table
            emby_db.addReference(itemid, songid, "Audio", "song", pathid=pathid, parentid=albumid,
                checksum=checksum)

        
        # Link song to album
        query = (
            '''
            INSERT OR REPLACE INTO albuminfosong(
                idAlbumInfoSong, idAlbumInfo, iTrack, strTitle, iDuration)
            
            VALUES (?, ?, ?, ?, ?)
            '''
        )
        kodicursor.execute(query, (songid, albumid, track, title, duration))
        
        # Link song to artists
        for index, artist in enumerate(item['ArtistItems']):

            artist_name = artist['Name']
            artist_eid = artist['Id']
            artist_edb = emby_db.getItem_byId(artist_eid)
            try:
                artistid = artist_edb[0]
            except TypeError:
                # Artist is missing from emby database, add it.
                artist_full = emby.getItem(artist_eid)
                self.add_updateArtist(artist_full)
                artist_edb = emby_db.getItem_byId(artist_eid)
                artistid = artist_edb[0]
            finally:
                query = (
                    '''
                    INSERT OR REPLACE INTO song_artist(idArtist, idSong, iOrder, strArtist)

                    VALUES (?, ?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (artistid, songid, index, artist_name))

        # Verify if album artist exists
        album_artists = []
        for artist in item['AlbumArtists']:

            artist_name = artist['Name']
            album_artists.append(artist_name)
            artist_eid = artist['Id']
            artist_edb = emby_db.getItem_byId(artist_eid)
            try:
                artistid = artist_edb[0]
            except TypeError:
                # Artist is missing from emby database, add it.
                artist_full = emby.getItem(artist_eid)
                self.add_updateArtist(artist_full)
                artist_edb = emby_db.getItem_byId(artist_eid)
                artistid = artist_edb[0]
            finally:
                query = (
                    '''
                    INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist)

                    VALUES (?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (artistid, albumid, artist_name))
                # Update discography
                if item.get('Album'):
                    query = (
                        '''
                        INSERT OR REPLACE INTO discography(idArtist, strAlbum, strYear)

                        VALUES (?, ?, ?)
                        '''
                    )
                    kodicursor.execute(query, (artistid, item['Album'], 0))
        else:
            album_artists = " / ".join(album_artists)
            query = ' '.join((

                "SELECT strArtists",
                "FROM album",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (albumid,))
            result = kodicursor.fetchone()
            if result and result[0] != album_artists:
                # Field is empty
                if self.kodiversion in (16, 17):
                    # Kodi Jarvis, Krypton
                    query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                    kodicursor.execute(query, (album_artists, albumid))
                elif self.kodiversion == 15:
                    # Kodi Isengard
                    query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                    kodicursor.execute(query, (album_artists, albumid))
                else:
                    # Kodi Helix
                    query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                    kodicursor.execute(query, (album_artists, albumid))

        # Add genres
        self.kodi_db.addMusicGenres(songid, genres, "song")
        
        # Update artwork
        allart = artwork.getAllArtwork(item, parentInfo=True)
        if hasEmbeddedCover:
            allart["Primary"] = "image://music@" + artwork.single_urlencode( playurl )
        artwork.addArtwork(allart, songid, "song", kodicursor)

        if item.get('AlbumId') is None:
            # Update album artwork
            artwork.addArtwork(allart, albumid, "album", kodicursor)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        API = api.API(item)

        # Get emby information
        itemid = item['Id']
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()
        rating = userdata['UserRating']

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            log.info("Update playstate for %s: %s" % (mediatype, item['Name']))
        except TypeError:
            return

        if mediatype == "song":
            
            #should we ignore this item ?
            #happens when userdata updated by ratings method
            if window("ignore-update-%s" %itemid):
                window("ignore-update-%s" %itemid,clear=True)
                return
                
            # Process playstates
            playcount = userdata['PlayCount']
            dateplayed = userdata['LastPlayedDate']
            
            #process item ratings
            rating, comment, hasEmbeddedCover = musicutils.getAdditionalSongTags(itemid, rating, API, kodicursor, emby_db, self.enableimportsongrating, self.enableexportsongrating, self.enableupdatesongrating)
            
            query = "UPDATE song SET iTimesPlayed = ?, lastplayed = ?, rating = ? WHERE idSong = ?"
            kodicursor.execute(query, (playcount, dateplayed, rating, kodiid))

        elif mediatype == "album":
            # Process playstates
            query = "UPDATE album SET iRating = ? WHERE idAlbum = ?"
            kodicursor.execute(query, (rating, kodiid))

        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove kodiid, fileid, pathid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            log.info("Removing %s kodiid: %s" % (mediatype, kodiid))
        except TypeError:
            return

        ##### PROCESS ITEM #####

        # Remove the emby reference
        emby_db.removeItem(itemid)


        ##### IF SONG #####

        if mediatype == "song":
            # Delete song
            self.removeSong(kodiid)
            # This should only address single song scenario, where server doesn't actually
            # create an album for the song. 
            emby_db.removeWildItem(itemid)

            for item in emby_db.getItem_byWildId(itemid):

                item_kid = item[0]
                item_mediatype = item[1]

                if item_mediatype == "album":
                    childs = emby_db.getItem_byParentId(item_kid, "song")
                    if not childs:
                        # Delete album
                        self.removeAlbum(item_kid)

        ##### IF ALBUM #####

        elif mediatype == "album":
            # Delete songs, album
            album_songs = emby_db.getItem_byParentId(kodiid, "song")
            for song in album_songs:
                self.removeSong(song[1])
            else:
                # Remove emby songs
                emby_db.removeItems_byParentId(kodiid, "song")

            # Remove the album
            self.removeAlbum(kodiid)

        ##### IF ARTIST #####

        elif mediatype == "artist":
            # Delete songs, album, artist
            albums = emby_db.getItem_byParentId(kodiid, "album")
            for album in albums:
                albumid = album[1]
                album_songs = emby_db.getItem_byParentId(albumid, "song")
                for song in album_songs:
                    self.removeSong(song[1])
                else:
                    # Remove emby song
                    emby_db.removeItems_byParentId(albumid, "song")
                    # Remove emby artist
                    emby_db.removeItems_byParentId(albumid, "artist")
                    # Remove kodi album
                    self.removeAlbum(albumid)
            else:
                # Remove emby albums
                emby_db.removeItems_byParentId(kodiid, "album")

            # Remove artist
            self.removeArtist(kodiid)

        log.info("Deleted %s: %s from kodi database" % (mediatype, itemid))

    def removeSong(self, kodiId):

        kodicursor = self.kodicursor

        self.artwork.deleteArtwork(kodiId, "song", self.kodicursor)
        self.kodicursor.execute("DELETE FROM song WHERE idSong = ?", (kodiId,))

    def removeAlbum(self, kodiId):

        self.artwork.deleteArtwork(kodiId, "album", self.kodicursor)
        self.kodicursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodiId,))

    def removeArtist(self, kodiId):

        self.artwork.deleteArtwork(kodiId, "artist", self.kodicursor)
        self.kodicursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodiId,))