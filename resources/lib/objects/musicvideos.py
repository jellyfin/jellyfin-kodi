# -*- coding: utf-8 -*-

##################################################################################################

import datetime
import logging
import re
import urllib

from obj import Objects
from kodi import MusicVideos as KodiDb, queries as QU
from database import emby_db, queries as QUEM
from helper import api, catch, stop, validate, library_check, emby_item, values

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class MusicVideos(KodiDb):

    def __init__(self, server, embydb, videodb, direct_path):

        self.server = server
        self.emby = embydb
        self.video = videodb
        self.direct_path = direct_path

        self.emby_db = emby_db.EmbyDatabase(embydb.cursor)
        self.objects = Objects()

        KodiDb.__init__(self, videodb.cursor)

    def __getitem__(self, key):

        if key == 'MusicVideo':
            return self.musicvideo
        elif key == 'UserData':
            return self.userdata
        elif key in 'Removed':
            return self.remove

    @stop()
    @emby_item()
    @library_check()
    def musicvideo(self, item, e_item, library):

        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.

            If we don't get the track number from Emby, see if we can infer it
            from the sortname attribute.
        '''
        API = api.API(item, self.server['auth/server-address'])
        obj = self.objects.map(item, 'MusicVideo')
        update = True

        try:
            obj['MvideoId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        except TypeError as error:

            update = False
            LOG.debug("MvideoId for %s not found", obj['Id'])
            obj['MvideoId'] = self.create_entry()
        else:
            if self.get(*values(obj, QU.get_musicvideo_obj)) is None:

                update = False
                LOG.info("MvideoId %s missing from kodi. repairing the entry.", obj['MvideoId'])

        obj['Path'] = API.get_file_path(obj['Path'])
        obj['LibraryId'] = library['Id']
        obj['LibraryName'] = library['Name']
        obj['Genres'] = obj['Genres'] or []
        obj['ArtistItems'] = obj['ArtistItems'] or []
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['DateAdded'] = obj['DateAdded'].split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else obj['DatePlayed'].split('.')[0].replace('T', " ")
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['Premiere'] = obj['Premiere'] or datetime.date(obj['Year'] or 2021, 1, 1)
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['Studio'] = " / ".join(obj['Studios'])
        obj['Artists'] = " / ".join(obj['Artists'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        self.get_path_filename(obj)

        if obj['Premiere']:
            obj['Premiere'] = str(obj['Premiere']).split('.')[0].replace('T', " ")

        for artist in obj['ArtistItems']:
            artist['Type'] = "Artist"

        obj['People'] = obj['People'] or [] + obj['ArtistItems']
        obj['People'] = API.get_people_artwork(obj['People'])

        if obj['Index'] is None and obj['SortTitle'] is not None:
            search = re.search(r'^\d+\s?', obj['SortTitle'])

            if search:
                obj['Index'] = search.group()

        tags = []
        tags.extend(obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite musicvideos')

        obj['Tags'] = tags


        if update:
            self.musicvideo_update(obj)
        else:
            self.musicvideo_add(obj)


        self.update_path(*values(obj, QU.update_path_mvideo_obj))
        self.update_file(*values(obj, QU.update_file_obj))
        self.add_tags(*values(obj, QU.add_tags_mvideo_obj))
        self.add_genres(*values(obj, QU.add_genres_mvideo_obj))
        self.add_studios(*values(obj, QU.add_studios_mvideo_obj))
        self.add_playstate(*values(obj, QU.add_bookmark_obj))
        self.add_people(*values(obj, QU.add_people_mvideo_obj))
        self.add_streams(*values(obj, QU.add_streams_obj))
        self.artwork.add(obj['Artwork'], obj['MvideoId'], "musicvideo")

    def musicvideo_add(self, obj):
        
        ''' Add object to kodi.
        '''
        obj['PathId'] = self.add_path(*values(obj, QU.add_path_obj))
        obj['FileId'] = self.add_file(*values(obj, QU.add_file_obj))

        self.add(*values(obj, QU.add_musicvideo_obj))
        self.emby_db.add_reference(*values(obj, QUEM.add_reference_mvideo_obj))
        LOG.info("ADD mvideo [%s/%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['MvideoId'], obj['Id'], obj['Title'])

    def musicvideo_update(self, obj):
        
        ''' Update object to kodi.
        '''
        self.update(*values(obj, QU.update_musicvideo_obj))
        self.emby_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.info("UPDATE mvideo [%s/%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['MvideoId'], obj['Id'], obj['Title'])

    def get_path_filename(self, obj):
        
        ''' Get the path and filename and build it into protocol://path
        '''
        obj['Filename'] = obj['Path'].rsplit('\\', 1)[1] if '\\' in obj['Path'] else obj['Path'].rsplit('/', 1)[1]

        if self.direct_path:

            if not validate(obj['Path']):
                raise Exception("Failed to validate path. User stopped.")

            obj['Path'] = obj['Path'].replace(obj['Filename'], "")

        else:
            obj['Path'] = "plugin://plugin.video.emby.musicvideos/"
            params = {
                'filename': obj['Filename'].encode('utf-8'),
                'id': obj['Id'],
                'dbid': obj['MvideoId'],
                'mode': "play"
            }
            obj['Filename'] = "%s?%s" % (obj['Path'], urllib.urlencode(params))


    @stop()
    @emby_item()
    def userdata(self, item, e_item):
        
        ''' This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
            Poster with progress bar
        '''
        API = api.API(item, self.server['auth/server-address'])
        obj = self.objects.map(item, 'MusicVideoUserData')

        try:
            obj['MvideoId'] = e_item[0]
            obj['FileId'] = e_item[1]
        except TypeError:
            return

        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])

        if obj['DatePlayed']:
            obj['DatePlayed'] = obj['DatePlayed'].split('.')[0].replace('T', " ")

        if obj['Favorite']:
            self.get_tag(*values(obj, QU.get_tag_mvideo_obj))
        else:
            self.remove_tag(*values(obj, QU.delete_tag_mvideo_obj))

        self.add_playstate(*values(obj, QU.add_bookmark_obj))
        self.emby_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.info("USERDATA mvideo [%s/%s] %s: %s", obj['FileId'], obj['MvideoId'], obj['Id'], obj['Title'])

    @stop()
    @emby_item()
    def remove(self, item_id, e_item):

        ''' Remove mvideoid, fileid, pathid, emby reference. 
        '''
        obj = {'Id': item_id}

        try:
            obj['MvideoId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        except TypeError:
            return

        self.artwork.delete(obj['MvideoId'], "musicvideo")
        self.delete(*values(obj, QU.delete_musicvideo_obj))

        if self.direct_path:
            self.remove_path(*values(obj, QU.delete_path_obj))

        self.emby_db.remove_item(*values(obj, QUEM.delete_item_obj))
        LOG.info("DELETE musicvideo %s [%s/%s] %s", obj['MvideoId'], obj['PathId'], obj['FileId'], obj['Id'])
