# -*- coding: utf-8 -*-

##################################################################################################

import json
import logging
import urllib

import downloader as server
from obj import Objects
from kodi import Movies as KodiDb, queries as QU
from database import emby_db, queries as QUEM
from helper import api, catch, stop, validate, emby_item, library_check, values

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Movies(KodiDb):

    def __init__(self, server, embydb, videodb, direct_path):

        self.server = server
        self.emby = embydb
        self.video = videodb
        self.direct_path = direct_path

        self.emby_db = emby_db.EmbyDatabase(embydb.cursor)
        self.objects = Objects()

        KodiDb.__init__(self, videodb.cursor)

    def __getitem__(self, key):

        if key == 'Movie':
            return self.movie
        elif key == 'BoxSet':
            return self.boxset
        elif key == 'UserData':
            return self.userdata
        elif key in 'Removed':
            return self.remove

    @stop()
    @emby_item()
    @library_check()
    def movie(self, item, e_item, library):
        
        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.
        '''
        API = api.API(item, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Movie')
        update = True

        try:
            obj['MovieId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        except TypeError as error:

            update = False
            LOG.debug("MovieId %s not found", obj['Id'])
            obj['MovieId'] = self.create_entry()
        else:
            if self.get(*values(obj, QU.get_movie_obj)) is None:

                update = False
                LOG.info("MovieId %s missing from kodi. repairing the entry.", obj['MovieId'])


        obj['Path'] = API.get_file_path(obj['Path'])
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Genres'] = obj['Genres'] or []
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['People'] = obj['People'] or []
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = API.get_people_artwork(obj['People'])
        obj['DateAdded'] = obj['DateAdded'].split('.')[0].replace('T', " ")
        obj['DatePlayed'] = (obj['DatePlayed'] or obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])

        self.get_path_filename(obj)
        self.trailer(obj)

        if obj['Countries']:
            self.add_countries(*values(obj, QU.update_country_obj))

        tags = []
        tags.extend(obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite movies')

        obj['Tags'] = tags


        if update:
            self.movie_update(obj)
        else:
            self.movie_add(obj)


        self.update_path(*values(obj, QU.update_path_movie_obj))
        self.update_file(*values(obj, QU.update_file_obj))
        self.add_tags(*values(obj, QU.add_tags_movie_obj))
        self.add_genres(*values(obj, QU.add_genres_movie_obj))
        self.add_studios(*values(obj, QU.add_studios_movie_obj))
        self.add_playstate(*values(obj, QU.add_bookmark_obj))
        self.add_people(*values(obj, QU.add_people_movie_obj))
        self.add_streams(*values(obj, QU.add_streams_obj))
        self.artwork.add(obj['Artwork'], obj['MovieId'], "movie")

    def movie_add(self, obj):

        ''' Add object to kodi.
        '''
        obj['RatingId'] = self.create_entry_rating()
        self.add_ratings(*values(obj, QU.add_rating_movie_obj))

        obj['Unique'] = self.create_entry_unique_id()
        self.add_unique_id(*values(obj, QU.add_unique_id_movie_obj))

        obj['PathId'] = self.add_path(*values(obj, QU.add_path_obj))
        obj['FileId'] = self.add_file(*values(obj, QU.add_file_obj))

        self.add(*values(obj, QU.add_movie_obj))
        self.emby_db.add_reference(*values(obj, QUEM.add_reference_movie_obj))
        LOG.info("ADD movie [%s/%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['MovieId'], obj['Id'], obj['Title'])

    def movie_update(self, obj):

        ''' Update object to kodi.
        '''
        obj['RatingId'] = self.get_rating_id(*values(obj, QU.get_rating_movie_obj))
        self.update_ratings(*values(obj, QU.update_rating_movie_obj))

        obj['Unique'] = self.get_unique_id(*values(obj, QU.get_unique_id_movie_obj))
        self.update_unique_id(*values(obj, QU.update_unique_id_movie_obj))

        self.update(*values(obj, QU.update_movie_obj))
        self.emby_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.info("UPDATE movie [%s/%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['MovieId'], obj['Id'], obj['Title'])

    def trailer(self, obj):

        try:
            if obj['LocalTrailer']:

                trailer = self.server['api'].get_local_trailers(obj['Id'])
                obj['Trailer'] = "plugin://plugin.video.emby/trailer?id=%s&mode=play" % trailer[0]['Id']

            elif obj['Trailer']:
                obj['Trailer'] = "plugin://plugin.video.youtube/play/?video_id=%s" % obj['Trailer'].rsplit('=', 1)[1]
        except Exception as error:

            LOG.error("Failed to get trailer: %s", error)
            obj['Trailer'] = None

    def get_path_filename(self, obj):

        ''' Get the path and filename and build it into protocol://path
        '''
        obj['Filename'] = obj['Path'].rsplit('\\', 1)[1] if '\\' in obj['Path'] else obj['Path'].rsplit('/', 1)[1]

        if self.direct_path:

            if not validate(obj['Path']):
                raise Exception("Failed to validate path. User stopped.")

            obj['Path'] = obj['Path'].replace(obj['Filename'], "")

        else:
            obj['Path'] = "plugin://plugin.video.emby.movies/"
            params = {
                'filename': obj['Filename'].encode('utf-8'),
                'id': obj['Id'],
                'dbid': obj['MovieId'],
                'mode': "play"
            }
            obj['Filename'] = "%s?%s" % (obj['Path'], urllib.urlencode(params))


    @stop()
    @emby_item()
    def boxset(self, item, e_item):
                
        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.

            Process movies inside boxset.
            Process removals from boxset.
        '''
        API = api.API(item, self.server['auth/server-address'])
        obj = self.objects.map(item, 'Boxset')

        obj['Overview'] = API.get_overview(obj['Overview'])

        try:
            obj['SetId'] = e_item[0]
            self.update_boxset(*values(obj, QU.update_set_obj))
        except TypeError as error:

            LOG.debug("SetId %s not found", obj['Id'])
            obj['SetId'] = self.add_boxset(*values(obj, QU.add_set_obj))

        self.boxset_current(obj)
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        for movie in obj['Current']:

            temp_obj = dict(obj)
            temp_obj['Movie'] = movie
            temp_obj['MovieId'] = obj['Current'][temp_obj['Movie']]
            self.remove_from_boxset(*values(temp_obj, QU.delete_movie_set_obj))
            self.emby_db.update_parent_id(*values(temp_obj, QUEM.delete_parent_boxset_obj))
            LOG.info("DELETE from boxset [%s] %s: %s", temp_obj['SetId'], temp_obj['Title'], temp_obj['MovieId'])

        self.artwork.add(obj['Artwork'], obj['SetId'], "set")
        self.emby_db.add_reference(*values(obj, QUEM.add_reference_boxset_obj))
        LOG.info("UPDATE boxset [%s] %s", obj['SetId'], obj['Title'])

    def boxset_current(self, obj):

        ''' Add or removes movies based on the current movies found in the boxset.
        '''
        obj['Current'] = []
        try:
            movies = dict(self.emby_db.get_item_id_by_parent_id(*values(obj, QUEM.get_item_id_by_parent_boxset_obj)))
        except ValueError:
            movies = {}

        for movie in movies:
            obj['Current'].append(movie)


        for all_movies in server.get_movies_by_boxset(obj['Id']):
            for movie in all_movies['Items']:

                temp_obj = dict(obj)
                temp_obj['Title'] = movie['Name']
                temp_obj['Id'] = movie['Id']

                try:
                    temp_obj['MovieId'] = self.emby_db.get_item_by_id(*values(temp_obj, QUEM.get_item_obj))[0]
                except TypeError:
                    LOG.info("Failed to process %s to boxset.", temp_obj['Title'])

                    continue

                if temp_obj['Id'] not in movies:

                    self.set_boxset(*values(temp_obj, QU.update_movie_set_obj))
                    self.emby_db.update_parent_id(*values(temp_obj, QUEM.update_parent_movie_obj))
                    LOG.info("ADD to boxset [%s/%s] %s: %s to boxset", temp_obj['SetId'], temp_obj['MovieId'], temp_obj['Title'], temp_obj['Id'])
                else:
                    obj['Current'].remove(temp_obj['Id'])

    def boxsets_reset(self):

        ''' Special function to remove all existing boxsets.
        '''
        boxsets = self.emby_db.get_items_by_media('set')
        for boxset in boxsets:
            self.remove(boxset[0])

    @stop()
    @emby_item()
    def userdata(self, item, e_item):
        
        ''' This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
            Poster with progress bar
        '''
        API = api.API(item, self.server['auth/server-address'])
        obj = self.objects.map(item, 'MovieUserData')

        try:
            obj['MovieId'] = e_item[0]
            obj['FileId'] = e_item[1]
        except TypeError:
            return

        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])

        if obj['DatePlayed']:
            obj['DatePlayed'] = obj['DatePlayed'].split('.')[0].replace('T', " ")

        if obj['Favorite']:
            self.get_tag(*values(obj, QU.get_tag_movie_obj))
        else:
            self.remove_tag(*values(obj, QU.delete_tag_movie_obj))

        LOG.debug("New resume point %s: %s", obj['Id'], obj['Resume'])
        self.add_playstate(*values(obj, QU.add_bookmark_obj))
        self.emby_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.info("USERDATA movie [%s/%s] %s: %s", obj['FileId'], obj['MovieId'], obj['Id'], obj['Title'])

    @stop()
    @emby_item()
    def remove(self, item_id, e_item):

        ''' Remove movieid, fileid, emby reference.
            Remove artwork, boxset
        '''
        obj = {'Id': item_id}

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        self.artwork.delete(obj['KodiId'], obj['Media'])

        if obj['Media'] == 'movie':
            self.delete(*values(obj, QU.delete_movie_obj))
        elif obj['Media'] == 'set':

            for movie in self.emby_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_movie_obj)):
                
                temp_obj = dict(obj)
                temp_obj['MovieId'] = movie[1]
                temp_obj['Movie'] = movie[0]
                self.remove_from_boxset(*values(temp_obj, QU.delete_movie_set_obj))
                self.emby_db.update_parent_id(*values(temp_obj, QUEM.delete_parent_boxset_obj))

            self.delete_boxset(*values(obj, QU.delete_set_obj))

        self.emby_db.remove_item(*values(obj, QUEM.delete_item_obj))
        LOG.info("DELETE %s [%s/%s] %s", obj['Media'], obj['FileId'], obj['KodiId'], obj['Id'])
