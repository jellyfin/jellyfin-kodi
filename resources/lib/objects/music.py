# -*- coding: utf-8 -*-

##################################################################################################

import logging
from datetime import datetime

import api
import common
import embydb_functions as embydb
import kodidb_functions as kodidb
import musicutils
from utils import window, settings, language as lang, catch_except

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Music(common.Items):


    def __init__(self, embycursor, kodicursor, pdialog=None):

        self.embycursor = embycursor
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodicursor = kodicursor
        self.kodi_db = kodidb.Kodidb_Functions(self.kodicursor)
        self.pdialog = pdialog

        self.new_time = int(settings('newmusictime'))*1000
        self.directstream = settings('streamMusic') == "true"
        self.enableimportsongrating = settings('enableImportSongRating') == "true"
        self.enableexportsongrating = settings('enableExportSongRating') == "true"
        self.enableupdatesongrating = settings('enableUpdateSongRating') == "true"
        self.userid = window('emby_currUser')
        self.server = window('emby_server%s' % self.userid)

        common.Items.__init__(self)

    def _get_func(self, item_type, action):

        if item_type == "MusicAlbum":
            actions = {
                'added': self.added_album,
                'update': self.add_updateAlbum,
                'userdata': self.updateUserdata,
                'remove': self.remove
            }
        elif item_type in ("MusicArtist", "AlbumArtist"):
            actions = {
                'added': self.added,
                'update': self.add_updateArtist,
                'remove': self.remove
            }
        elif item_type == "Audio":
            actions = {
                'added': self.added_song,
                'update': self.add_updateSong,
                'userdata': self.updateUserdata,
                'remove': self.remove
            }
        else:
            log.info("Unsupported item_type: %s", item_type)
            actions = {}

        return actions.get(action)

    def compare_all(self):
        # Pull the list of artists, albums, songs
        pdialog = self.pdialog

        views = self.emby_db.getView_byType('music')
        try:
            all_kodiartists = dict(self.emby_db.get_checksum('MusicArtist'))
            all_kodialbumartists = dict(self.emby_db.get_checksum('AlbumArtist'))
        except ValueError:
            all_kodiartists = {}
            all_kodialbumartists = {}

        try:
            all_kodialbums = dict(self.emby_db.get_checksum('MusicAlbum'))
        except ValueError:
            all_kodialbums = {}

        try:
            all_kodisongs = dict(self.emby_db.get_checksum('Audio'))
        except ValueError:
            all_kodisongs = {}

        all_embyartistsIds = set()
        all_embyalbumsIds = set()
        all_embysongsIds = set()
        updatelist = []

        process = {

            'artists': [self.emby.getArtists, self.add_updateArtist],
            'albums': [self.emby.getAlbums, self.add_updateAlbum],
            'songs': [self.emby.getSongs, self.add_updateSong]
        }
        for view in views:
            for data_type in ['artists', 'albums', 'songs']:
                if pdialog:
                    pdialog.update(
                            heading=lang(29999),
                            message="%s %s..." % (lang(33031), data_type))
                if data_type != "artists":
                    all_embyitems = process[data_type][0](basic=True, dialog=pdialog)
                else:
                    all_embyitems = process[data_type][0](view['id'], dialog=pdialog)

                for embyitem in all_embyitems['Items']:
                    if self.should_stop():
                        return False
                    API = api.API(embyitem)
                    itemid = embyitem['Id']
                    if data_type == "artists":
                        all_embyartistsIds.add(itemid)
                        if itemid in all_kodiartists:
                            if all_kodiartists[itemid] != API.get_checksum():
                                # Only update if artist is not in Kodi or checksum is different
                                updatelist.append(itemid)
                        elif all_kodialbumartists.get(itemid) != API.get_checksum():
                            # Only update if artist is not in Kodi or checksum is different
                            updatelist.append(itemid)
                    elif data_type == "albums":
                        all_embyalbumsIds.add(itemid)
                        if all_kodialbums.get(itemid) != API.get_checksum():
                            # Only update if album is not in Kodi or checksum is different
                            updatelist.append(itemid)
                    else:
                        all_embysongsIds.add(itemid)
                        if all_kodisongs.get(itemid) != API.get_checksum():
                            # Only update if songs is not in Kodi or checksum is different
                            updatelist.append(itemid)
                log.info("%s to update: %s", data_type, updatelist)
                embyitems = self.emby.getFullItems(updatelist)
                self.total = len(updatelist)
                del updatelist[:]
                if pdialog:
                    pdialog.update(heading="Processing %s / %s items" % (data_type, self.total))
                self.count = 0
                for embyitem in embyitems:
                    # Process individual item
                    if self.should_stop():
                        return False
                    self.title = embyitem['Name']
                    self.update_pdialog()
                    process[data_type][1](embyitem)
                    self.count += 1
        ##### PROCESS DELETES #####
        for kodiartist in all_kodiartists:
            if kodiartist not in all_embyartistsIds and all_kodiartists[kodiartist] is not None:
                self.remove(kodiartist)

        log.info("Artist compare finished.")

        for kodialbum in all_kodialbums:
            if kodialbum not in all_embyalbumsIds:
                self.remove(kodialbum)

        log.info("Albums compare finished.")

        for kodisong in all_kodisongs:
            if kodisong not in all_embysongsIds:
                self.remove(kodisong)

        log.info("Songs compare finished.")
        return True


    def added(self, items, total=None):

        for item in super(Music, self).added(items, total):
            if self.add_updateArtist(item):
                # Add albums
                all_albums = self.emby.getAlbumsbyArtist(item['Id'])
                self.added_album(all_albums['Items'])

    def added_album(self, items, total=None):

        update = True if not self.total else False

        for item in super(Music, self).added(items, total, update):
            self.title = "%s - %s" % (item.get('AlbumArtist', "unknown"), self.title)

            if self.add_updateAlbum(item):
                # Add songs
                all_songs = self.emby.getSongsbyAlbum(item['Id'])
                self.added_song(all_songs['Items'])

    def added_song(self, items, total=None):

        update = True if not self.total else False

        for item in super(Music, self).added(items, total, update):
            self.title = "%s - %s" % (item.get('AlbumArtist', "unknown"), self.title)

            if self.add_updateSong(item):
                self.content_pop(self.title)

    @catch_except()
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
            log.debug("artistid: %s not found", itemid)

        ##### The artist details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API.get_date_created()
        checksum = API.get_checksum()

        name = item['Name']
        musicBrainzId = API.get_provider('MusicBrainzArtist')
        genres = " / ".join(item.get('Genres'))
        bio = API.get_overview()

        # Associate artwork
        artworks = artwork.get_all_artwork(item, parent_info=True)
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
            log.info("UPDATE artist itemid: %s - Name: %s", itemid, name)
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE ARTIST #####
        else:
            log.info("ADD artist itemid: %s - Name: %s", itemid, name)
            # safety checks: It looks like Emby supports the same artist multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the artist entries.
            artistid = self.kodi_db.addArtist(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, artistid, artisttype, "artist", checksum=checksum)

        # Process the artist
        if self.kodi_version in (16, 17):
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
        artwork.add_artwork(artworks, artistid, "artist", kodicursor)

        return True

    @catch_except()
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
            log.debug("albumid: %s not found", itemid)

        ##### The album details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API.get_date_created()
        userdata = API.get_userdata()
        checksum = API.get_checksum()

        name = item['Name']
        musicBrainzId = API.get_provider('MusicBrainzAlbum')
        year = item.get('ProductionYear')
        genres = item.get('Genres')
        genre = " / ".join(genres)
        bio = API.get_overview()
        rating = userdata['UserRating']
        artists = item['AlbumArtists']
        artistname = []
        for artist in artists:
            artistname.append(artist['Name'])
        artistname = " / ".join(artistname)

        # Associate artwork
        artworks = artwork.get_all_artwork(item, parent_info=True)
        thumb = artworks['Primary']
        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb

        ##### UPDATE THE ALBUM #####
        if update_item:
            log.info("UPDATE album itemid: %s - Name: %s", itemid, name)
            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE ALBUM #####
        else:
            log.info("ADD album itemid: %s - Name: %s", itemid, name)
            # safety checks: It looks like Emby supports the same artist multiple times.
            # Kodi doesn't allow that. In case that happens we just merge the artist entries.
            albumid = self.kodi_db.addAlbum(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, albumid, "MusicAlbum", "album", checksum=checksum)


        # Process the album info
        if self.kodi_version == 17:
            # Kodi Krypton
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iUserrating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                                       "album", albumid))
        elif self.kodi_version == 16:
            # Kodi Jarvis
            query = ' '.join((

                "UPDATE album",
                "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                    "iRating = ?, lastScraped = ?, strReleaseType = ?",
                "WHERE idAlbum = ?"
            ))
            kodicursor.execute(query, (artistname, year, genre, bio, thumb, rating, lastScraped,
                                       "album", albumid))
        elif self.kodi_version == 15:
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

        # Assign main artists to album
        for artist in item['AlbumArtists']:
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
            # Update emby reference with parentid
            emby_db.updateParentId(artistId, albumid)

        for artist in item['ArtistItems']:
            artistId = artist['Id']
            emby_dbartist = emby_db.getItem_byId(artistId)
            try:
                artistid = emby_dbartist[0]
            except TypeError:
                pass
            else:
                # Update discography
                query = (
                    '''
                    INSERT OR REPLACE INTO discography(idArtist, strAlbum, strYear)

                    VALUES (?, ?, ?)
                    '''
                )
                kodicursor.execute(query, (artistid, name, year))

        # Add genres
        self.kodi_db.addMusicGenres(albumid, genres, "album")
        # Update artwork
        artwork.add_artwork(artworks, albumid, "album", kodicursor)

        return True

    @catch_except()
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
            log.debug("songid: %s not found", itemid)

        ##### The song details #####
        checksum = API.get_checksum()
        dateadded = API.get_date_created()
        userdata = API.get_userdata()
        playcount = userdata['PlayCount']
        dateplayed = userdata['LastPlayedDate']

        # item details
        title = item['Name']
        musicBrainzId = API.get_provider('MusicBrainzTrackId')
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
        duration = API.get_runtime()
        rating = userdata['UserRating']

        #if enabled, try to get the rating from file and/or emby
        if not self.directstream:
            rating, comment, hasEmbeddedCover = musicutils.getAdditionalSongTags(itemid, rating, API, kodicursor, emby_db, self.enableimportsongrating, self.enableexportsongrating, self.enableupdatesongrating)
        else:
            hasEmbeddedCover = False
            comment = API.get_overview()


        ##### GET THE FILE AND PATH #####
        if self.directstream:
            path = "%s/emby/Audio/%s/" % (self.server, itemid)
            extensions = ['mp3', 'aac', 'ogg', 'oga', 'webma', 'wma', 'flac']

            if 'Container' in item and item['Container'].lower() in extensions:
                filename = "stream.%s?static=true" % item['Container']
            else:
                filename = "stream.mp3?static=true"
        else:
            playurl = API.get_file_path()

            if "\\" in playurl:
                # Local path
                filename = playurl.rsplit("\\", 1)[1]
            else: # Network share
                filename = playurl.rsplit("/", 1)[1]

            # Direct paths is set the Kodi way
            if not self.path_validation(playurl):
                return False

            path = playurl.replace(filename, "")
            window('emby_pathverified', value="true")

        ##### UPDATE THE SONG #####
        if update_item:
            log.info("UPDATE song itemid: %s - Title: %s", itemid, title)

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
            log.info("ADD song itemid: %s - Title: %s", itemid, title)

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
                    log.info("Creating virtual music album for song: %s", itemid)
                    albumid = self.kodi_db.addAlbum(album_name, API.get_provider('MusicBrainzAlbum'))
                    emby_db.addReference("%salbum%s" % (itemid, albumid), albumid, "MusicAlbum_", "album")
                else:
                    # No album Id associated to the song.
                    log.error("Song itemid: %s has no albumId associated", itemid)
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
                    log.info("Found albumid: %s", albumid)
                except TypeError:
                    # No album found, create a single's album
                    log.info("Failed to add album. Creating singles.")
                    kodicursor.execute("select coalesce(max(idAlbum),0) from album")
                    albumid = kodicursor.fetchone()[0] + 1
                    if self.kodi_version == 16:
                        # Kodi Jarvis
                        query = (
                            '''
                            INSERT INTO album(idAlbum, strGenres, iYear, strReleaseType)

                            VALUES (?, ?, ?, ?)
                            '''
                        )
                        kodicursor.execute(query, (albumid, genre, year, "single"))
                    elif self.kodi_version == 15:
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
                                       duration, year, filename, musicBrainzId, playcount,
                                       dateplayed, rating))

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
                if self.kodi_version >= 17:
                    # Kodi Krypton
                    query = (
                        '''
                        INSERT OR REPLACE INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist)

                        VALUES (?, ?, ?, ?, ?)
                        '''
                    )
                    kodicursor.execute(query, (artistid, songid, 1, index, artist_name))

                    # May want to look into only doing this once?
                    query = (
                        '''
                        INSERT OR REPLACE INTO role(idRole, strRole)

                        VALUES (?, ?)
                        '''
                    )
                    kodicursor.execute(query, (1, 'Composer'))
                else:
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
            if self.kodi_version in (16, 17):
                # Kodi Jarvis, Krypton
                query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
                kodicursor.execute(query, (album_artists, albumid))
            elif self.kodi_version == 15:
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
        allart = artwork.get_all_artwork(item, parent_info=True)
        if hasEmbeddedCover:
            allart["Primary"] = "image://music@" + artwork.single_urlencode(playurl)
        artwork.add_artwork(allart, songid, "song", kodicursor)

        if item.get('AlbumId') is None:
            # Update album artwork
            artwork.add_artwork(allart, albumid, "album", kodicursor)

        return True

    def updateUserdata(self, item):
        # This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
        # Poster with progress bar
        kodicursor = self.kodicursor
        emby_db = self.emby_db
        API = api.API(item)

        # Get emby information
        itemid = item['Id']
        checksum = API.get_checksum()
        userdata = API.get_userdata()
        rating = userdata['UserRating']

        # Get Kodi information
        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            log.info("Update playstate for %s: %s", mediatype, item['Name'])
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
            if self.kodi_version >= 17:
                query = "UPDATE album SET fRating = ? WHERE idAlbum = ?"
            else:
                query = "UPDATE album SET iRating = ? WHERE idAlbum = ?"
            kodicursor.execute(query, (rating, kodiid))

        emby_db.updateReference(itemid, checksum)

    def remove(self, itemid):
        # Remove kodiid, fileid, pathid, emby reference
        emby_db = self.emby_db

        emby_dbitem = emby_db.getItem_byId(itemid)
        try:
            kodiid = emby_dbitem[0]
            mediatype = emby_dbitem[4]
            log.info("Removing %s kodiid: %s", mediatype, kodiid)
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

        self.artwork.delete_artwork(kodiId, "song", self.kodicursor)
        self.kodicursor.execute("DELETE FROM song WHERE idSong = ?", (kodiId,))

    def removeAlbum(self, kodiId):

        self.artwork.delete_artwork(kodiId, "album", self.kodicursor)
        self.kodicursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodiId,))

    def removeArtist(self, kodiId):

        self.artwork.delete_artwork(kodiId, "artist", self.kodicursor)
        self.kodicursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodiId,))
