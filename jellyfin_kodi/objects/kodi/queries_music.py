from __future__ import division, absolute_import, print_function, unicode_literals

create_artist = """
SELECT      coalesce(max(idArtist), 1)
FROM        artist
"""
create_album = """
SELECT      coalesce(max(idAlbum), 0)
FROM        album
"""
create_song = """
SELECT      coalesce(max(idSong), 0)
FROM        song
"""
create_genre = """
SELECT      coalesce(max(idGenre), 0)
FROM        genre
"""


get_artist = """
SELECT      idArtist, strArtist
FROM        artist
WHERE       strMusicBrainzArtistID = ?
"""
get_artist_obj = ["{ArtistId}", "{Name}", "{UniqueId}"]
get_artist_by_name = """
SELECT      idArtist
FROM        artist
WHERE       strArtist = ?
            COLLATE NOCASE
"""
get_artist_by_id = """
SELECT      *
FROM        artist
WHERE       idArtist = ?
"""
get_artist_by_id_obj = ["{ArtistId}"]
get_album_by_id = """
SELECT      *
FROM        album
WHERE       idAlbum = ?
"""
get_album_by_id_obj = ["{AlbumId}"]
get_song_by_id = """
SELECT      *
FROM        song
WHERE       idSong = ?
"""
get_song_by_id_obj = ["{SongId}"]
get_album = """
SELECT      idAlbum
FROM        album
WHERE       strMusicBrainzAlbumID = ?
"""
get_album_obj = ["{AlbumId}", "{Title}", "{UniqueId}", "{Artists}", "album"]
get_album_obj82 = ["{AlbumId}", "{Title}", "{UniqueId}", "{Artists}", "album", "{DateAdded}"]
get_album_by_name = """
SELECT      idAlbum, strArtists
FROM        album
WHERE       strAlbum = ?
"""
get_album_by_name72 = """
SELECT      idAlbum, strArtistDisp
FROM        album
WHERE       strAlbum = ?
"""
get_album_artist = """
SELECT      strArtists
FROM        album
WHERE       idAlbum = ?
"""
get_album_artist72 = """
SELECT      strArtistDisp
FROM        album
WHERE       idAlbum = ?
"""
get_album_artist_obj = ["{AlbumId}", "{strAlbumArtists}"]
get_genre = """
SELECT      idGenre
FROM        genre
WHERE       strGenre = ?
            COLLATE NOCASE
"""
get_total_episodes = """
SELECT      totalCount
FROM        tvshowcounts
WHERE       idShow = ?
"""


add_artist = """
INSERT INTO     artist(idArtist, strArtist, strMusicBrainzArtistID)
VALUES          (?, ?, ?)
"""
add_album = """
INSERT INTO     album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType)
VALUES          (?, ?, ?, ?)
"""
add_album72 = """
INSERT INTO     album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType, bScrapedMBID)
VALUES          (?, ?, ?, ?, 1)
"""
add_album82 = """
INSERT INTO     album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType, bScrapedMBID, DateAdded)
VALUES          (?, ?, ?, ?, 1, ?)
"""
add_single = """
INSERT INTO     album(idAlbum, strGenres, iYear, strReleaseType)
VALUES          (?, ?, ?, ?)
"""
add_single74 = """
INSERT INTO     album(idAlbum, strGenres, strReleaseDate, strReleaseType)
VALUES          (?, ?, ?, ?)
"""
add_single_obj = ["{AlbumId}", "{Genre}", "{Year}", "single"]
add_song = """
INSERT INTO     song(idSong, idAlbum, idPath, strArtists, strGenres, strTitle, iTrack,
                iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed,
                rating, comment, dateAdded)
VALUES          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
add_song72 = """
INSERT INTO     song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack,
                iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed,
                rating, comment, dateAdded)
VALUES          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
add_song74 = """
INSERT INTO     song(idSong, idAlbum, idPath, strArtistDisp, strGenres, strTitle, iTrack,
                iDuration, strReleaseDate, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed,
                rating, comment, dateAdded)
VALUES          (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""
add_song_obj = ["{SongId}", "{AlbumId}", "{PathId}", "{Artists}", "{Genre}", "{Title}", "{Index}",
                "{Runtime}", "{Year}", "{Filename}", "{UniqueId}", "{PlayCount}", "{DatePlayed}", "{Rating}",
                "{Comment}", "{DateAdded}"]
add_genre = """
INSERT INTO     genre(idGenre, strGenre)
VALUES          (?, ?)
"""
add_genres_obj = ["{AlbumId}", "{Genres}", "album"]


update_path = """
UPDATE      path
SET         strPath = ?
WHERE       idPath = ?
"""
update_path_obj = ["{Path}", "{PathId}"]
update_role = """
INSERT OR REPLACE INTO      role(idRole, strRole)
VALUES                      (?, ?)
"""
update_role_obj = [1, "Composer"]
update_artist_name = """
UPDATE      artist
SET         strArtist = ?
WHERE       idArtist = ?
"""
update_artist_name_obj = ["{Name}", "{ArtistId}"]
update_artist74 = """
UPDATE      artist
SET         strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?, lastScraped = ?
WHERE       idArtist = ?
"""
update_artist82 = """
UPDATE      artist
SET         strGenres = ?, strBiography = ?, strImage = ?, lastScraped = ?
WHERE       idArtist = ?
"""
update_link = """
INSERT OR REPLACE INTO      album_artist(idArtist, idAlbum, strArtist)
VALUES                      (?, ?, ?)
"""
update_link_obj = ["{ArtistId}", "{AlbumId}", "{Name}"]
update_discography = """
INSERT OR REPLACE INTO      discography(idArtist, strAlbum, strYear)
VALUES                      (?, ?, ?)
"""
update_discography_obj = ["{ArtistId}", "{Title}", "{Year}"]
update_album = """
UPDATE      album
SET         strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,
            iUserrating = ?, lastScraped = ?, strReleaseType = ?
