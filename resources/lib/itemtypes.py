# -*- coding: utf-8 -*-

##################################################################################################

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
import utils
import embydb_functions as embydb
import kodidb_functions as kodidb
import read_embyserver as embyserver

##################################################################################################


class Items(object):


    def __init__(self, embycursor, kodicursor):

        self.embycursor = embycursor
        self.kodicursor = kodicursor

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.doUtils = downloadutils.DownloadUtils()

        self.kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])
        self.directpath = utils.settings('useDirectPaths') == "1"
        self.music_enabled = utils.settings('enableMusic') == "true"
        self.contentmsg = utils.settings('newContent') == "true"
        
        self.artwork = artwork.Artwork()
        self.emby = embyserver.Read_EmbyServer()
        self.emby_db = embydb.Embydb_Functions(embycursor)
        self.kodi_db = kodidb.Kodidb_Functions(kodicursor)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def itemsbyId(self, items, process, pdialog=None):
        # Process items by itemid. Process can be added, update, userdata, remove
        emby = self.emby
        embycursor = self.embycursor
        kodicursor = self.kodicursor
        music_enabled = self.music_enabled
        
        itemtypes = {

            'Movie': Movies,
            'BoxSet': Movies,
            'MusicVideo': MusicVideos,
            'Series': TVShows,
            'Season': TVShows,
            'Episode': TVShows,
            'MusicAlbum': Music,
            'MusicArtist': Music,
            'AlbumArtist': Music,
            'Audio': Music,
            'Video': HomeVideos
        }

        total = 0
        for item in items:
            total += len(items[item])

        if total == 0:
            return False

        self.logMsg("Processing %s: %s" % (process, items), 1)
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
                    musicconn = utils.kodiSQL('music')
                    musiccursor = musicconn.cursor()
                    items_process = itemtypes[itemtype](embycursor, musiccursor)
                else:
                    # Music is not enabled, do not proceed with itemtype
                    continue
            else:
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
            elif itemtype == "Video":
                actions = {
                    'added': items_process.added,
                    'update': items_process.add_update,
                    'userdata': items_process.updateUserdata,
                    'remove': items_process.remove
                }
            else:
                self.logMsg("Unsupported itemtype: %s." % itemtype, 1)
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
                            title = "%s - %s" % (item['SeriesName'], title)

                        if pdialog:
                            percentage = int((float(count) / float(total))*100)
                            pdialog.update(percentage, message=title)
                            count += 1

                        actions[process](item)
                    else:
                        if itemtype == "Movie" and process == "update":
                            # Refresh boxsets
                            boxsets = self.emby.getBoxset()
                            items_process.added_boxset(boxsets['Items'], pdialog)


            if musicconn is not None:
                # close connection for special types
                musicconn.commit()
                musiccursor.close()

        return True

    def contentPop(self, name):
        xbmcgui.Dialog().notification(
                heading="Emby for Kodi",
                message="Added: %s" % name,
                icon="special://home/addons/plugin.video.emby/icon.png",
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
                self.contentPop(title)
        # Refresh boxsets
        boxsets = self.emby.getBoxset()
        self.added_boxset(boxsets['Items'], pdialog)

    def added_boxset(self, items, pdialog):

        total = len(items)
        count = 0
        for boxset in items:

            title = boxset['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateBoxset(boxset)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single movie
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg("movieid: %s fileid: %s pathid: %s" % (movieid, fileid, pathid), 1)
        
        except TypeError:
            update_item = False
            self.logMsg("movieid: %s not found." % itemid, 2)
            # movieid
            kodicursor.execute("select coalesce(max(idMovie),0) from movie")
            movieid = kodicursor.fetchone()[0] + 1

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            self.logMsg("View tag found: %s" % viewtag, 2)

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
            trailer = "plugin://plugin.video.emby/trailer/?id=%s&mode=play" % result[0]['Id']
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
                    self.logMsg("Failed to process trailer: %s" % trailer)
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
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
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
            self.logMsg("UPDATE movie itemid: %s - Title: %s" % (itemid, title), 1)

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
            self.logMsg("ADD movie itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add path
            pathid = kodi_db.addPath(path)
            # Add the file
            fileid = kodi_db.addFile(filename, pathid)
            
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
        kodi_db.addCountries(movieid, item['ProductionLocations'], "movie")
        # Process cast
        people = artwork.getPeopleArtwork(item['People'])
        kodi_db.addPeople(movieid, people, "movie")
        # Process genres
        kodi_db.addGenres(movieid, genres, "movie")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), movieid, "movie", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        kodi_db.addStudios(movieid, studios, "movie")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite movies")
        kodi_db.addTags(movieid, tags, "movie")
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

    def add_updateBoxset(self, boxset):

        emby = self.emby
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork

        boxsetid = boxset['Id']
        title = boxset['Name']
        checksum = boxset['Etag']
        emby_dbitem = emby_db.getItem_byId(boxsetid)
        try:
            setid = emby_dbitem[0]

        except TypeError:
            setid = kodi_db.createBoxset(title)

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
        boxsetMovies = emby.getMovies_byBoxset(boxsetid)
        for movie in boxsetMovies['Items']:

            itemid = movie['Id']

            if not current.get(itemid):
                # Assign boxset to movie
                emby_dbitem = emby_db.getItem_byId(itemid)
                try:
                    movieid = emby_dbitem[0]
                except TypeError:
                    self.logMsg("Failed to add: %s to boxset." % movie['Name'], 1)
                    continue

                self.logMsg("New addition to boxset %s: %s" % (title, movie['Name']), 1)
                kodi_db.assignBoxset(setid, movieid)
                # Update emby reference
                emby_db.updateParentId(itemid, setid)
            else:
                # Remove from process, because the item still belongs
                process.remove(itemid)

        # Process removals from boxset
        for movie in process:
            movieid = current[movie]
            self.logMsg("Remove from boxset %s: %s" % (title, movieid))
            kodi_db.removefromBoxset(movieid)
            # Update emby reference
            emby_db.updateParentId(movie, None)

        # Update the reference in the emby table
        emby_db.addReference(boxsetid, setid, "BoxSet", mediatype="set", checksum=checksum)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg(
                "Update playstate for movie: %s fileid: %s"
                % (item['Name'], fileid), 1)
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            kodi_db.addTag(movieid, "Favorite movies", "movie")
        else:
            kodi_db.removeTag(movieid, "Favorite movies", "movie")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)

        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
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
            self.logMsg("Removing %sid: %s fileid: %s" % (mediatype, kodiid, fileid), 1)
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

        self.logMsg("Deleted %s %s from kodi database" % (mediatype, itemid), 1)

class HomeVideos(Items):

    
    def __init__(self, embycursor, kodicursor):
        Items.__init__(self, embycursor, kodicursor)

    def added(self, items, pdialog):

        total = len(items)
        count = 0
        for hvideo in items:

            title = hvideo['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_update(hvideo)
            if not pdialog and self.contentmsg:
                self.contentPop(title)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single movie
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = api.API(item)

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            hmovieid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            pathid = emby_dbitem[2]
            self.logMsg("hmovieid: %s fileid: %s pathid: %s" % (hmovieid, fileid, pathid), 1)
        
        except TypeError:
            update_item = False
            self.logMsg("hmovieid: %s not found." % itemid, 2)
            # movieid
            kodicursor.execute("select coalesce(max(idMovie),0) from movie")
            hmovieid = kodicursor.fetchone()[0] + 1

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            self.logMsg("View tag found: %s" % viewtag, 2)

        # fileId information
        checksum = API.getChecksum()
        dateadded = API.getDateCreated()
        userdata = API.getUserData()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        people = API.getPeople()
        title = item['Name']
        year = item.get('ProductionYear')
        sorttitle = item['SortName']
        runtime = API.getRuntime()
        genre = "HomeVideos"

        
        ##### GET THE FILE AND PATH #####
        playurl = API.getFilePath()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                utils.window('emby_directPath', clear=True)
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
        else:
            # Set plugin path and media flags using real filename
            path = "plugin://plugin.video.emby.movies/"
            params = {

                'filename': filename.encode('utf-8'),
                'id': itemid,
                'dbid': hmovieid,
                'mode': "play"
            }
            filename = "%s?%s" % (path, urllib.urlencode(params))


        ##### UPDATE THE MOVIE #####
        if update_item:
            self.logMsg("UPDATE homemovie itemid: %s - Title: %s" % (itemid, title), 1)

            # Update the movie entry
            query = ' '.join((
                
                "UPDATE movie",
                "SET c00 = ?, c07 = ?, c10 = ?, c11 = ?, c14 = ?, c16 = ?",
                "WHERE idMovie = ?"
            ))
            kodicursor.execute(query, (title, year, sorttitle, runtime, genre, title, hmovieid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE MOVIE #####
        else:
            self.logMsg("ADD homemovie itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add path
            pathid = kodi_db.addPath(path)
            # Add the file
            fileid = kodi_db.addFile(filename, pathid)
            
            # Create the movie entry
            query = (
                '''
                INSERT INTO movie(
                    idMovie, idFile, c00, c07, c10, c11, c14, c16)

                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                '''
            )
            kodicursor.execute(query, (hmovieid, fileid, title, year, sorttitle, runtime,
                genre, title))

            # Create the reference in emby table
            emby_db.addReference(itemid, hmovieid, "Video", "movie", fileid, pathid,
                None, checksum, viewid)

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
        

        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), hmovieid, "movie", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite homemovies")
        kodi_db.addTags(hmovieid, tags, "movie")
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg(
                "Update playstate for homemovie: %s fileid: %s"
                % (item['Name'], fileid), 1)
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            kodi_db.addTag(movieid, "Favorite homemovies", "movie")
        else:
            kodi_db.removeTag(movieid, "Favorite homemovies", "movie")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)

        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove movieid, fileid, emby reference
        emby_db = self.emby_db
        kodicursor = self.kodicursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            hmovieid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            self.logMsg("Removing hmovieid: %s fileid: %s" % (hmovieid, fileid), 1)
        except TypeError:
            return

        # Remove artwork
        artwork.deleteArtwork(hmovieid, "movie", kodicursor)

        # Delete kodi movie and file
        kodicursor.execute("DELETE FROM movie WHERE idMovie = ?", (hmovieid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))

        # Remove the emby reference
        emby_db.removeItem(itemid)

        self.logMsg("Deleted homemovie %s from kodi database" % itemid, 1)

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
                self.contentPop(title)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single music video
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg("mvideoid: %s fileid: %s pathid: %s" % (mvideoid, fileid, pathid), 1)
        
        except TypeError:
            update_item = False
            self.logMsg("mvideoid: %s not found." % itemid, 2)
            # mvideoid
            kodicursor.execute("select coalesce(max(idMVideo),0) from musicvideo")
            mvideoid = kodicursor.fetchone()[0] + 1

        if not viewtag or not viewid:
            # Get view tag from emby
            viewtag, viewid, mediatype = self.emby.getView_embyId(itemid)
            self.logMsg("View tag found: %s" % viewtag, 2)

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
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
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
            self.logMsg("UPDATE mvideo itemid: %s - Title: %s" % (itemid, title), 1)
            
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
            self.logMsg("ADD mvideo itemid: %s - Title: %s" % (itemid, title), 1)
            
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
        kodi_db.addPeople(mvideoid, people, "musicvideo")
        # Process genres
        kodi_db.addGenres(mvideoid, genres, "musicvideo")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), mvideoid, "musicvideo", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process studios
        kodi_db.addStudios(mvideoid, studios, "musicvideo")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite musicvideos")
        kodi_db.addTags(mvideoid, tags, "musicvideo")
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg(
                "Update playstate for musicvideo: %s fileid: %s"
                % (item['Name'], fileid), 1)
        except TypeError:
            return

        # Process favorite tags
        if userdata['Favorite']:
            kodi_db.addTag(mvideoid, "Favorite musicvideos", "musicvideo")
        else:
            kodi_db.removeTag(mvideoid, "Favorite musicvideos", "musicvideo")

        # Process playstates
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)

        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
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
            self.logMsg("Removing mvideoid: %s fileid: %s" % (mvideoid, fileid, pathid), 1)
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
        rows = kodicursor.fetchall()
        for row in rows:
            
            url = row[0]
            imagetype = row[1]
            if imagetype in ("poster", "fanart"):
                artwork.deleteCachedArtwork(url)

        kodicursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (mvideoid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        if self.directpath:
            kodicursor.execute("DELETE FROM path WHERE idPath = ?", (pathid,))
        self.embycursor.execute("DELETE FROM emby WHERE emby_id = ?", (itemid,))

        self.logMsg("Deleted musicvideo %s from kodi database" % itemid, 1)

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
                self.contentPop(title)


    def add_update(self, item, viewtag=None, viewid=None):
        # Process single tvshow
        kodicursor = self.kodicursor
        emby = self.emby
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = api.API(item)

        if utils.settings('syncEmptyShows') == "false" and not item['RecursiveItemCount']:
            self.logMsg("Skipping empty show: %s" % item['Name'], 1)
            return
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            showid = emby_dbitem[0]
            pathid = emby_dbitem[2]
            self.logMsg("showid: %s pathid: %s" % (showid, pathid), 1)
        
        except TypeError:
            update_item = False
            self.logMsg("showid: %s not found." % itemid, 2)

        if viewtag is None or viewid is None:
            # Get view tag from emby
            viewtag, viewid, mediatype = emby.getView_embyId(itemid)
            self.logMsg("View tag found: %s" % viewtag, 2)

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

            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(path):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False

            utils.window('emby_pathverified', value="true")
        else:
            # Set plugin path
            toplevelpath = "plugin://plugin.video.emby.tvshows/"
            path = "%s%s/" % (toplevelpath, itemid)


        ##### UPDATE THE TVSHOW #####
        if update_item:
            self.logMsg("UPDATE tvshow itemid: %s - Title: %s" % (itemid, title), 1)

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
            self.logMsg("ADD tvshow itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add top path
            toppathid = kodi_db.addPath(toplevelpath)
            query = ' '.join((

                "UPDATE path",
                "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
                "WHERE idPath = ?"
            ))
            kodicursor.execute(query, (toplevelpath, "tvshows", "metadata.local", 1, toppathid))
            
            # Add path
            pathid = kodi_db.addPath(path)
            
            # Create the tvshow entry
            kodicursor.execute("select coalesce(max(idShow),0) from tvshow")
            showid = kodicursor.fetchone()[0] + 1
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
        kodi_db.addPeople(showid, people, "tvshow")
        # Process genres
        kodi_db.addGenres(showid, genres, "tvshow")
        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), showid, "tvshow", kodicursor)
        # Process studios
        kodi_db.addStudios(showid, studios, "tvshow")
        # Process tags: view, emby tags
        tags = [viewtag]
        tags.extend(item['Tags'])
        if userdata['Favorite']:
            tags.append("Favorite tvshows")
        kodi_db.addTags(showid, tags, "tvshow")
        # Process seasons
        all_seasons = emby.getSeasons(itemid)
        for season in all_seasons['Items']:
            self.add_updateSeason(season, showid=showid)
        else:
            # Finally, refresh the all season entry
            seasonid = kodi_db.addSeason(showid, -1)
            # Process artwork
            artwork.addArtwork(artwork.getAllArtwork(item), seasonid, "season", kodicursor)

    def add_updateSeason(self, item, showid=None):

        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork

        if item['LocationType'] == "Virtual":
            self.logMsg("Skipping virtual season.")
            return

        seasonnum = item.get('IndexNumber', 1)
        itemid = item['Id']

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
            
        seasonid = kodi_db.addSeason(showid, seasonnum)
        # Create the reference in emby table
        emby_db.addReference(itemid, seasonid, "Season", "season", parentid=showid)

        # Process artwork
        artwork.addArtwork(artwork.getAllArtwork(item), seasonid, "season", kodicursor)

    def add_updateEpisode(self, item):
        # Process single episode
        kodiversion = self.kodiversion
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg("episodeid: %s fileid: %s pathid: %s" % (episodeid, fileid, pathid), 1)
        
        except TypeError:
            update_item = False
            self.logMsg("episodeid: %s not found." % itemid, 2)
            # episodeid
            kodicursor.execute("select coalesce(max(idEpisode),0) from episode")
            episodeid = kodicursor.fetchone()[0] + 1

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
        seriesId = item['SeriesId']
        seriesName = item['SeriesName']
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
            airsBeforeSeason = item.get('AirsBeforeSeasonNumber', "-1")
            airsBeforeEpisode = item.get('AirsBeforeEpisodeNumber', "-1")

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
                self.logMsg("Skipping: %s. Unable to add series: %s." % (itemid, seriesId))
                return False

        seasonid = kodi_db.addSeason(showid, season)

        
        ##### GET THE FILE AND PATH #####
        playurl = API.getFilePath()

        if "\\" in playurl:
            # Local path
            filename = playurl.rsplit("\\", 1)[1]
        else: # Network share
            filename = playurl.rsplit("/", 1)[1]

        if self.directpath:
            # Direct paths is set the Kodi way
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")
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
            self.logMsg("UPDATE episode itemid: %s - Title: %s" % (itemid, title), 1)

            # Update the movie entry
            if kodiversion == 16:
                # Kodi Jarvis
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
            self.logMsg("ADD episode itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add path
            pathid = kodi_db.addPath(path)
            # Add the file
            fileid = kodi_db.addFile(filename, pathid)
            
            # Create the episode entry
            if kodiversion == 16:
                # Kodi Jarvis
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
        kodi_db.addPeople(episodeid, people, "episode")
        # Process artwork
        artworks = artwork.getAllArtwork(item)
        artwork.addOrUpdateArt(artworks['Primary'], episodeid, "episode", "thumb", kodicursor)
        # Process stream details
        streams = API.getMediaStreams()
        kodi_db.addStreams(fileid, streams, runtime)
        # Process playstates
        resume = API.adjustResume(userdata['Resume'])
        total = round(float(runtime), 6)
        kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
        if not self.directpath and resume:
            # Create additional entry for widgets. This is only required for plugin/episode.
            temppathid = kodi_db.getPath("plugin://plugin.video.emby.tvshows/")
            tempfileid = kodi_db.addFile(filename, temppathid)
            query = ' '.join((

                "UPDATE files",
                "SET idPath = ?, strFilename = ?, dateAdded = ?",
                "WHERE idFile = ?"
            ))
            kodicursor.execute(query, (temppathid, filename, dateadded, tempfileid))
            kodi_db.addPlaystate(tempfileid, resume, total, playcount, dateplayed)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        API = api.API(item)
        
        # Get emby information
        itemid = item['Id']
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            fileid = emby_dbitem[1]
            mediatype = emby_dbitem[4]
            self.logMsg(
                "Update playstate for %s: %s fileid: %s"
                % (mediatype, item['Name'], fileid), 1)
        except TypeError:
            return

        # Process favorite tags
        if mediatype == "tvshow":
            if userdata['Favorite']:
                kodi_db.addTag(kodiid, "Favorite tvshows", "tvshow")
            else:
                kodi_db.removeTag(kodiid, "Favorite tvshows", "tvshow")

        # Process playstates
        if mediatype == "episode":
            playcount = userdata['PlayCount']
            dateplayed = userdata['LastPlayedDate']
            resume = API.adjustResume(userdata['Resume'])
            total = round(float(runtime), 6)

            kodi_db.addPlaystate(fileid, resume, total, playcount, dateplayed)
            if not self.directpath and not resume:
                # Make sure there's no other bookmarks created by widget.
                filename = kodi_db.getFile(fileid)
                kodi_db.removeFile("plugin://plugin.video.emby.tvshows/", filename)
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
            self.logMsg("Removing %s kodiid: %s fileid: %s" % (mediatype, kodiid, fileid), 1)
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

        self.logMsg("Deleted %s: %s from kodi database" % (mediatype, itemid), 1)

    def removeShow(self, kodiid):
        
        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "tvshow", kodicursor)
        kodicursor.execute("DELETE FROM tvshow WHERE idShow = ?", (kodiid,))
        self.logMsg("Removed tvshow: %s." % kodiid, 2)

    def removeSeason(self, kodiid):
        
        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "season", kodicursor)
        kodicursor.execute("DELETE FROM seasons WHERE idSeason = ?", (kodiid,))
        self.logMsg("Removed season: %s." % kodiid, 2)

    def removeEpisode(self, kodiid, fileid):

        kodicursor = self.kodicursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "episode", kodicursor)
        kodicursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodiid,))
        kodicursor.execute("DELETE FROM files WHERE idFile = ?", (fileid,))
        self.logMsg("Removed episode: %s." % kodiid, 2)

