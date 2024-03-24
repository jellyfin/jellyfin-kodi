from __future__ import division, absolute_import, print_function, unicode_literals

get_item = """
SELECT      kodi_id, kodi_fileid, kodi_pathid, parent_id, media_type,
            jellyfin_type, media_folder, jellyfin_parent_id
FROM        jellyfin
WHERE       jellyfin_id = ?
"""
get_item_obj = ["{Id}"]
get_item_series_obj = ["{SeriesId}"]
get_item_song_obj = ["{SongAlbumId}"]
get_item_id_by_parent = """
SELECT      jellyfin_id, kodi_id
FROM        jellyfin
WHERE       parent_id = ?
AND         media_type = ?
"""
get_item_id_by_parent_boxset_obj = ["{SetId}", "movie"]
get_item_by_parent = """
SELECT      jellyfin_id, kodi_id, kodi_fileid
FROM        jellyfin
WHERE       parent_id = ?
AND         media_type = ?
"""
get_item_by_media_folder = """
SELECT      jellyfin_id, jellyfin_type
FROM        jellyfin
WHERE       media_folder = ?
"""
get_item_by_parent_movie_obj = ["{KodiId}", "movie"]
get_item_by_parent_tvshow_obj = ["{ParentId}", "tvshow"]
get_item_by_parent_season_obj = ["{ParentId}", "season"]
get_item_by_parent_episode_obj = ["{ParentId}", "episode"]
get_item_by_parent_album_obj = ["{ParentId}", "album"]
get_item_by_parent_song_obj = ["{ParentId}", "song"]
get_item_by_wild = """
SELECT      kodi_id, media_type
FROM        jellyfin
WHERE       jellyfin_id LIKE ?
"""
get_item_by_wild_obj = ["{Id}"]
get_item_by_kodi = """
SELECT      jellyfin_id, parent_id, media_folder, jellyfin_type, checksum
FROM        jellyfin
WHERE       kodi_id = ?
AND         media_type = ?
"""
get_checksum = """
SELECT      jellyfin_id, checksum
FROM        jellyfin
WHERE       jellyfin_type = ?
"""
get_view_name = """
SELECT      view_name
FROM        view
WHERE       view_id = ?
"""
get_media_by_id = """
SELECT      jellyfin_type
FROM        jellyfin
WHERE       jellyfin_id = ?
"""
get_media_by_parent_id = """
SELECT      jellyfin_id, jellyfin_type, kodi_id, kodi_fileid
FROM        jellyfin
WHERE       jellyfin_parent_id = ?
"""
get_view = """
SELECT      *
FROM        view
WHERE       view_id = ?
"""
get_views = """
SELECT      *
FROM        view
"""
get_views_by_media = """
SELECT      *
FROM        view
WHERE       media_type = ?
"""
get_items_by_media = """
SELECT      jellyfin_id
FROM        jellyfin
WHERE       media_type = ?
"""
get_version = """
SELECT      idVersion
FROM        version
"""

add_reference = """
INSERT OR REPLACE INTO      jellyfin(jellyfin_id, kodi_id, kodi_fileid, kodi_pathid, jellyfin_type,
                            media_type, parent_id, checksum, media_folder, jellyfin_parent_id)
VALUES                      (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
add_reference_movie_obj = ["{Id}", "{MovieId}", "{FileId}", "{PathId}", "Movie", "movie", None, "{Checksum}", "{LibraryId}", "{JellyfinParentId}"]
add_reference_boxset_obj = ["{Id}", "{SetId}", None, None, "BoxSet", "set", None, "{Checksum}", None, None]
add_reference_tvshow_obj = ["{Id}", "{ShowId}", None, "{PathId}", "Series", "tvshow", None, "{Checksum}", "{LibraryId}", "{JellyfinParentId}"]
add_reference_season_obj = ["{Id}", "{SeasonId}", None, None, "Season", "season", "{ShowId}", None, None, None]
add_reference_pool_obj = ["{SeriesId}", "{ShowId}", None, "{PathId}", "Series", "tvshow", None, "{Checksum}", "{LibraryId}", None]
add_reference_episode_obj = ["{Id}", "{EpisodeId}", "{FileId}", "{PathId}", "Episode", "episode", "{SeasonId}", "{Checksum}", None, "{JellyfinParentId}"]
add_reference_mvideo_obj = ["{Id}", "{MvideoId}", "{FileId}", "{PathId}", "MusicVideo", "musicvideo", None, "{Checksum}", "{LibraryId}", "{JellyfinParentId}"]
add_reference_artist_obj = ["{Id}", "{ArtistId}", None, None, "{ArtistType}", "artist", None, "{Checksum}", "{LibraryId}", "{JellyfinParentId}"]
add_reference_album_obj = ["{Id}", "{AlbumId}", None, None, "MusicAlbum", "album", None, "{Checksum}", "{LibraryId}", "{JellyfinParentId}"]
add_reference_song_obj = ["{Id}", "{SongId}", None, "{PathId}", "Audio", "song", "{AlbumId}", "{Checksum}", "{LibraryId}", "{JellyfinParentId}"]
add_view = """
INSERT OR REPLACE INTO      view(view_id, view_name, media_type)
VALUES                      (?, ?, ?)
"""
add_version = """
INSERT OR REPLACE INTO      version(idVersion)
VALUES                      (?)
"""

update_reference = """
UPDATE      jellyfin
SET         checksum = ?
WHERE       jellyfin_id = ?
"""
update_reference_obj = ["{Checksum}", "{Id}"]
update_parent = """
UPDATE      jellyfin
SET         parent_id = ?
WHERE       jellyfin_id = ?
"""
update_parent_movie_obj = ["{SetId}", "{Id}"]
update_parent_episode_obj = ["{SeasonId}", "{Id}"]
update_parent_album_obj = ["{ArtistId}", "{AlbumId}"]


delete_item = """
DELETE FROM     jellyfin
WHERE           jellyfin_id = ?
"""
delete_item_obj = ["{Id}"]
delete_item_by_parent = """
DELETE FROM     jellyfin
WHERE           parent_id = ?
AND             media_type = ?
"""
delete_item_by_parent_tvshow_obj = ["{ParentId}", "tvshow"]
delete_item_by_parent_season_obj = ["{ParentId}", "season"]
delete_item_by_parent_episode_obj = ["{ParentId}", "episode"]
delete_item_by_parent_song_obj = ["{ParentId}", "song"]
delete_item_by_parent_artist_obj = ["{ParentId}", "artist"]
delete_item_by_parent_album_obj = ["{KodiId}", "album"]
delete_item_by_kodi = """
DELETE FROM     jellyfin
WHERE           kodi_id = ?
AND             media_type = ?
"""
delete_item_by_wild = """
DELETE FROM     jellyfin
WHERE           jellyfin_id LIKE ?
"""
delete_view = """
DELETE FROM     view
WHERE           view_id = ?
"""
delete_parent_boxset_obj = [None, "{Movie}"]
delete_media_by_parent_id = """
DELETE FROM     jellyfin
WHERE           jellyfin_parent_id = ?
"""
delete_version = """
DELETE FROM     version
"""

get_episode_kodi_parent_path_id = """
SELECT          sh.kodi_pathid
FROM            jellyfin e
JOIN            jellyfin s
ON              e.parent_id = s.kodi_id
JOIN            jellyfin sh
ON              s.parent_id = sh.kodi_id
WHERE           e.media_type = ?
AND             s.media_type = ?
AND             sh.media_type = ?
AND             e.jellyfin_id = ?;
"""
get_episode_kodi_parent_path_id_obj = ["episode", "season", "tvshow", "{Id}"]
