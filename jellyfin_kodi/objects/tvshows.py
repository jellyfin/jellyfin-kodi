# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

import sqlite3
from ntpath import dirname

from six.moves.urllib.parse import urlencode
from kodi_six.utils import py2_encode

from .. import downloader as server
from ..database import jellyfin_db, queries as QUEM
from ..helper import api, stop, validate, validate_bluray_dir, validate_dvd_dir, jellyfin_item, values, Local
from ..helper import LazyLogger
from ..helper.utils import find_library
from ..helper.exceptions import PathValidationException

from .obj import Objects
from .kodi import TVShows as KodiDb, queries as QU

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class TVShows(KodiDb):

    def __init__(self, server, jellyfindb, videodb, direct_path, library=None, update_library=False):

        self.server = server
        self.jellyfin = jellyfindb
        self.video = videodb
        self.direct_path = direct_path
        self.update_library = update_library

        self.jellyfin_db = jellyfin_db.JellyfinDatabase(jellyfindb.cursor)
        self.objects = Objects()
        self.item_ids = []
        self.library = library

        KodiDb.__init__(self, videodb.cursor)

    @stop
    @jellyfin_item
    def tvshow(self, item, e_item):

        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.

            If the show is empty, try to remove it.
            Process seasons.
            Apply series pooling.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'Series')
        update = True

        try:
            obj['ShowId'] = e_item[0]
            obj['PathId'] = e_item[2]
            obj['LibraryId'] = e_item[6]
            obj['LibraryName'] = self.jellyfin_db.get_view_name(obj['LibraryId'])
        except TypeError:
            update = False
            LOG.debug("ShowId %s not found", obj['Id'])

            library = self.library or find_library(self.server, item)
            if not library:
                # This item doesn't belong to a whitelisted library
                return

            obj['ShowId'] = self.create_entry()
            obj['LibraryId'] = library['Id']
            obj['LibraryName'] = library['Name']
        else:
            if self.get(*values(obj, QU.get_tvshow_obj)) is None:

                update = False
                LOG.info("ShowId %s missing from kodi. repairing the entry.", obj['ShowId'])

        obj['Path'] = API.get_file_path(obj['Path'])
        obj['Genres'] = obj['Genres'] or []
        obj['People'] = obj['People'] or []
        obj['Mpaa'] = API.get_mpaa(obj['Mpaa'])
        obj['Studios'] = [API.validate_studio(studio) for studio in (obj['Studios'] or [])]
        obj['Genre'] = " / ".join(obj['Genres'])
        obj['People'] = API.get_people_artwork(obj['People'])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['Studio'] = " / ".join(obj['Studios'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        if obj['Status'] != 'Ended':
            obj['Status'] = None

        self.get_path_filename(obj)

        if obj['Premiere']:
            obj['Premiere'] = str(Local(obj['Premiere'])).split('.')[0].replace('T', " ")

        tags = []
        tags.extend(obj['Tags'] or [])
        tags.append(obj['LibraryName'])

        if obj['Favorite']:
            tags.append('Favorite tvshows')

        obj['Tags'] = tags

        if update:
            self.tvshow_update(obj)
        else:
            self.tvshow_add(obj)

        self.link(*values(obj, QU.update_tvshow_link_obj))
        self.update_path(*values(obj, QU.update_path_tvshow_obj))
        self.add_tags(*values(obj, QU.add_tags_tvshow_obj))
        self.add_people(*values(obj, QU.add_people_tvshow_obj))
        self.add_genres(*values(obj, QU.add_genres_tvshow_obj))
        self.add_studios(*values(obj, QU.add_studios_tvshow_obj))
        self.artwork.add(obj['Artwork'], obj['ShowId'], "tvshow")
        self.item_ids.append(obj['Id'])

        season_episodes = {}

        for season in self.server.jellyfin.get_seasons(obj['Id'])['Items']:

            if season['SeriesId'] != obj['Id']:
                obj['SeriesId'] = season['SeriesId']
                self.item_ids.append(season['SeriesId'])

                try:
                    self.jellyfin_db.get_item_by_id(*values(obj, QUEM.get_item_series_obj))[0]

                    if self.update_library:
                        season_episodes[season['Id']] = season['SeriesId']
                except TypeError:

                    self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_pool_obj))
                    LOG.info("POOL %s [%s/%s]", obj['Title'], obj['Id'], obj['SeriesId'])
                    season_episodes[season['Id']] = season['SeriesId']

            try:
                self.jellyfin_db.get_item_by_id(season['Id'])[0]
                self.item_ids.append(season['Id'])
            except TypeError:
                self.season(season, obj['ShowId'])
        else:
            season_id = self.get_season(*values(obj, QU.get_season_special_obj))
            self.artwork.add(obj['Artwork'], season_id, "season")

        for season in season_episodes:
            for episodes in server.get_episode_by_season(season_episodes[season], season):

                for episode in episodes['Items']:
                    self.episode(episode)

    def tvshow_add(self, obj):

        ''' Add object to kodi.
        '''
        obj['RatingId'] = self.create_entry_rating()
        self.add_ratings(*values(obj, QU.add_rating_tvshow_obj))

        obj['Unique'] = self.create_entry_unique_id()
        self.add_unique_id(*values(obj, QU.add_unique_id_tvshow_obj))

        obj['TopPathId'] = self.add_path(obj['TopLevel'])

        if self.direct_path:
            # Normal way, we use the actual top path
            self.update_path(*values(obj, QU.update_path_toptvshow_obj))
        else:
            # Hack to allow cast information in add-on mode
            # We create a path on top of all others that holds mediaType and scrapper
            self.update_path(*values(obj, QU.update_path_toptvshow_addon_obj))
            temp_obj = dict()
            temp_obj['TopLevel'] = 'plugin://plugin.video.jellyfin/'
            temp_obj['TopPathId'] = self.add_path(temp_obj['TopLevel'])
            self.update_path(*values(temp_obj, QU.update_path_toptvshow_obj))
            self.update_path_parent_id(obj['TopPathId'], temp_obj['TopPathId'])

        obj['PathId'] = self.add_path(*values(obj, QU.get_path_obj))

        self.add(*values(obj, QU.add_tvshow_obj))
        self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_tvshow_obj))
        LOG.debug("ADD tvshow [%s/%s/%s] %s: %s", obj['TopPathId'], obj['PathId'], obj['ShowId'], obj['Title'], obj['Id'])

        self.update_path_parent_id(obj['PathId'], obj['TopPathId'])

    def tvshow_update(self, obj):

        ''' Update object to kodi.
        '''
        obj['RatingId'] = self.get_rating_id(*values(obj, QU.get_unique_id_tvshow_obj))
        self.update_ratings(*values(obj, QU.update_rating_tvshow_obj))

        obj['Unique'] = self.get_unique_id(*values(obj, QU.get_unique_id_tvshow_obj))
        self.update_unique_id(*values(obj, QU.update_unique_id_tvshow_obj))

        obj['TopPathId'] = self.get_path(obj['TopLevel'])

        self.update(*values(obj, QU.update_tvshow_obj))
        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.debug("UPDATE tvshow [%s/%s] %s: %s", obj['PathId'], obj['ShowId'], obj['Title'], obj['Id'])

        self.update_path_parent_id(obj['PathId'], obj['TopPathId'])

    def get_path_filename(self, obj):

        ''' Get the path and build it into protocol://path
        '''
        if self.direct_path:

            if '\\' in obj['Path']:
                obj['Path'] = "%s\\" % obj['Path']
                obj['TopLevel'] = "%s\\" % dirname(dirname(obj['Path']))
            elif 'smb://' in obj['Path'] or 'nfs://' in obj['Path']:
                obj['Path'] = "%s/" % obj['Path']
                obj['TopLevel'] = "%s/" % dirname(dirname(obj['Path']))
            else:
                obj['Path'] = "%s/" % obj['Path']
                obj['TopLevel'] = "plugin://plugin.video.jellyfin/"

            if not validate(obj['Path']):
                raise PathValidationException("Failed to validate path. User stopped.")
        else:
            obj['TopLevel'] = "plugin://plugin.video.jellyfin/%s/" % obj['LibraryId']
            obj['Path'] = "%s%s/" % (obj['TopLevel'], obj['Id'])

    @stop
    def season(self, item, show_id=None):

        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.

            If the show is empty, try to remove it.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'Season')

        obj['ShowId'] = show_id

        if obj['ShowId'] is None:

            try:
                obj['ShowId'] = self.jellyfin_db.get_item_by_id(*values(obj, QUEM.get_item_series_obj))[0]
            except (KeyError, TypeError) as error:
                LOG.error("Unable to add series %s", obj['SeriesId'])
                LOG.exception(error)

                return False

        obj['SeasonId'] = self.get_season(*values(obj, QU.get_season_obj))
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))

        if obj['Location'] != "Virtual":
            self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_season_obj))
            self.item_ids.append(obj['Id'])

        self.artwork.add(obj['Artwork'], obj['SeasonId'], "season")
        LOG.debug("UPDATE season [%s/%s] %s: %s", obj['ShowId'], obj['SeasonId'], obj['Title'] or obj['Index'], obj['Id'])

    @stop
    @jellyfin_item
    def episode(self, item, e_item):

        ''' If item does not exist, entry will be added.
            If item exists, entry will be updated.

            Create additional entry for widgets.
            This is only required for plugin/episode.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'Episode')
        update = True

        if obj['Location'] == "Virtual":
            LOG.info("Skipping virtual episode %s: %s", obj['Title'], obj['Id'])

            return

        elif obj['SeriesId'] is None:
            LOG.info("Skipping episode %s with missing SeriesId", obj['Id'])

            return

        try:
            obj['EpisodeId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['PathId'] = e_item[2]
        except TypeError:
            update = False
            LOG.debug("EpisodeId %s not found", obj['Id'])

            library = self.library or find_library(self.server, item)
            if not library:
                # This item doesn't belong to a whitelisted library
                return

            obj['EpisodeId'] = self.create_entry_episode()
        else:
            if self.get_episode(*values(obj, QU.get_episode_obj)) is None:

                update = False
                LOG.info("EpisodeId %s missing from kodi. repairing the entry.", obj['EpisodeId'])

        obj['Path'] = API.get_file_path(obj['Path'])
        obj['Index'] = obj['Index'] or -1
        obj['Writers'] = " / ".join(obj['Writers'] or [])
        obj['Directors'] = " / ".join(obj['Directors'] or [])
        obj['Plot'] = API.get_overview(obj['Plot'])
        obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
        obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
        obj['People'] = API.get_people_artwork(obj['People'] or [])
        obj['DateAdded'] = Local(obj['DateAdded']).split('.')[0].replace('T', " ")
        obj['DatePlayed'] = None if not obj['DatePlayed'] else Local(obj['DatePlayed']).split('.')[0].replace('T', " ")
        obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])
        obj['Artwork'] = API.get_all_artwork(self.objects.map(item, 'Artwork'))
        obj['Video'] = API.video_streams(obj['Video'] or [], obj['Container'])
        obj['Audio'] = API.audio_streams(obj['Audio'] or [])
        obj['Streams'] = API.media_streams(obj['Video'], obj['Audio'], obj['Subtitles'])

        self.get_episode_path_filename(obj)

        if obj['Premiere']:
            obj['Premiere'] = Local(obj['Premiere']).split('.')[0].replace('T', " ")

        if obj['Season'] is None:
            if obj['AbsoluteNumber']:

                obj['Season'] = 1
                obj['Index'] = obj['AbsoluteNumber']
            else:
                obj['Season'] = 0

        if obj['AirsAfterSeason']:

            obj['AirsBeforeSeason'] = obj['AirsAfterSeason']
            obj['AirsBeforeEpisode'] = 4096  # Kodi default number for afterseason ordering

        if obj['MultiEpisode']:
            obj['Title'] = "| %02d | %s" % (obj['MultiEpisode'], obj['Title'])

        if not self.get_show_id(obj):
            return False

        obj['SeasonId'] = self.get_season(*values(obj, QU.get_season_episode_obj))

        if update:
            self.episode_update(obj)
        else:
            self.episode_add(obj)

        self.update_path(*values(obj, QU.update_path_episode_obj))
        self.update_file(*values(obj, QU.update_file_obj))
        self.add_people(*values(obj, QU.add_people_episode_obj))
        self.add_streams(*values(obj, QU.add_streams_obj))
        self.add_playstate(*values(obj, QU.add_bookmark_obj))
        self.artwork.update(obj['Artwork']['Primary'], obj['EpisodeId'], "episode", "thumb")
        self.item_ids.append(obj['Id'])

        if not self.direct_path and obj['Resume']:

            temp_obj = dict(obj)
            temp_obj['Path'] = "plugin://plugin.video.jellyfin/"
            temp_obj['PathId'] = self.get_path(*values(temp_obj, QU.get_path_obj))
            temp_obj['FileId'] = self.add_file(*values(temp_obj, QU.add_file_obj))
            self.update_file(*values(temp_obj, QU.update_file_obj))
            self.add_playstate(*values(temp_obj, QU.add_bookmark_obj))

        return not update

    def episode_add(self, obj):

        ''' Add object to kodi.
        '''
        obj['RatingId'] = self.create_entry_rating()
        self.add_ratings(*values(obj, QU.add_rating_episode_obj))

        obj['Unique'] = self.create_entry_unique_id()
        self.add_unique_id(*values(obj, QU.add_unique_id_episode_obj))

        obj['PathId'] = self.add_path(*values(obj, QU.add_path_obj))
        obj['FileId'] = self.add_file(*values(obj, QU.add_file_obj))

        try:
            self.add_episode(*values(obj, QU.add_episode_obj))
        except sqlite3.IntegrityError:
            LOG.error("IntegrityError for %s", obj)
            obj['EpisodeId'] = self.create_entry_episode()

            return self.episode_add(obj)

        self.jellyfin_db.add_reference(*values(obj, QUEM.add_reference_episode_obj))

        parentPathId = self.jellyfin_db.get_episode_kodi_parent_path_id(*values(obj, QUEM.get_episode_kodi_parent_path_id_obj))
        if obj['PathId'] != parentPathId:
            LOG.debug("Setting episode pathParentId, episode %s, title %s, pathId %s, pathParentId %s", obj['Id'], obj['Title'], obj['PathId'], parentPathId)
            self.update_path_parent_id(obj['PathId'], parentPathId)

        LOG.debug("ADD episode [%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['Id'], obj['Title'])

    def episode_update(self, obj):

        ''' Update object to kodi.
        '''
        obj['RatingId'] = self.get_rating_id(*values(obj, QU.get_rating_episode_obj))
        self.update_ratings(*values(obj, QU.update_rating_episode_obj))

        obj['Unique'] = self.get_unique_id(*values(obj, QU.get_unique_id_episode_obj))
        self.update_unique_id(*values(obj, QU.update_unique_id_episode_obj))

        self.update_episode(*values(obj, QU.update_episode_obj))

        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        self.jellyfin_db.update_parent_id(*values(obj, QUEM.update_parent_episode_obj))
        LOG.debug("UPDATE episode [%s/%s] %s: %s", obj['PathId'], obj['FileId'], obj['Id'], obj['Title'])

    def get_episode_path_filename(self, obj):

        ''' Get the path and build it into protocol://path
        '''
        if '\\' in obj['Path']:
            obj['Filename'] = obj['Path'].rsplit('\\', 1)[1]
        else:
            obj['Filename'] = obj['Path'].rsplit('/', 1)[1]

        if self.direct_path:

            if not validate(obj['Path']):
                raise PathValidationException("Failed to validate path. User stopped.")

            obj['Path'] = obj['Path'].replace(obj['Filename'], "")

            '''check dvd directories and point it to ./VIDEO_TS/VIDEO_TS.IFO'''
            if validate_dvd_dir(obj['Path'] + obj['Filename']):
                obj['Path'] = obj['Path'] + obj['Filename'] + '/VIDEO_TS/'
                obj['Filename'] = 'VIDEO_TS.IFO'
                LOG.debug("DVD directory %s", obj['Path'])

            '''check bluray directories and point it to ./BDMV/index.bdmv'''
            if validate_bluray_dir(obj['Path'] + obj['Filename']):
                obj['Path'] = obj['Path'] + obj['Filename'] + '/BDMV/'
                obj['Filename'] = 'index.bdmv'
                LOG.debug("Bluray directory %s", obj['Path'])

            obj['FullFilePath'] = obj['Path'] + obj['Filename']

        else:
            # We need LibraryId
            library = self.library or find_library(self.server, obj)
            obj['LibraryId'] = library['Id']
            obj['Path'] = "plugin://plugin.video.jellyfin/%s/%s/" % (obj['LibraryId'], obj['SeriesId'])
            params = {
                'filename': py2_encode(obj['Filename'], 'utf-8'),
                'id': obj['Id'],
                'dbid': obj['EpisodeId'],
                'mode': "play"
            }
            obj['Filename'] = "%s?%s" % (obj['Path'], urlencode(params))
            obj['FullFilePath'] = obj['Filename']

    def get_show_id(self, obj):
        obj['ShowId'] = self.jellyfin_db.get_item_by_id(*values(obj, QUEM.get_item_series_obj))

        if obj['ShowId'] is None:

            try:
                self.tvshow(self.server.jellyfin.get_item(obj['SeriesId']))
                obj['ShowId'] = self.jellyfin_db.get_item_by_id(*values(obj, QUEM.get_item_series_obj))[0]
            except (TypeError, KeyError) as error:
                LOG.error("Unable to add series %s", obj['SeriesId'])
                LOG.exception(error)

                return False
        else:
            obj['ShowId'] = obj['ShowId'][0]

        self.item_ids.append(obj['SeriesId'])

        return True

    @stop
    @jellyfin_item
    def userdata(self, item, e_item):

        ''' This updates: Favorite, LastPlayedDate, Playcount, PlaybackPositionTicks
            Poster with progress bar

            Make sure there's no other bookmarks created by widget.
            Create additional entry for widgets. This is only required for plugin/episode.
        '''
        server_address = self.server.auth.get_server_info(self.server.auth.server_id)['address']
        API = api.API(item, server_address)
        obj = self.objects.map(item, 'EpisodeUserData')

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        if obj['Media'] == "tvshow":

            if obj['Favorite']:
                self.get_tag(*values(obj, QU.get_tag_episode_obj))
            else:
                self.remove_tag(*values(obj, QU.delete_tag_episode_obj))

        elif obj['Media'] == "episode":

            obj['Resume'] = API.adjust_resume((obj['Resume'] or 0) / 10000000.0)
            obj['Runtime'] = round(float((obj['Runtime'] or 0) / 10000000.0), 6)
            obj['PlayCount'] = API.get_playcount(obj['Played'], obj['PlayCount'])

            if obj['DatePlayed']:
                obj['DatePlayed'] = Local(obj['DatePlayed']).split('.')[0].replace('T', " ")

            if obj['DateAdded']:
                obj['DateAdded'] = Local(obj['DateAdded']).split('.')[0].replace('T', " ")

            self.add_playstate(*values(obj, QU.add_bookmark_obj))

            if not self.direct_path and not obj['Resume']:

                temp_obj = dict(obj)
                temp_obj['Filename'] = self.get_filename(*values(temp_obj, QU.get_file_obj))
                temp_obj['Path'] = "plugin://plugin.video.jellyfin/"
                self.remove_file(*values(temp_obj, QU.delete_file_obj))

            elif not self.direct_path and obj['Resume']:

                temp_obj = dict(obj)
                temp_obj['Filename'] = self.get_filename(*values(temp_obj, QU.get_file_obj))
                temp_obj['PathId'] = self.get_path("plugin://plugin.video.jellyfin/")
                temp_obj['FileId'] = self.add_file(*values(temp_obj, QU.add_file_obj))
                self.update_file(*values(temp_obj, QU.update_file_obj))
                self.add_playstate(*values(temp_obj, QU.add_bookmark_obj))

        self.jellyfin_db.update_reference(*values(obj, QUEM.update_reference_obj))
        LOG.debug("USERDATA %s [%s/%s] %s: %s", obj['Media'], obj['FileId'], obj['KodiId'], obj['Id'], obj['Title'])

    @stop
    @jellyfin_item
    def remove(self, item_id, e_item):

        ''' Remove showid, fileid, pathid, jellyfin reference.
            There's no episodes left, delete show and any possible remaining seasons
        '''
        obj = {'Id': item_id}

        try:
            obj['KodiId'] = e_item[0]
            obj['FileId'] = e_item[1]
            obj['ParentId'] = e_item[3]
            obj['Media'] = e_item[4]
        except TypeError:
            return

        if obj['Media'] == 'episode':

            temp_obj = dict(obj)
            self.remove_episode(obj['KodiId'], obj['FileId'], obj['Id'])
            season = self.jellyfin_db.get_full_item_by_kodi_id(*values(obj, QUEM.delete_item_by_parent_season_obj))

            try:
                temp_obj['Id'] = season[0]
                temp_obj['ParentId'] = season[1]
            except TypeError:
                return

            if not self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_episode_obj)):

                self.remove_season(obj['ParentId'], obj['Id'])
                self.jellyfin_db.remove_item(*values(temp_obj, QUEM.delete_item_obj))

            temp_obj['Id'] = self.jellyfin_db.get_item_by_kodi_id(*values(temp_obj, QUEM.get_item_by_parent_tvshow_obj))

            if not self.get_total_episodes(*values(temp_obj, QU.get_total_episodes_obj)):

                for season in self.jellyfin_db.get_item_by_parent_id(*values(temp_obj, QUEM.get_item_by_parent_season_obj)):
                    self.remove_season(season[1], obj['Id'])
                else:
                    self.jellyfin_db.remove_items_by_parent_id(*values(temp_obj, QUEM.delete_item_by_parent_season_obj))

                self.remove_tvshow(temp_obj['ParentId'], obj['Id'])
                self.jellyfin_db.remove_item(*values(temp_obj, QUEM.delete_item_obj))

        elif obj['Media'] == 'tvshow':
            obj['ParentId'] = obj['KodiId']

            for season in self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_season_obj)):

                temp_obj = dict(obj)
                temp_obj['ParentId'] = season[1]

                for episode in self.jellyfin_db.get_item_by_parent_id(*values(temp_obj, QUEM.get_item_by_parent_episode_obj)):
                    self.remove_episode(episode[1], episode[2], obj['Id'])
                else:
                    self.jellyfin_db.remove_items_by_parent_id(*values(temp_obj, QUEM.delete_item_by_parent_episode_obj))
            else:
                self.jellyfin_db.remove_items_by_parent_id(*values(obj, QUEM.delete_item_by_parent_season_obj))

            self.remove_tvshow(obj['KodiId'], obj['Id'])

        elif obj['Media'] == 'season':

            for episode in self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_episode_obj)):
                self.remove_episode(episode[1], episode[2], obj['Id'])
            else:
                self.jellyfin_db.remove_items_by_parent_id(*values(obj, QUEM.delete_item_by_parent_episode_obj))

            self.remove_season(obj['KodiId'], obj['Id'])

            if not self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.delete_item_by_parent_season_obj)):

                self.remove_tvshow(obj['ParentId'], obj['Id'])
                self.jellyfin_db.remove_item_by_kodi_id(*values(obj, QUEM.delete_item_by_parent_tvshow_obj))

        # Remove any series pooling episodes
        for episode in self.jellyfin_db.get_media_by_parent_id(obj['Id']):
            self.remove_episode(episode[2], episode[3], obj['Id'])
        else:
            self.jellyfin_db.remove_media_by_parent_id(obj['Id'])

        self.jellyfin_db.remove_item(*values(obj, QUEM.delete_item_obj))

    def remove_tvshow(self, kodi_id, item_id):

        self.artwork.delete(kodi_id, "tvshow")
        self.delete_tvshow(kodi_id)
        LOG.debug("DELETE tvshow [%s] %s", kodi_id, item_id)

    def remove_season(self, kodi_id, item_id):

        self.artwork.delete(kodi_id, "season")
        self.delete_season(kodi_id)
        LOG.debug("DELETE season [%s] %s", kodi_id, item_id)

    def remove_episode(self, kodi_id, file_id, item_id):

        self.artwork.delete(kodi_id, "episode")
        self.delete_episode(kodi_id, file_id)
        LOG.debug("DELETE episode [%s/%s] %s", file_id, kodi_id, item_id)

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

        for season in self.jellyfin_db.get_item_by_parent_id(*values(obj, QUEM.get_item_by_parent_season_obj)):

            temp_obj = dict(obj)
            temp_obj['ParentId'] = season[1]
            child.append(season[0])

            for episode in self.jellyfin_db.get_item_by_parent_id(*values(temp_obj, QUEM.get_item_by_parent_episode_obj)):
                child.append(episode[0])

        for episode in self.jellyfin_db.get_media_by_parent_id(obj['Id']):
            child.append(episode[0])

        return child
