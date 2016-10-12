# -*- coding: utf-8 -*-

##################################################################################################

import logging

from _kodi_common import KodiItems

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class KodiMusic(KodiItems):


    def __init__(self, cursor):
        self.cursor = cursor

        KodiItems.__init__(self)

    def create_entry(self):
        self.cursor.execute("select coalesce(max(idArtist),0) from artist")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_album(self):
        self.cursor.execute("select coalesce(max(idAlbum),0) from album")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_song(self):
        self.cursor.execute("select coalesce(max(idSong),0) from song")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_genre(self):
        self.cursor.execute("select coalesce(max(idGenre),0) from genre")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def update_path(self, path_id, path):

        query = "UPDATE path SET strPath = ? WHERE idPath = ?"
        self.cursor.execute(query, (path, path_id))

    def add_role(self):
        query = (
            '''
            INSERT OR REPLACE INTO role(idRole, strRole)
            VALUES (?, ?)
            '''
        )
        self.cursor.execute(query, (1, 'Composer'))

    def get_artist(self, name, musicbrainz):

        query = ' '.join((

            "SELECT idArtist, strArtist",
            "FROM artist",
            "WHERE strMusicBrainzArtistID = ?"
        ))
        self.cursor.execute(query, (musicbrainz,))
        try:
            result = self.cursor.fetchone()
            artist_id = result[0]
            artist_name = result[1]
        except TypeError:
            artist_id = self._add_artist(name, musicbrainz)
        else:
            if artist_name != name:
                self.update_artist_name(artist_id, name)

        return artist_id

    def _add_artist(self, name, musicbrainz):

        query = ' '.join((
            # Safety check, when musicbrainz does not exist
            "SELECT idArtist",
            "FROM artist",
            "WHERE strArtist = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (name,))
        try:
            artist_id = self.cursor.fetchone()[0]
        except TypeError:
            artist_id = self.create_entry()
            query = (
                '''
                INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID)
                VALUES (?, ?, ?)
                '''
            )
            self.cursor.execute(query, (artist_id, name, musicbrainz))

        return artist_id

    def update_artist_name(self, kodi_id, name):

        query = "UPDATE artist SET strArtist = ? WHERE idArtist = ?"
        self.cursor.execute(query, (name, kodi_id,))

    def update_artist_16(self, *args):
        query = ' '.join((

            "UPDATE artist",
            "SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?,",
                "lastScraped = ?",
            "WHERE idArtist = ?"
        ))
        self.cursor.execute(query, (args))

    def update_artist(self, *args):
        query = ' '.join((

            "UPDATE artist",
            "SET strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?,",
                "lastScraped = ?, dateAdded = ?",
            "WHERE idArtist = ?"
        ))
        self.cursor.execute(query, (args))

    def link_artist(self, kodi_id, album_id, name):
        query = (
            '''
            INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist)
            VALUES (?, ?, ?)
            '''
        )
        self.cursor.execute(query, (kodi_id, album_id, name))

    def add_discography(self, kodi_id, album, year):
        query = (
            '''
            INSERT OR REPLACE INTO discography(idArtist, strAlbum, strYear)
            VALUES (?, ?, ?)
            '''
        )
        self.cursor.execute(query, (kodi_id, album, year))

    def get_album(self, name, musicbrainz):

        query = ' '.join((

            "SELECT idAlbum",
            "FROM album",
            "WHERE strMusicBrainzAlbumID = ?"
        ))
        self.cursor.execute(query, (musicbrainz,))
        try:
            album_id = self.cursor.fetchone()[0]
        except TypeError:
            album_id = self._add_album(name, musicbrainz)

        return album_id

    def _add_album(self, name, musicbrainz):

        album_id = self.create_entry_album()
        if self.kodi_version > 14:
            query = (
                '''
                INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType)
                VALUES (?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (album_id, name, musicbrainz, "album"))
        else:
            # TODO: Remove Helix code when Krypton is RC
            query = (
                '''
                INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID)
                VALUES (?, ?, ?)
                '''
            )
            self.cursor.execute(query, (album_id, name, musicbrainz))

        return album_id

    def update_album(self, *args):
        query = ' '.join((

            "UPDATE album",
            "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                "iRating = ?, lastScraped = ?, strReleaseType = ?",
            "WHERE idAlbum = ?"
        ))
        self.cursor.execute(query, (args))

    def update_album_17(self, *args):
        query = ' '.join((

            "UPDATE album",
            "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                "iUserrating = ?, lastScraped = ?, strReleaseType = ?",
            "WHERE idAlbum = ?"
        ))
        self.cursor.execute(query, (args))

    def update_album_15(self, *args):
        query = ' '.join((

            "UPDATE album",
            "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                "iRating = ?, lastScraped = ?, dateAdded = ?, strReleaseType = ?",
            "WHERE idAlbum = ?"
        ))
        self.cursor.execute(query, (args))

    def update_album_14(self, *args):
        # TODO: Remove Helix code when Krypton is RC
        query = ' '.join((

            "UPDATE album",
            "SET strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,",
                "iRating = ?, lastScraped = ?, dateAdded = ?",
            "WHERE idAlbum = ?"
        ))
        self.cursor.execute(query, (args))

    def get_album_artist(self, album_id, artists):

        query = ' '.join((

            "SELECT strArtists",
            "FROM album",
            "WHERE idAlbum = ?"
        ))
        self.cursor.execute(query, (album_id,))
        try:
            curr_artists = self.cursor.fetchone()[0]
        except TypeError:
            return

        if curr_artists != artists:
            self._update_album_artist(album_id, artists)

    def _update_album_artist(self, album_id, artists):

        query = "UPDATE album SET strArtists = ? WHERE idAlbum = ?"
        self.cursor.execute(query, (artists, album_id))

    def add_single(self, *args):
        query = (
            '''
            INSERT INTO album(idAlbum, strGenres, iYear, strReleaseType)

            VALUES (?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def add_single_15(self, *args):
        query = (
            '''
            INSERT INTO album(idAlbum, strGenres, iYear, dateAdded, strReleaseType)

            VALUES (?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def add_single_14(self, *args):
        # TODO: Remove Helix code when Krypton is RC
        query = (
            '''
            INSERT INTO album(idAlbum, strGenres, iYear, dateAdded)

            VALUES (?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def add_song(self, *args):
        query = (
            '''
            INSERT INTO song(
                idSong, idAlbum, idPath, strArtists, strGenres, strTitle, iTrack,
                iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed,
                rating)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def update_song(self, *args):
        query = ' '.join((

            "UPDATE song",
            "SET idAlbum = ?, strArtists = ?, strGenres = ?, strTitle = ?, iTrack = ?,",
                "iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,",
                "rating = ?, comment = ?",
            "WHERE idSong = ?"
        ))
        self.cursor.execute(query, (args))

    def link_song_artist(self, kodi_id, song_id, index, artist):

        if self.kodi_version > 16:
            query = (
                '''
                INSERT OR REPLACE INTO song_artist(idArtist, idSong, idRole, iOrder, strArtist)
                VALUES (?, ?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (kodi_id, song_id, 1, index, artist))
        else:
            query = (
                '''
                INSERT OR REPLACE INTO song_artist(idArtist, idSong, iOrder, strArtist)
                VALUES (?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (kodi_id, song_id, index, artist))

    def link_song_album(self, song_id, album_id, track, title, duration):
        query = (
            '''
            INSERT OR REPLACE INTO albuminfosong(
                idAlbumInfoSong, idAlbumInfo, iTrack, strTitle, iDuration)

            VALUES (?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (song_id, album_id, track, title, duration))

    def rate_song(self, kodi_id, playcount, rating, date_played):

        query = "UPDATE song SET iTimesPlayed = ?, lastplayed = ?, rating = ? WHERE idSong = ?"
        self.cursor.execute(query, (playcount, date_played, rating, kodi_id))

    def add_genres(self, kodi_id, genres, media_type):

        if media_type == "album":
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM album_genre",
                "WHERE idAlbum = ?"
            ))
            self.cursor.execute(query, (kodi_id,))

            for genre in genres:

                genre_id = self.get_genre(genre)
                query = "INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) values(?, ?)"
                self.cursor.execute(query, (genre_id, kodi_id))

        elif media_type == "song":
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM song_genre",
                "WHERE idSong = ?"
            ))
            self.cursor.execute(query, (kodi_id,))

            for genre in genres:

                genre_id = self.get_genre(genre)
                query = "INSERT OR REPLACE INTO song_genre(idGenre, idSong) values(?, ?)"
                self.cursor.execute(query, (genre_id, kodi_id))

    def get_genre(self, genre):

        query = ' '.join((

            "SELECT idGenre",
            "FROM genre",
            "WHERE strGenre = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (genre,))
        try:
            genre_id = self.cursor.fetchone()[0]
        except TypeError:
            genre_id = self._add_genre(genre)

        return genre_id

    def _add_genre(self, genre):

        genre_id = self.create_entry_genre()
        query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
        self.cursor.execute(query, (genre_id, genre))

        return genre_id

    def remove_artist(self, kodi_id):
        self.cursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodi_id,))

    def remove_album(self, kodi_id):
        self.cursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodi_id,))

    def remove_song(self, kodi_id):
        self.cursor.execute("DELETE FROM song WHERE idSong = ?", (kodi_id,))
