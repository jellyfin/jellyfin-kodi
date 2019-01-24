# -*- coding: utf-8 -*-

##################################################################################################

import logging

import queries_music as QU
from kodi import Kodi

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Music(Kodi):


    def __init__(self, cursor):

        self.cursor = cursor
        Kodi.__init__(self)

    def create_entry(self):

        ''' Krypton has a dummy first entry
            idArtist: 1  strArtist: [Missing Tag]  strMusicBrainzArtistID: Artist Tag Missing
        '''
        self.cursor.execute(QU.create_artist)

        return self.cursor.fetchone()[0] + 1

    def create_entry_album(self):
        self.cursor.execute(QU.create_album)
        
        return self.cursor.fetchone()[0] + 1

    def create_entry_song(self):
        self.cursor.execute(QU.create_song)
        
        return self.cursor.fetchone()[0] + 1

    def create_entry_genre(self):
        self.cursor.execute(QU.create_genre)
        
        return self.cursor.fetchone()[0] + 1

    def update_path(self, *args):
        self.cursor.execute(QU.update_path, args)

    def add_role(self, *args):
        self.cursor.execute(QU.update_role, args)

    def get(self, artist_id, name, musicbrainz):

        ''' Get artist or create the entry.
        '''
        try:
            self.cursor.execute(QU.get_artist, (musicbrainz,))
            result = self.cursor.fetchone()
            artist_id = result[0]
            artist_name = result[1]
        except TypeError:
            artist_id = self.add_artist(artist_id, name, musicbrainz)
        else:
            if artist_name != name:
                self.update_artist_name(artist_id, name)

        return artist_id

    def add_artist(self, artist_id, name, *args):

        ''' Safety check, when musicbrainz does not exist
        '''
        try:
            self.cursor.execute(QU.get_artist_by_name, (name,))
            artist_id = self.cursor.fetchone()[0]
        except TypeError:
            artist_id = artist_id or self.create_entry()
            self.cursor.execute(QU.add_artist, (artist_id, name,) + args)

        return artist_id

    def update_artist_name(self, *args):
        self.cursor.execute(QU.update_artist_name, args)

    def update(self, *args):
        self.cursor.execute(QU.update_artist, args)

    def link(self, *args):
        self.cursor.execute(QU.update_link, args)

    def add_discography(self, *args):
        self.cursor.execute(QU.update_discography, args)

    def validate_artist(self, *args):

        try:
            self.cursor.execute(QU.get_artist_by_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def validate_album(self, *args):

        try:
            self.cursor.execute(QU.get_album_by_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def validate_song(self, *args):

        try:
            self.cursor.execute(QU.get_song_by_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_album(self, album_id, name, musicbrainz, artists=None, *args):

        try:
            if musicbrainz is not None:
                self.cursor.execute(QU.get_album, (musicbrainz,))
                album = None
            else:
                self.cursor.execute(QU.get_album_by_name, (name,))
                album = self.cursor.fetchone()

                if album[1] and album[1].split(' / ')[0] not in artists.split(' / '):
                    LOG.info("Album found, but artist doesn't match?")
                    LOG.info("Album [ %s/%s ] %s", name, album[1], artists)

                    raise TypeError

            album_id = (album or self.cursor.fetchone())[0]
        except TypeError:
            album_id = self.add_album(*(album_id, name, musicbrainz,) + args)

        return album_id

    def add_album(self, album_id, *args):

        album_id = album_id or self.create_entry_album()
        self.cursor.execute(QU.add_album, (album_id,) + args)

        return album_id

    def update_album(self, *args):
        self.cursor.execute(QU.update_album, args)

    def get_album_artist(self, album_id, artists):

        try:
            self.cursor.execute(QU.get_album_artist, (album_id,))
            curr_artists = self.cursor.fetchone()[0]
        except TypeError:
            return

        if curr_artists != artists:
            self.update_album_artist(artists, album_id)

    def update_album_artist(self, *args):
        self.cursor.execute(QU.update_album_artist, args)

    def add_single(self, *args):
        self.cursor.execute(QU.add_single, args)

    def add_song(self, *args):
        self.cursor.execute(QU.add_song, args)

    def update_song(self, *args):
        self.cursor.execute(QU.update_song, args)

    def link_song_artist(self, *args):
        self.cursor.execute(QU.update_song_artist, args)

    def link_song_album(self, *args):
        self.cursor.execute(QU.update_song_album, args)

    def rate_song(self, *args):
        self.cursor.execute(QU.update_song_rating, args)

    def add_genres(self, kodi_id, genres, media):

        ''' Add genres, but delete current genres first.
        '''
        if media == 'album':
            self.cursor.execute(QU.delete_genres_album, (kodi_id,))

            for genre in genres:

                genre_id = self.get_genre(genre)
                self.cursor.execute(QU.update_genre_album, (genre_id, kodi_id))

        elif media == 'song':
            self.cursor.execute(QU.delete_genres_song, (kodi_id,))

            for genre in genres:

                genre_id = self.get_genre(genre)
                self.cursor.execute(QU.update_genre_song, (genre_id, kodi_id))

    def get_genre(self, *args):

        try:
            self.cursor.execute(QU.get_genre, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return self.add_genre(*args)

    def add_genre(self, *args):

        genre_id = self.create_entry_genre()
        self.cursor.execute(QU.add_genre, (genre_id,) + args)

        return genre_id

    def delete(self, *args):
        self.cursor.execute(QU.delete_artist, args)

    def delete_album(self, *args):
        self.cursor.execute(QU.delete_album, args)

    def delete_song(self, *args):
        self.cursor.execute(QU.delete_song, args)
