# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

import datetime

from ..database import jellyfin_db, queries as QUEM
from ..helper import api, stop, validate, jellyfin_item, values, Local, LazyLogger
from ..helper.utils import find_library
from ..helper.exceptions import PathValidationException

from .obj import Objects
from .kodi import Music as KodiDb, queries_music as QU

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class Music(KodiDb):

    def __init__(self, server, jellyfindb, musicdb, direct_path, library=None):

        self.server = server
        self.jellyfin = jellyfindb
        self.music = musicdb
        self.direct_path = direct_path

        self.jellyfin_db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)
        self.objects = Objects()
        self.item_ids = []
        self.library = library

        KodiDb.__init__(self, musicdb.cursor)

    @stop
    @jellyfin_item
    def artist(self, item, e_item):

        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'Artist')
        update = True

        try:
            obj['ArtistId'] = e_item[0]
            obj['LibraryId'] = e_item[6]
            obj['LibraryName'] = self.jellyfin_db.get_view_name(obj['LibraryId'])
        except TypeError:
            update = False

            library = self.library or find_library(self.server, item)
            if not library:
                # This item doesn't belong to a whitelisted library
                return

            obj['ArtistId'] = None
            obj['LibraryId'] = library['Id']
            obj['LibraryName'] = library['Name']
            LOG.debug("ArtistId %s not found", obj['Id'])
        else:
            if self.validate_artist(*values(obj, QU.get_artist_by_id_obj)) is None:

                update = False
                LOG.info("ArtistId %s missing from kodi. repairing the entry.", obj['ArtistId'])

        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        obj['ArtistType'] = "MusicArtist"
        obj['Genre'] = " / ".join(obj['Genres'] or [])
        obj['Bio'] = API.get_overview(obj['Bio'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']
        obj['Backdrops'] = obj['Artwork']['Backdrop'] or ""

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if obj['Backdrops']:
            obj['Backdrops'] = "<fanart>%s</fanart>" % obj['Backdrops'][0]

        if update:
            self.artist_update(obj)
        else:
            self.artist_add(obj)

        self.update(obj['Genre'], obj['Bio'], obj['Thumb'], obj['Backdrops'], obj['LastScraped'], obj['ArtistId'])
        self.artwork.add(obj['Artwork'], obj['ArtistId'], "artist")
        self.item_ids.append(obj['Id'])

    def artist_add(self, obj):

        ''' Add object to kodi.

            safety checks: It looks like Jellyfin supports the same artist multiple times.
            Kodi doesn't allow that. In case that happens we just merge the artist entries.
        '''
        obj['ArtistId'] = self.get(*values(obj, QU.get_artist_obj))
        self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_artist_obj))
        LOG.debug("ADD artist [%s] %s: %s", obj['ArtistId'], obj['Name'], obj['Id'])

    def artist_update(self, obj):

        ''' Update object to kodi.
        '''
        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.debug("UPDATE artist [%s] %s: %s", obj['ArtistId'], obj['Name'], obj['Id'])

    @stop
    @jellyfin_item
    def album(self, item, e_item):

        ''' Update object to kodi.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'Album')
        update = True

        try:
            obj['AlbumId'] = e_item[0]
            obj['LibraryId'] = e_item[6]
            obj['LibraryName'] = self.jellyfin_db.get_view_name(obj['LibraryId'])
        except TypeError:
            update = False

            library = self.library or find_library(self.server, item)
            if not library:
                # This item doesn't belong to a whitelisted library
                return

            obj['AlbumId'] = None
            obj['LibraryId'] = library['Id']
            obj['LibraryName'] = library['Name']
            LOG.debug("AlbumId %s not found", obj['Id'])
        else:
            if self.validate_album(*values(obj, QU.get_album_by_id_obj)) is None:

                update = False
                LOG.info("AlbumId %s missing from kodi. repairing the entry.", obj['AlbumId'])

        obj['Rating'] = 0
        obj['LastScraped'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        obj['Genres'] = obj['Genres'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Bio'] = API.get_overview(obj['Bio'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)
        obj['Thumb'] = obj['Artwork']['Primary']
        obj['DateAdded'] = item.get('DateCreated')

        if obj['DateAdded']:
            obj['DateAdded'] = Local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['Thumb']:
            obj['Thumb'] = "<thumb>%s</thumb>" % obj['Thumb']

        if update:
            self.album_update(obj)
        else:
            self.album_add(obj)

        self.artist_link(obj)
        self.artist_discography(obj)
        self.update_album(*values(obj, QU.update_album_obj))
        self.add_genres(*values(obj, QU.add_genres_obj))
        self.artwork.add(obj['Artwork'], obj['AlbumId'], "album")
        self.item_ids.append(obj['Id'])

    def album_add(self, obj):

        ''' Add object to kodi.
        '''
        if self.version_id >= 82:
            obj_values = values(obj, QU.get_album_obj82)
        else:
            obj_values = values(obj, QU.get_album_obj)
        obj['AlbumId'] = self.get_album(*obj_values)
        self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_album_obj))
        LOG.debug("ADD album [%s] %s: %s", obj['AlbumId'], obj['Title'], obj['Id'])

    def album_update(self, obj):

        ''' Update object to kodi.
        '''
        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.debug("UPDATE album [%s] %s: %s", obj['AlbumId'], obj['Title'], obj['Id'])

    def artist_discography(self, obj):

        ''' Update the artist's discography.
        '''
        for artist in (obj['ArtistItems'] or []):

            temp_obj = dict(obj)
            temp_obj['Id'] = artist['Id']
            temp_obj['AlbumId'] = obj['Id']

            try:
                temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
            except TypeError:
                continue

            self.add_discography(*values(temp_obj, QU.update_discography_obj))
            self.jellyfin_db.update_parent_id(*values(temp_obj, QUEM.update_parent_album_obj))

    def artist_link(self, obj):

        ''' Assign main artists to album.
            Artist does not exist in jellyfin database, create the reference.
        '''
        for artist in (obj['AlbumArtists'] or []):

            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']

            try:
                temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
            except TypeError:

                try:
                    self.artist(self.server.jellyfin.get_item(temp_obj['Id']))
                    temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
                except Exception as error:
                    LOG.exception(error)
                    continue

            self.update_artist_name(*values(temp_obj, QU.update_artist_name_obj))
            self.link(*values(temp_obj, QU.update_link_obj))
            self.item_ids.append(temp_obj['Id'])

    @stop
    @jellyfin_item
    def song(self, item, e_item):

        ''' Update object to kodi.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'Song')
        update = True

        try:
            obj['SongId'] = e_item[0]
            obj['PathId'] = e_item[2]
            obj['AlbumId'] = e_item[3]
            obj['LibraryId'] = e_item[6]
            obj['LibraryName'] = self.jellyfin_db.get_view_name(obj['LibraryId'])
        except TypeError:
            update = False

            library = self.library or find_library(self.server, item)
            if not library:
                # This item doesn't belong to a whitelisted library
                return

            obj['SongId'] = self.create_entry_song()
            obj['LibraryId'] = library['Id']
            obj['LibraryName'] = library['Name']
            LOG.debug("SongId %s not found", obj['Id'])
        else:
            if self.validate_song(*values(obj, QU.get_song_by_id_obj)) is None:

                update = False
                LOG.info("SongId %s missing from kodi. repairing the entry.", obj['SongId'])

        self.get_song_path_filename(obj, API)

        obj['Rating'] = 0
        obj['Genres'] = obj['Genres'] or []
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Runtime'] = (obj['Runtime'] or 0) / 10000000.0
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['AlbumArtists'] = obj['AlbumArtists'] or []
        obj['Index'] = obj['Index'] or 0
        obj['Disc'] = obj['Disc'] or 1
        obj['EmbedCover'] = False
        obj['Comment'] = API.get_overview(obj['Comment'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'ArtworkMusic'), True)

        if obj['DateAdded']:
            obj['DateAdded'] = Local(obj['DateAdded']).split('.')[0].replace('T', " ")

        if obj['DatePlayed']:
            obj['DatePlayed'] = Local(obj['DatePlayed']).split('.')[0].replace('T', " ")

        obj['Index'] = obj['Disc'] * 2 ** 16 + obj['Index']

        if update:
            self.song_update(obj)
        else:
            self.song_add(obj)

        self.link_song_album(*values(obj, QU.update_song_album_obj))
        self.add_role(*values(obj, QU.update_role_obj))  # defaultt role
        self.song_artist_link(obj)
        self.song_artist_discography(obj)

        obj['strAlbumArtists'] = " / ".join(obj['AlbumArtists'])
        self.get_album_artist(*values(obj, QU.get_album_artist_obj))

        self.add_genres(*values(obj, QU.update_genre_song_obj))
        self.artwork.add(obj['Artwork'], obj['SongId'], "song")
        self.item_ids.append(obj['Id'])

        if obj['SongAlbumId'] is None:
            self.artwork.add(obj['Artwork'], obj['AlbumId'], "album")

        return not update

    def song_add(self, obj):

        ''' Add object to kodi.

            Verify if there's an album associated.
            If no album found, create a single's album
        '''
        obj['PathId'] = self.add_path(obj['Path'])

        try:
            obj['AlbumId'] = self.jellyfin_db.get_item_by_id(*values(obj, QUEM.get_item_song_obj))[0]
        except TypeError:

            try:
                if obj['SongAlbumId'] is None:
                    raise TypeError("No album id found associated?")

                self.album(self.server.jellyfin.get_item(obj['SongAlbumId']))
                obj['AlbumId'] = self.jellyfin_db.get_item_by_id(*values(obj, QUEM.get_item_song_obj))[0]
            except TypeError:
                self.single(obj)

        self.add_song(*values(obj, QU.add_song_obj))
        self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_song_obj))
        LOG.debug("ADD song [%s/%s/%s] %s: %s", obj['PathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title'])

    def song_update(self, obj):

        ''' Update object to kodi.
        '''
        self.update_path(*values(obj, QU.update_path_obj))

        self.update_song(*values(obj, QU.update_song_obj))
        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.debug("UPDATE song [%s/%s/%s] %s: %s", obj['PathId'], obj['AlbumId'], obj['SongId'], obj['Id'], obj['Title'])

    def get_song_path_filename(self, obj, api):

        ''' Get the path and filename and build it into protocol://path
        '''
        obj['Path'] = api.get_file_path(obj['Path'])
        obj['Filename'] = obj['Path'].rsplit('\\', 1)[1] if '\\' in obj['Path'] else obj['Path'].rsplit('/', 1)[1]

        if self.direct_path:

            if not validate(obj['Path']):
                raise PathValidationException("Failed to validate path. User stopped.")

            obj['Path'] = obj['Path'].replace(obj['Filename'], "")

        else:
            server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
            obj['Path'] = "%s/Audio/%s/" % (server_address, obj['Id'])
            obj['Filename'] = "stream.%s?static=true" % obj['Container']

    def song_artist_discography(self, obj):

        ''' Update the artist's discography.
        '''
        artists = []
        for artist in (obj['AlbumArtists'] or []):

            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']

            artists.append(temp_obj['Name'])

            try:
                temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
            except TypeError:

                try:
                    self.artist(self.server.jellyfin.get_item(temp_obj['Id']))
                    temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
                except Exception as error:
                    LOG.exception(error)
                    continue

            self.link(*values(temp_obj, QU.update_link_obj))
            self.item_ids.append(temp_obj['Id'])

            if obj['Album']:

                temp_obj['Title'] = obj['Album']
                temp_obj['Year'] = 0
                self.add_discography(*values(temp_obj, QU.update_discography_obj))

        obj['AlbumArtists'] = artists

    def song_artist_link(self, obj):

        ''' Assign main artists to song.
            Artist does not exist in jellyfin database, create the reference.
        '''
        for index, artist in enumerate(obj['ArtistItems'] or []):

            temp_obj = dict(obj)
            temp_obj['Name'] = artist['Name']
            temp_obj['Id'] = artist['Id']
            temp_obj['Index'] = index

            try:
                temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
            except TypeError:

                try:
                    self.artist(self.server.jellyfin.get_item(temp_obj['Id']))
                    temp_obj['ArtistId'] = self.jellyfin_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
                except Exception as error:
                    LOG.exception(error)
                    continue

            self.link_song_artist(*values(temp_obj, QU.update_song_artist_obj))
            self.item_ids.append(temp_obj['Id'])

    def single(self, obj):

        obj['AlbumId'] = self.create_entry_album()
        self.add_single(*values(obj, QU.add_single_obj))

    @stop
    @jellyfin_item
    def userdata(self, item, e_item):

        ''' This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
            Poster with progress bar
        '''

        obj = self.objects.map(item, 'SongUserData')

        try:
            obj['KodiId'] = e_item[0]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        obj['Rating'] = 0

        if obj['Media'] == 'song':

            if obj['DatePlayed']:
                obj['DatePlayed'] = Local(obj['DatePlayed']).split('.')[0].replace('T', " ")

            self.rate_song(*values(obj, QU.update_song_rating_obj))

        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.debug("USERDATA %s [%s] %s: %s", obj['Media'], obj['KodiId'], obj['Id'], obj['Title'])

    @stop
    @jellyfin_item
    def remove(self, item_id, e_item):

        ''' This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
            Poster with progress bar

            This should address single song scenario, where server doesn't actually
            create an album for the song.
        '''
        obj = {'Id': item_id}

        try:
            obj['KodiId'] = e_item[0]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        if obj['Media'] == 'song':

            self.remove_song(obj['KodiId'], obj['Id'])
            self.jellyfin_db.remove_wild_item(obj['Id'])

            for item in self.jellyfin_db.get_item_by_wild_id(*values(obj, QUEM.get_item_by_wild_obj)):
                if item[1] == 'album':

                    temp_obj = dict(obj)
                    temp_obj['ParentId'] = item[0]

                    if not self.jellyfin_db.get_item_by_parent_id(*values(temp_obj, QUEM.get_item_by_parent_song_obj)):
                        self.remove_album(temp_obj['ParentId'], obj['Id'])

        elif obj['Media'] == 'album':
            obj['ParentId'] = obj['KodiId']

            for song in self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_song_obj)):
                self.remove_song(song[1], obj['Id'])
            else:
                self.jellyfin_db.remove_items_by_parent_id(*values(obj, QUEM.delete_item_by_parent_song_obj))

            self.remove_album(obj['KodiId'], obj['Id'])

        elif obj['Media'] == 'artist':
            obj['ParentId'] = obj['KodiId']

            for album in self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_album_obj)):

                temp_obj = dict(obj)
                temp_obj['ParentId'] = album[1]

                for song in self.jellyfin_db.get_item_by_parent_id(*values(temp_obj, QUEM.get_item_by_parent_song_obj)):
                    self.remove_song(song[1], obj['Id'])
                else:
                    self.jellyfin_db.remove_items_by_parent_id(*values(temp_obj, QUEM.delete_item_by_parent_song_obj))
                    self.jellyfin_db.remove_items_by_parent_id(*values(temp_obj, QUEM.delete_item_by_parent_artist_obj))
                    self.remove_album(temp_obj['ParentId'], obj['Id'])
            else:
                self.jellyfin_db.remove_items_by_parent_id(*values(obj, QUEM.delete_item_by_parent_album_obj))

            self.remove_artist(obj['KodiId'], obj['Id'])

        self.jellyfin_db.remove_item(*values(obj, QUEM.delete_item_obj))

    def remove_artist(self, kodi_id, item_id):

        self.artwork.delete(kodi_id, "artist")
        self.delete(kodi_id)
        LOG.debug("DELETE artist [%s] %s", kodi_id, item_id)

    def remove_album(self, kodi_id, item_id):

        self.artwork.delete(kodi_id, "album")
        self.delete_album(kodi_id)
        LOG.debug("DELETE album [%s] %s", kodi_id, item_id)

    def remove_song(self, kodi_id, item_id):

        self.artwork.delete(kodi_id, "song")
        self.delete_song(kodi_id)
        LOG.debug("DELETE song [%s] %s", kodi_id, item_id)

    @jellyfin_item
    def get_child(self, item_id, e_item):

        ''' Get all child elements from tv show jellyfin id.
        '''
        obj = {'Id': item_id}
        child = []

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        except TypeError:
            return child

        obj['ParentId'] = obj['KodiId']

        for album in self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_album_obj)):

            temp_obj = dict(obj)
            temp_obj['ParentId'] = album[1]
            child.append((album[0],))

            for song in self.jellyfin_db.get_item_by_parent_id(*values(temp_obj, QUEM.get_item_by_parent_song_obj)):
                child.append((song[0],))

        return child