class Music(Items):


    def __init__(self, embycursor, musiccursor):
        
        Items.__init__(self, embycursor, musiccursor)
        self.musiccursor = musiccursor

        self.directstream = utils.settings('streamMusic') == "true"
        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)

    def added(self, items, pdialog):
        
        total = len(items)
        count = 0
        for artist in items:

            title = artist['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateArtist(artist)
            # Add albums
            all_albums = self.emby.getAlbumsbyArtist(artist['Id'])
            self.added_album(all_albums['Items'], pdialog)

    def added_album(self, items, pdialog):
        
        total = len(items)
        count = 0
        for album in items:

            title = album['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateAlbum(album)
            # Add songs
            all_songs = self.emby.getSongsbyAlbum(album['Id'])
            self.added_song(all_songs['Items'], pdialog)

    def added_song(self, items, pdialog):
        
        total = len(items)
        count = 0
        for song in items:

            title = song['Name']
            if pdialog:
                percentage = int((float(count) / float(total))*100)
                pdialog.update(percentage, message=title)
                count += 1
            self.add_updateSong(song)
            if not pdialog and self.contentmsg:
                self.contentPop(title)


    def add_updateArtist(self, item, artisttype="MusicArtist"):
        # Process a single artist
        kodiversion = self.kodiversion
        kodicursor = self.musiccursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = api.API(item)

        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            artistid = emby_dbitem[0]
        except TypeError:
            update_item = False
            self.logMsg("artistid: %s not found." % itemid, 2)

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
            self.logMsg("UPDATE artist itemid: %s - Name: %s" % (itemid, name), 1)
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE ARTIST #####
        else:
            self.logMsg("ADD artist itemid: %s - Name: %s" % (itemid, name), 1)
            # safety checks: It looks like Emby supports the same artist multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the artist entries.
            artistid = kodi_db.addArtist(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, artistid, artisttype, "artist", checksum=checksum)
            

        # Process the artist
        if kodiversion == 16:
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
        kodiversion = self.kodiversion
        kodicursor = self.musiccursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        artwork = self.artwork
        API = api.API(item)

        update_item = True
        itemid = item['Id']
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            albumid = emby_dbitem[0]
        except TypeError:
            update_item = False
            self.logMsg("albumid: %s not found." % itemid, 2)

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
        rating = userdata['Rating']
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
            self.logMsg("UPDATE album itemid: %s - Name: %s" % (itemid, name), 1)
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE ALBUM #####
        else:
            self.logMsg("ADD album itemid: %s - Name: %s" % (itemid, name), 1)
            # safety checks: It looks like Emby supports the same artist multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the artist entries.
            albumid = kodi_db.addAlbum(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, albumid, "MusicAlbum", "album", checksum=checksum)


        # Process the album info
        if kodiversion == 16:
            # Kodi Jarvis
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                "album", albumid))
        elif kodiversion == 15:
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
        kodi_db.addMusicGenres(albumid, genres, "album")
        # Update artwork
        artwork.addArtwork(artworks, albumid, "album", kodicursor)

    def add_updateSong(self, item):
        # Process single song
        kodiversion = self.kodiversion
        kodicursor = self.musiccursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
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
            self.logMsg("songid: %s not found." % itemid, 2)
            
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
        bio = API.getOverview()
        duration = API.getRuntime()
        rating = userdata['Rating']


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
            if utils.window('emby_pathverified') != "true" and not xbmcvfs.exists(playurl):
                # Validate the path is correct with user intervention
                utils.window('emby_directPath', clear=True)
                resp = xbmcgui.Dialog().yesno(
                                        heading="Can't validate path",
                                        line1=(
                                            "Kodi can't locate file: %s. Verify the path. "
                                            "You may to verify your network credentials in the "
                                            "add-on settings or use the emby path substitution "
                                            "to format your path correctly. Stop syncing?"
                                            % playurl))
                if resp:
                    utils.window('emby_shouldStop', value="true")
                    return False
            
            path = playurl.replace(filename, "")
            utils.window('emby_pathverified', value="true")

        ##### UPDATE THE SONG #####
        if update_item:
            self.logMsg("UPDATE song itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Update path
            query = "UPDATE path SET strPath = ? WHERE idPath = ?"
            kodicursor.execute(query, (path, pathid))

            # Update the song entry
            query = ' '.join((
                
                "UPDATE song",
                "SET idAlbum = ?, strArtists = ?, strGenres = ?, strTitle = ?, iTrack = ?,",
                    "iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,",
                    "rating = ?",
                "WHERE idSong = ?"
            ))
            kodicursor.execute(query, (albumid, artists, genre, title, track, duration, year,
                filename, playcount, dateplayed, rating, songid))

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)
        
        ##### OR ADD THE SONG #####
        else:
            self.logMsg("ADD song itemid: %s - Title: %s" % (itemid, title), 1)
            
            # Add path
            pathid = kodi_db.addPath(path)

            try:
                # Get the album
                emby_dbalbum = emby_db.getItem_byId(item['AlbumId'])
                albumid = emby_dbalbum[0]
            except KeyError:
                # No album Id associated to the song.
                self.logMsg("Song itemid: %s has no albumId." % itemid, 1)
                return
            except TypeError:
                # No album found, create a single's album
                kodicursor.execute("select coalesce(max(idAlbum),0) from album")
                albumid = kodicursor.fetchone()[0] + 1
                if kodiversion == 16:
                    # Kodi Jarvis
                    query = (
                        '''
                        INSERT INTO album(idAlbum, strGenres, iYear, strReleaseType)

                        VALUES (?, ?, ?, ?)
                        '''
                    )
                    kodicursor.execute(query, (albumid, genre, year, "single"))
                elif kodiversion == 15:
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
        
        # Verify if album has artists
        addArtist = False
        query = ' '.join((

            "SELECT strArtists",
            "FROM album",
            "WHERE idAlbum = ?"
        ))
        kodicursor.execute(query, (albumid,))
        result = kodicursor.fetchone()
        if result and result[0] == "":
            addArtist = True

        if item['AlbumArtists']:
            album_artists = item['AlbumArtists']
        else:
            album_artists = item['ArtistItems']

        # Link song to artist
        artists_name = []
        for artist in album_artists:
            artist_name = artist['Name']
            artists_name.append(artist_name)
            emby_dbartist = emby_db.getItem_byId(artist['Id'])
            try:
                artistid = emby_dbartist[0]
            except: pass
            else:
                query = (
                    '''
                    INSERT OR REPLACE INTO song_artist(idArtist, idSong, strArtist)

                    VALUES (?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (artistid, songid, artist_name))

                if addArtist:
                    query = (
                        '''
                        INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist)

                        VALUES (?, ?, ?)
                        '''
                    )
                    kodicursor.execute(query, (artistid, albumid, artist_name))
        else:
            if addArtist:
                artists_onalbum = " / ".join(artists_name)
                if kodiversion == 16:
                    # Kodi Jarvis
                    query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                    kodicursor.execute(query, (artists_onalbum, albumid))
                elif kodiversion == 15:
                    # Kodi Isengard
                    query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                    kodicursor.execute(query, (artists_onalbum, albumid))
                else:
                    # Kodi Helix
                    query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                    kodicursor.execute(query, (artists_onalbum, albumid))

        # Add genres
        kodi_db.addMusicGenres(songid, genres, "song")
        # Update artwork
        artwork.addArtwork(artwork.getAllArtwork(item, parentInfo=True), songid, "song", kodicursor)

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        kodicursor = self.musiccursor
        emby_db = self.emby_db
        kodi_db = self.kodi_db
        API = api.API(item)

        # Get emby information
        itemid = item['Id']
        checksum = API.getChecksum()
        userdata = API.getUserData()
        runtime = API.getRuntime()
        rating = userdata['Rating']

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            self.logMsg("Update playstate for %s: %s" % (mediatype, item['Name']), 1)
        except TypeError:
            return

        if mediatype == "song":
            # Process playstates
            playcount = userdata['PlayCount']
            dateplayed = userdata['LastPlayedDate']
            
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
        kodicursor = self.musiccursor
        artwork = self.artwork

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            self.logMsg("Removing %s kodiid: %s" % (mediatype, kodiid), 1)
        except TypeError:
            return

        ##### PROCESS ITEM #####

        # Remove the emby reference
        emby_db.removeItem(itemid)


        ##### IF SONG #####

        if mediatype == "song":
            # Delete song
            self.removeSong(kodiid)

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

        self.logMsg("Deleted %s: %s from kodi database" % (mediatype, itemid), 1)

    def removeSong(self, kodiid):

        kodicursor = self.musiccursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "song", kodicursor)
        kodicursor.execute("DELETE FROM song WHERE idSong = ?", (kodiid,))

    def removeAlbum(self, kodiid):

        kodicursor = self.musiccursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "album", kodicursor)
        kodicursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodiid,))

    def removeArtist(self, kodiid):

        kodicursor = self.musiccursor
        artwork = self.artwork

        artwork.deleteArtwork(kodiid, "artist", kodicursor)
        kodicursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodiid,))