WHERE       idAlbum = ?
"""
update_album72 = """
UPDATE      album
SET         strArtistDisp = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?,
            iUserrating = ?, lastScraped = ?, bScrapedMBID = 1, strReleaseType = ?
WHERE       idAlbum = ?
"""
update_album74 = """
UPDATE      album
SET         strArtistDisp = ?, strReleaseDate = ?, strGenres = ?, strReview = ?, strImage = ?,
            iUserrating = ?, lastScraped = ?, bScrapedMBID = 1, strReleaseType = ?
WHERE       idAlbum = ?
"""
update_album_obj = ["{Artists}", "{Year}", "{Genre}", "{Bio}", "{Thumb}", "{Rating}", "{LastScraped}", "album", "{AlbumId}"]
update_album_artist = """
UPDATE      album
SET         strArtists = ?
WHERE       idAlbum = ?
"""
update_album_artist72 = """
UPDATE      album
SET         strArtistDisp = ?
WHERE       idAlbum = ?
"""
update_song = """
UPDATE      song
SET         idAlbum = ?, strArtists = ?, strGenres = ?, strTitle = ?, iTrack = ?,
            iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,
            rating = ?, comment = ?, dateAdded = ?
WHERE       idSong = ?
"""
update_song72 = """
UPDATE      song
SET         idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?,
            iDuration = ?, iYear = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,
            rating = ?, comment = ?, dateAdded = ?
WHERE       idSong = ?
"""
update_song74 = """
UPDATE      song
SET         idAlbum = ?, strArtistDisp = ?, strGenres = ?, strTitle = ?, iTrack = ?,
            iDuration = ?, strReleaseDate = ?, strFilename = ?, iTimesPlayed = ?, lastplayed = ?,
            rating = ?, comment = ?, dateAdded = ?
WHERE       idSong = ?
"""
update_song_obj = ["{AlbumId}", "{Artists}", "{Genre}", "{Title}", "{Index}", "{Runtime}", "{Year}",
                                "{Filename}", "{PlayCount}", "{DatePlayed}", "{Rating}", "{Comment}",
                                "{DateAdded}", "{SongId}"]
update_song_artist = """
INSERT OR REPLACE INTO      song_artist(idArtist, idSong, idRole, iOrder, strArtist)
VALUES                      (?, ?, ?, ?, ?)
"""
update_song_artist_obj = ["{ArtistId}", "{SongId}", 1, "{Index}", "{Name}"]
update_song_album = """
INSERT OR REPLACE INTO      albuminfosong(idAlbumInfoSong, idAlbumInfo, iTrack,
                            strTitle, iDuration)
VALUES                      (?, ?, ?, ?, ?)
"""
update_song_album_obj = ["{SongId}", "{AlbumId}", "{Index}", "{Title}", "{Runtime}"]
update_song_rating = """
UPDATE      song
SET         iTimesPlayed = ?, lastplayed = ?, rating = ?
WHERE       idSong = ?
"""
update_song_rating_obj = ["{PlayCount}", "{DatePlayed}", "{Rating}", "{KodiId}"]
update_genre_album = """
INSERT OR REPLACE INTO      album_genre(idGenre, idAlbum)
VALUES                      (?, ?)
"""
update_genre_song = """
INSERT OR REPLACE INTO      song_genre(idGenre, idSong)
VALUES                      (?, ?)
"""
update_genre_song_obj = ["{SongId}", "{Genres}", "song"]


delete_genres_album = """
DELETE FROM     album_genre
WHERE           idAlbum = ?
"""
delete_genres_song = """
DELETE FROM     song_genre
WHERE           idSong = ?
"""
delete_artist = """
DELETE FROM     artist
WHERE           idArtist = ?
"""
delete_album = """
DELETE FROM     album
WHERE           idAlbum = ?
"""
delete_song = """
DELETE FROM     song
WHERE           idSong = ?
"""
get_version = """
SELECT      idVersion
FROM        version
"""
update_versiontag = """
INSERT OR REPLACE INTO      versiontagscan(idVersion, iNeedsScan)
VALUES                      (?, 0)
"""
get_versiontagcount = """
SELECT COUNT    (*)
FROM            versiontagscan
"""
