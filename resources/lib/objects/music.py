# -*- coding: utf-8 -*-

##################################################################################################

import logging
from datetime import datetime

import api
import embydb_functions as embydb
import musicutils
import _kodi_music
from _common import Items, catch_except
from utils import window, settings, language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Music(Items):


    def __init__(self, embycursor, kodicursor, pdialog=None):

        self.embycursor = embycursor
        self.emby_db = embydb.Embydb_Functions(self.embycursor)
        self.kodicursor = kodicursor
        self.kodi_db = _kodi_music.KodiMusic(self.kodicursor)
        self.pdialog = pdialog

        self.new_time = int(settings('newmusictime'))*1000
        self.directstream = settings('streamMusic') == "true"
        self.enableimportsongrating = settings('enableImportSongRating') == "true"
        self.enableexportsongrating = settings('enableExportSongRating') == "true"
        self.enableupdatesongrating = settings('enableUpdateSongRating') == "true"
        self.userid = window('emby_currUser')
        self.server = window('emby_server%s' % self.userid)

        Items.__init__(self)

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
        views = self.emby_db.getView_byType('music')

        for view in views:
            # Process artists
            self.compare_artists(view)
            # Process albums
            self.compare_albums()
            # Process songs
            self.compare_songs()

        return True

    def compare_artists(self, view):

        all_embyartistsIds = set()
        update_list = list()

        if self.pdialog:
            self.pdialog.update(heading=lang(29999), message="%s Artists..." % lang(33031))

        artists = dict(self.emby_db.get_checksum('MusicArtist'))
        album_artists = dict(self.emby_db.get_checksum('AlbumArtist'))
        emby_artists = self.emby.getArtists(view['id'], dialog=self.pdialog)

        for item in emby_artists['Items']:

            if self.should_stop():
                    return False

            item_id = item['Id']
            API = api.API(item)

            all_embyartistsIds.add(item_id)
            if item_id in artists:
                if artists[item_id] != API.get_checksum():
                    # Only update if artist is not in Kodi or checksum is different
                    update_list.append(item_id)
            elif album_artists.get(item_id) != API.get_checksum():
                # Only update if artist is not in Kodi or checksum is different
                update_list.append(item_id)

            #compare_to.pop(item_id, None)

        log.info("Update for Artist: %s", update_list)

        emby_items = self.emby.getFullItems(update_list)
        total = len(update_list)

        if self.pdialog:
            self.pdialog.update(heading="Processing Artists / %s items" % total)

        # Process additions and updates
        if emby_items:
            self.process_all("MusicArtist", "update", emby_items, total)
        # Process removals
        for artist in artists:
            if artist not in all_embyartistsIds and artists[artist] is not None:
                self.remove(artist)

    def compare_albums(self):

        if self.pdialog:
            self.pdialog.update(heading=lang(29999), message="%s Albums..." % lang(33031))

        albums = dict(self.emby_db.get_checksum('MusicAlbum'))
        emby_albums = self.emby.getAlbums(basic=True, dialog=self.pdialog)

        return self.compare("MusicAlbum", emby_albums['Items'], albums)

    def compare_songs(self):

        if self.pdialog:
            self.pdialog.update(heading=lang(29999), message="%s Songs..." % lang(33031))

        songs = dict(self.emby_db.get_checksum('Audio'))
        emby_songs = self.emby.getSongs(basic=True, dialog=self.pdialog)

        return self.compare("Audio", emby_songs['Items'], songs)

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
        else:
            pass

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
            artistid = self.kodi_db.get_artist(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, artistid, artisttype, "artist", checksum=checksum)

        # Process the artist
        if self.kodi_version > 15:
            self.kodi_db.update_artist_16(genres, bio, thumb, fanart, lastScraped, artistid)
        else:
            self.kodi_db.update_artist(genres, bio, thumb, fanart, lastScraped, dateadded, artistid)

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
        rating = 0
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
            albumid = self.kodi_db.get_album(name, musicBrainzId)
            # Create the reference in emby table
            emby_db.addReference(itemid, albumid, "MusicAlbum", "album", checksum=checksum)

        # Process the album info
        if self.kodi_version == 17:
            # Kodi Krypton
            self.kodi_db.update_album_17(artistname, year, genre, bio, thumb, rating, lastScraped,
                                         "album", albumid)
        elif self.kodi_version == 16:
            # Kodi Jarvis
            self.kodi_db.update_album(artistname, year, genre, bio, thumb, rating, lastScraped,
                                      "album", albumid)
        elif self.kodi_version == 15:
            # Kodi Isengard
            self.kodi_db.update_album_15(artistname, year, genre, bio, thumb, rating, lastScraped,
                                         dateadded, "album", albumid)
        else:
            # TODO: Remove Helix code when Krypton is RC
            self.kodi_db.update_album_14(artistname, year, genre, bio, thumb, rating, lastScraped,
                                         dateadded, albumid)

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
                self.kodi_db.update_artist_name(artistid, artistname)

            # Add artist to album
            self.kodi_db.link_artist(artistid, albumid, artistname)
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
                self.kodi_db.add_discography(artistid, name, year)

        # Add genres
        self.kodi_db.add_genres(albumid, genres, "album")
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
            songid = self.kodi_db.create_entry_song()

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
        rating = 0

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
            self.kodi_db.update_path(pathid, path)

            # Update the song entry
            self.kodi_db.update_song(albumid, artists, genre, title, track, duration, year,
                                     filename, playcount, dateplayed, rating, comment, songid)

            # Update the checksum in emby table
            emby_db.updateReference(itemid, checksum)

        ##### OR ADD THE SONG #####
        else:
            log.info("ADD song itemid: %s - Title: %s", itemid, title)

            # Add path
            pathid = self.kodi_db.add_path(path)

            try:
                # Get the album
                emby_dbalbum = emby_db.getItem_byId(item['AlbumId'])
                albumid = emby_dbalbum[0]
            except KeyError:
                # Verify if there's an album associated.
                album_name = item.get('Album')
                if album_name:
                    log.info("Creating virtual music album for song: %s", itemid)
                    albumid = self.kodi_db.get_album(album_name, API.get_provider('MusicBrainzAlbum'))
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
                    albumid = self.kodi_db.create_entry_album()
                    if self.kodi_version == 16:
                        self.kodi_db.add_single(albumid, genre, year, "single")

                    elif self.kodi_version == 15:
                        self.kodi_db.add_single_15(albumid, genre, year, dateadded, "single")

                    else:
                        # TODO: Remove Helix code when Krypton is RC
                        self.kodi_db.add_single_14(albumid, genre, year, dateadded)

            # Create the song entry
            self.kodi_db.add_song(songid, albumid, pathid, artists, genre, title, track, duration,
                                  year, filename, musicBrainzId, playcount, dateplayed, rating)

            # Create the reference in emby table
            emby_db.addReference(itemid, songid, "Audio", "song", pathid=pathid, parentid=albumid,
                                 checksum=checksum)

        # Link song to album
        self.kodi_db.link_song_album(songid, albumid, track, title, duration)
        # Create default role
        if self.kodi_version > 16:
            self.kodi_db.add_role()

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
                artistid = artist_edb[0] if artist_edb else None
            except Exception:
                artistid = None

            if artistid:
                # Link song to artist
                self.kodi_db.link_song_artist(artistid, songid, index, artist_name)

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
                # Link artist to album
                self.kodi_db.link_artist(artistid, albumid, artist_name)
                # Update discography
                if item.get('Album'):
                    self.kodi_db.add_discography(artistid, item['Album'], 0)

        # Artist names
        album_artists = " / ".join(album_artists)
        self.kodi_db.get_album_artist(albumid, album_artists)

        # Add genres
        self.kodi_db.add_genres(songid, genres, "song")

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
        rating = 0

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
            self.kodi_db.rate_song(playcount, dateplayed, rating, kodiid)

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

        log.info("Deleted %s: %s from kodi database", mediatype, itemid)

    def removeSong(self, kodi_id):

        self.artwork.delete_artwork(kodi_id, "song", self.kodicursor)
        self.kodi_db.remove_song(kodi_id)

    def removeAlbum(self, kodi_id):

        self.artwork.delete_artwork(kodi_id, "album", self.kodicursor)
        self.kodi_db.remove_album(kodi_id)

    def removeArtist(self, kodi_id):

        self.artwork.delete_artwork(kodi_id, "artist", self.kodicursor)
        self.kodi_db.remove_artist(kodi_id)
