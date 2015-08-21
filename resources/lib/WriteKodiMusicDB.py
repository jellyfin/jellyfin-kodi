# -*- coding: utf-8 -*-

#################################################################################################
# WriteKodiMusicDB
#################################################################################################

import sqlite3
from datetime import datetime
from ntpath import split as ntsplit

import xbmc
import xbmcgui
import xbmcaddon

from ClientInformation import ClientInformation
import Utils as utils
from API import API
from PlayUtils import PlayUtils
from ReadKodiDB import ReadKodiDB
from ReadEmbyDB import ReadEmbyDB
from TextureCache import TextureCache


class WriteKodiMusicDB():
    
    textureCache = TextureCache()
    kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])
    
    addonName = ClientInformation().getAddonName()
    WINDOW = xbmcgui.Window(10000)

    username = WINDOW.getProperty('currUser')
    userid = WINDOW.getProperty('userId%s' % username)
    server = WINDOW.getProperty('server%s' % username)

    directpath = utils.settings('useDirectPaths') == "true"

    def logMsg(self, msg, lvl = 1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))
        
    def addOrUpdateArtistToKodiLibrary(self, MBitem, connection, cursor):
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        embyId = MBitem["Id"]
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (embyId,))
        try:
            artistid = cursor.fetchone()[0]
        except:
            artistid = None
        
        ##### The artist details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)

        name = MBitem['Name']
        musicBrainzId = API().getProvider(MBitem, "musicBrainzArtist")
        genres = " / ".join(MBitem.get('Genres'))
        bio = API().getOverview(MBitem)

        # Associate artwork
        thumb = API().getArtwork(MBitem, "Primary")
        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb
        fanart = API().getArtwork(MBitem, "Backdrop")
        if fanart:
            fanart = "<fanart>%s</fanart>" % fanart    

        ##### UPDATE THE ARTIST #####
        if artistid:
            self.logMsg("UPDATE artist to Kodi library, Id: %s - Artist: %s" % (embyId, name), 1)

            query = "UPDATE artist SET strArtist = ?, strMusicBrainzArtistID = ?, strGenres = ?, strBiography = ?, strImage = ?, strFanart = ?, lastScraped = ?, dateadded = ? WHERE idArtist = ?"
            cursor.execute(query, (name, musicBrainzId, genres, bio, thumb, fanart, lastScraped, dateadded, artistid))

            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))

        ##### OR ADD THE ARTIST #####
        else:
            self.logMsg("ADD artist to Kodi library, Id: %s - Artist: %s" % (embyId, name), 1)
            
            #safety checks: It looks like Emby supports the same artist multiple times in the database while Kodi doesn't allow that. In case that happens we just merge the artist in the Kodi database.
            
            # Safety check 1: does the artist already exist?
            cursor.execute("SELECT idArtist FROM artist WHERE strArtist = ? COLLATE NOCASE", (name,))
            try:
                artistid = cursor.fetchone()[0]
                self.logMsg("Artist already exists in Kodi library - appending to existing object, Id: %s - Artist: %s - MusicBrainzId: %s - existing Kodi Id: %s" % (embyId, name, musicBrainzId, str(artistid)), 1)
            except: pass
            
            # Safety check 2: does the MusicBrainzArtistId already exist?
            cursor.execute("SELECT idArtist FROM artist WHERE strMusicBrainzArtistID = ?", (musicBrainzId,))
            try:
                artistid = cursor.fetchone()[0]
                self.logMsg("Artist already exists in Kodi library - appending to existing object, Id: %s - Artist: %s - MusicBrainzId: %s - existing Kodi Id: %s" % (embyId, name, musicBrainzId, str(artistid)), 1)
            except: pass
                
            if not artistid:
                # Create the artist
                cursor.execute("select coalesce(max(idArtist),0) as artistid from artist")
                artistid = cursor.fetchone()[0] + 1
                query = "INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, strImage, strFanart, lastScraped, dateAdded) values(?, ?, ?, ?, ?, ?, ?, ?, ?)"
                cursor.execute(query, (artistid, name, musicBrainzId, genres, bio, thumb, fanart, lastScraped, dateadded))

            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(query, (embyId, artistid, "artist", checksum))

        
        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), artistid, "artist", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), artistid, "artist", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), artistid, "artist", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), artistid, "artist", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), artistid, "artist", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), artistid, "artist", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), artistid, "artist", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), artistid, "artist", "fanart", cursor)

    def addOrUpdateAlbumToKodiLibrary(self, MBitem, connection, cursor):
        
        kodiVersion = self.kodiversion
        
        embyId = MBitem["Id"]
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (embyId,))
        try:
            albumid = cursor.fetchone()[0]
        except:
            albumid = None

        genres = MBitem.get('Genres')

        ##### The album details #####
        lastScraped = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)

        name = MBitem['Name']
        musicBrainzId = API().getProvider(MBitem, "musicBrainzAlbum")
        year = MBitem.get('ProductionYear')
        genre = " / ".join(genres)
        bio = API().getOverview(MBitem)
        
        MBartists = []
        for item in MBitem['AlbumArtists']:
            MBartists.append(item['Name'])
        artists = " / ".join(MBartists)

        # Associate the artwork
        thumb = API().getArtwork(MBitem, "Primary")
        if thumb:
            thumb = "<thumb>%s</thumb>" % thumb

        
        ##### UPDATE THE ALBUM #####
        if albumid:
            self.logMsg("UPDATE album to Kodi library, Id: %s - Title: %s" % (embyId, name), 1)

            if kodiVersion == 15 or kodiVersion == 16:
                # Kodi Isengard
                query = "UPDATE album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?, lastScraped = ?, dateAdded = ?, strReleaseType = ? WHERE idAlbum = ?"
                cursor.execute(query, (name, musicBrainzId, artists, year, genre, bio, thumb, lastScraped, dateadded, "album", albumid))
            else:
                # Kodi Gotham and Helix
                query = "UPDATE album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strArtists = ?, iYear = ?, strGenres = ?, strReview = ?, strImage = ?, lastScraped = ?, dateAdded = ? WHERE idAlbum = ?"
                cursor.execute(query, (name, musicBrainzId, artists, year, genre, bio, thumb, lastScraped, dateadded, albumid))

            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))

        ##### OR ADD THE ALBUM #####
        else:
            self.logMsg("ADD album to Kodi library, Id: %s - Title: %s" % (embyId, name), 1)
            
            # Safety check: does the strMusicBrainzAlbumID already exist?
            cursor.execute("SELECT idAlbum FROM album WHERE strMusicBrainzAlbumID = ?", (musicBrainzId,))
            try:
                albumid = cursor.fetchone()[0]
            except:
                # Create the album
                cursor.execute("select coalesce(max(idAlbum),0) as albumid from album")
                albumid = cursor.fetchone()[0] + 1
                if kodiVersion == 15 or kodiVersion == 16:
                    # Kodi Isengard
                    query = "INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strArtists, iYear, strGenres, strReview, strImage, lastScraped, dateAdded, strReleaseType) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (albumid, name, musicBrainzId, artists, year, genre, bio, thumb, lastScraped, dateadded, "album"))
                else:
                    # Kodi Gotham and Helix
                    query = "INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strArtists, iYear, strGenres, strReview, strImage, lastScraped, dateAdded) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                    cursor.execute(query, (albumid, name, musicBrainzId, artists, year, genre, bio, thumb, lastScraped, dateadded))

            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(query, (embyId, albumid, "album", checksum))


        # Add genres
        self.AddGenresToMedia(albumid, genres, "album", cursor)

        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), albumid, "album", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "BoxRear"), albumid, "album", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), albumid, "album", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), albumid, "album", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), albumid, "album", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), albumid, "album", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), albumid, "album", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), albumid, "album", "fanart", cursor)
        
        # Link album to artists
        if MBartists:
            album_artists = MBitem['AlbumArtists']
        else:
            album_artists = MBitem.get('ArtistItems', [])

        for artist in album_artists:
            cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (artist['Id'],))
            try:
                artistid = cursor.fetchone()[0]
            except: pass
            else:
                query = "INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist) values(?, ?, ?)"
                cursor.execute(query, (artistid, albumid, artist['Name']))
                # Update discography
                query = "INSERT OR REPLACE INTO discography(idArtist, strAlbum, strYear) values(?, ?, ?)"
                cursor.execute(query, (artistid, name, str(year)))
        
    def addOrUpdateSongToKodiLibrary(self, MBitem, connection, cursor):

        kodiVersion = self.kodiversion
        
        embyId = MBitem["Id"]
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (embyId,))
        try:
            songid = cursor.fetchone()[0]
        except:
            songid = None
        
        timeInfo = API().getTimeInfo(MBitem)
        userData = API().getUserData(MBitem)
        genres = MBitem.get('Genres')

        ##### The song details #####
        playcount = userData.get('PlayCount')
        lastplayed = userData.get('LastPlayedDate')
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)
        
        name = MBitem['Name']
        musicBrainzId = API().getProvider(MBitem, "musicBrainzTrackId")
        genre = " / ".join(genres)
        artists = " / ".join(MBitem.get('Artists'))
        track = MBitem.get('IndexNumber')
        year = MBitem.get('ProductionYear')
        bio = API().getOverview(MBitem)
        duration = timeInfo.get('TotalTime')

        # Get the path and filename
        playurl = PlayUtils().directPlay(MBitem)

        try:
            path, filename = ntsplit(playurl)
            if "/" in playurl:
                path = "%s/" % path
            elif "\\" in playurl:
                path = "%s\\" % path
        except: # playurl returned false - using server streaming path, because could not figure out plugin paths for music DB
            playurl = PlayUtils().directstream(MBitem, self.server, embyId, "Audio")
            filename = "stream.mp3"
            path = playurl.replace(filename, "")


        # Validate the path in database
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?", (path,))
        try:
            pathid = cursor.fetchone()[0]
        except:
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0] + 1
            query = "INSERT INTO path(idPath, strPath) values(?, ?)"
            cursor.execute(query, (pathid, path))

        # Get the album
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (MBitem.get("AlbumId"),))
        try:
            albumid = cursor.fetchone()[0]
        except:
            # No album found, create a single's album
            cursor.execute("select coalesce(max(idAlbum),0) as albumid from album")
            albumid = cursor.fetchone()[0] + 1
            if kodiVersion == 15 or kodiVersion == 16:
                # Kodi Isengard
                query = "INSERT INTO album(idAlbum, strArtists, strGenres, iYear, dateAdded, strReleaseType) values(?, ?, ?, ?, ?, ?)"
                cursor.execute(query, (albumid, artists, genre, year, dateadded, "single"))
            else:
                # Kodi Gotham and Helix
                query = "INSERT INTO album(idAlbum, strArtists, strGenres, iYear, dateAdded) values(?, ?, ?, ?, ?)"
                cursor.execute(query, (albumid, artists, genre, year, dateadded))

            # Link album to artists
            for artist in MBitem['ArtistItems']:
                cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (artist['Id'],))
                try:
                    artistid = cursor.fetchone()[0]
                except: pass
                else:
                    query = "INSERT OR REPLACE INTO album_artist(idArtist, idAlbum, strArtist) values(?, ?, ?)"
                    cursor.execute(query, (artistid, albumid, artist['Name']))


        ##### UPDATE THE SONG #####
        if songid:
            self.logMsg("UPDATE song to Kodi library, Id: %s - Title: %s" % (embyId, name), 1)

            query = "UPDATE song SET idAlbum = ?, strArtists = ?, strGenres = ?, strTitle = ?, iTrack = ?, iDuration = ?, iYear = ?, strFilename = ?, strMusicBrainzTrackID = ?, iTimesPlayed = ?, lastplayed = ? WHERE idSong = ?"
            cursor.execute(query, (albumid, artists, genre, name, track, duration, year, filename, musicBrainzId, playcount, lastplayed, songid))

            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))

        ##### OR ADD THE SONG #####
        else:
            self.logMsg("ADD song to Kodi library, Id: %s - Title: %s" % (embyId, name), 1)

            # Create the song
            cursor.execute("select coalesce(max(idSong),0) as songid from song")
            songid = cursor.fetchone()[0] + 1
            query = "INSERT INTO song(idSong, idAlbum, idPath, strArtists, strGenres, strTitle, iTrack, iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (songid, albumid, pathid, artists, genre, name, track, duration, year, filename, musicBrainzId, playcount, lastplayed))

            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(query, (embyId, songid, "song", checksum))

        
        # Add genres
        self.AddGenresToMedia(songid, genres, "song", cursor)
        
        # Link song to album
        if albumid:
            query = "INSERT OR REPLACE INTO albuminfosong(idAlbumInfoSong, idAlbumInfo, iTrack, strTitle, iDuration) values(?, ?, ?, ?, ?)"
            cursor.execute(query, (songid, albumid, track, name, duration))
        
        # Link song to artist
        for artist in MBitem.get('ArtistItems'):
            cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (artist['Id'],))
            try:
                artistid = cursor.fetchone()[0]
            except: pass
            else:
                query = "INSERT OR REPLACE INTO song_artist(idArtist, idSong, strArtist) values(?, ?, ?)"
                cursor.execute(query, (artistid, songid, artist['Name']))
        
        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), songid, "song", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), songid, "song", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), songid, "song", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), songid, "song", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), songid, "song", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), songid, "song", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), songid, "song", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), songid, "song", "fanart", cursor)
    
    def deleteItemFromKodiLibrary(self, id, connection, cursor):
        
        cursor.execute("SELECT kodi_id, media_type FROM emby WHERE emby_id=?", (id,))
        try:
            result = cursor.fetchone()
            kodi_id = result[0]
            media_type = result[1]
        except: pass
        else:
            if "artist" in media_type:
                self.logMsg("Deleting artist from Kodi library, Id: %s" % id, 1)
                cursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodi_id,))
            elif "song" in media_type:
                self.logMsg("Deleting song from Kodi library, Id: %s" % id, 1)
                cursor.execute("DELETE FROM song WHERE idSong = ?", (kodi_id,))
            elif "album" in media_type:
                self.logMsg("Deleting album from Kodi library, Id: %s" % id, 1)
                cursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodi_id,))

            # Delete the record in emby table
            cursor.execute("DELETE FROM emby WHERE emby_id = ?", (id,))
                          
    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):

        if imageUrl:

            cacheimage = False

            cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodiId, mediaType, imageType,))
            try:
                url = cursor.fetchone()[0]
            except: # Image does not exists
                cacheimage = True
                self.logMsg("Adding Art Link for kodiId: %s (%s)" % (kodiId, imageUrl), 1)
                query = "INSERT INTO art(media_id, media_type, type, url) values(?, ?, ?, ?)"
                cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))
            else:
                if url != imageUrl:
                    cacheimage = True
                    self.logMsg("Updating Art Link for kodiId: %s (%s) -> (%s)" % (kodiId, url, imageUrl), 1)
                    query = "UPDATE art SET url = ? WHERE media_id = ? and media_type = ? and type = ?"
                    cursor.execute(query, (imageUrl, kodiId, mediaType, imageType))
            
            # Cache fanart textures in Kodi texture cache
            if cacheimage and "fanart" in imageType:
                self.textureCache.CacheTexture(imageUrl)
                     
    def AddGenresToMedia(self, id, genres, mediatype, cursor):

        if genres:
            
            for genre in genres:

                cursor.execute("SELECT idGenre as idGenre FROM genre WHERE strGenre = ? COLLATE NOCASE", (genre,))
                try:
                    idGenre = cursor.fetchone()[0]
                except: # Create the genre
                    cursor.execute("select coalesce(max(idGenre),0) as idGenre from genre")
                    idGenre = cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    cursor.execute(query, (idGenre, genre))
                finally: # Assign the genre to item
                    if "album" in mediatype:
                        query = "INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) values(?, ?)"
                        cursor.execute(query, (idGenre, id))
                    elif "song" in mediatype:
                        query = "INSERT OR REPLACE INTO song_genre(idGenre, idSong) values(?, ?)"
                        cursor.execute(query, (idGenre, id))

    def updateUserdata(self, userdata, connection, cursor):
        # This updates: LastPlayedDate, Playcount
        embyId = userdata['ItemId']
        MBitem = ReadEmbyDB().getItem(embyId)

        if not MBitem:
            self.logMsg("UPDATE userdata to Kodi library FAILED, Item %s not found on server!" % embyId, 1)
            return

        # Get details
        checksum = API().getChecksum(MBitem)
        userdata = API().getUserData(MBitem)

        # Find the Kodi Id
        cursor.execute("SELECT kodi_id, media_type FROM emby WHERE emby_id = ?", (embyId,))
        try:
            result = cursor.fetchone()
            kodiid = result[0]
            mediatype = result[1]
            self.logMsg("Found embyId: %s in database - kodiId: %s type: %s" % (embyId, kodiid, mediatype), 1)
        except:
            self.logMsg("Id: %s not found in the emby database table." % embyId, 1)
        else:
            if mediatype in ("song"):
                playcount = userdata['PlayCount']
                dateplayed = userdata['LastPlayedDate']

                query = "UPDATE song SET iTimesPlayed = ?, lastplayed = ? WHERE idSong = ?"
                cursor.execute(query, (playcount, dateplayed, kodiid))

                #update the checksum in emby table
                query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
                cursor.execute(query, (checksum, embyId))