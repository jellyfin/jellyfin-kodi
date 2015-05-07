#################################################################################################
# WriteKodiVideoDB
#################################################################################################


import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import urllib
import sqlite3
import os
from decimal import Decimal

from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ReadKodiDB import ReadKodiDB
from ReadEmbyDB import ReadEmbyDB
from API import API
import Utils as utils

from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

addon = xbmcaddon.Addon(id='plugin.video.emby')
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))
dataPath = os.path.join(addondir,",musicfiles")


class WriteKodiMusicDB():
    


    def updatePlayCountFromKodi(self, id, type, playcount=0):
        #when user marks item watched from kodi interface update this in Emby
        
        utils.logMsg("Emby", "updatePlayCountFromKodi Called")
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        cursor.execute("SELECT emby_id FROM emby WHERE media_type=? AND kodi_id=?",(type,id))
        
        emby_id = cursor.fetchone()[0]
        cursor.close

        if(emby_id != None):
            addon = xbmcaddon.Addon(id='plugin.video.emby')   
            downloadUtils = DownloadUtils()       
            watchedurl = "{server}/mediabrowser/Users/{UserId}/PlayedItems/%s" % emby_id
            if playcount != 0:
                downloadUtils.downloadUrl(watchedurl, type="POST")
            else:
                downloadUtils.downloadUrl(watchedurl, type="DELETE")
        
    def addOrUpdateArtistToKodiLibrary( self, embyId ,connection, cursor):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        downloadUtils = DownloadUtils()
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(MBitem["Id"],))
        result = cursor.fetchone()
        if result != None:
            artistid = result[0]
        else:
            artistid = None
        

        #### The artist details #########
        name = utils.convertEncoding(MBitem["Name"])
        musicBrainsId = None
        if MBitem.get("ProviderIds"):
            if MBitem.get("ProviderIds").get("MusicBrainzArtist"):
                musicBrainsId = MBitem.get("ProviderIds").get("MusicBrainzArtist")
                
        genres = " / ".join(MBitem.get("Genres"))
        bio = utils.convertEncoding(API().getOverview(MBitem))
        dateadded = None
        if MBitem.get("DateCreated"):
            dateadded = MBitem["DateCreated"].split('.')[0].replace('T', " ")
            
        #safety check: does the musicbrainzartistId already exist?
        cursor.execute("SELECT idArtist FROM artist WHERE strMusicBrainzArtistID = ?",(musicBrainsId,))
        result = cursor.fetchone()
        if result != None:
            artistid = result[0]
        else:
            artistid = None
        
        ##### ADD THE ARTIST ############
        if artistid == None:
            
            utils.logMsg("ADD artist to Kodi library","Id: %s - Title: %s" % (embyId, name))

            #create the artist
            cursor.execute("select coalesce(max(idArtist),0) as artistid from artist")
            artistid = cursor.fetchone()[0]
            artistid = artistid + 1
            pathsql="insert into artist(idArtist, strArtist, strMusicBrainzArtistID, strGenres, strBiography, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (artistid, name, musicBrainsId, genres, bio, dateadded))
            
            #create the reference in emby table
            pathsql = "INSERT into emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(pathsql, (MBitem["Id"], artistid, "artist", API().getChecksum(MBitem)))
                        
        #### UPDATE THE ARTIST #####
        else:
            utils.logMsg("UPDATE artist to Kodi library","Id: %s - Title: %s" % (embyId, name))
            pathsql="update artist SET strArtist = ?, strMusicBrainzArtistID = ?, strGenres = ?, strBiography = ?,  dateAdded = ?  WHERE idArtist = ?"
            cursor.execute(pathsql, (name, musicBrainsId, genres, bio, dateadded, artistid))
            
            #update the checksum in emby table
            cursor.execute("UPDATE emby SET checksum = ? WHERE emby_id = ?", (API().getChecksum(MBitem),MBitem["Id"]))
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), artistid, "artist", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), artistid, "artist", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), artistid, "artist", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), artistid, "artist", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), artistid, "artist", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), artistid, "artist", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), artistid, "artist", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), artistid, "artist", "fanart", cursor)

    def addOrUpdateAlbumToKodiLibrary( self, embyId ,connection, cursor, isSingle=False):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        downloadUtils = DownloadUtils()
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(MBitem["Id"],))
        result = cursor.fetchone()
        if result != None:
            albumid = result[0]
        else:
            albumid = None
        

        #### The album details #########
        name = utils.convertEncoding(MBitem["Name"])
        
        MBartists = []
        for item in MBitem.get("AlbumArtists"):
            MBartists.append(item["Name"])

        artists = " / ".join(MBartists)
        year = MBitem.get("ProductionYear")
        musicBrainsId = None
        if MBitem.get("ProviderIds"):
            if MBitem.get("ProviderIds").get("MusicBrainzAlbum"):
                musicBrainsId = MBitem.get("ProviderIds").get("MusicBrainzAlbum")
                
        genres = " / ".join(MBitem.get("Genres"))
        bio = utils.convertEncoding(API().getOverview(MBitem))
        dateadded = None
        if MBitem.get("DateCreated"):
            dateadded = MBitem["DateCreated"].split('.')[0].replace('T', " ")
        
        if isSingle:
            releasetype = "single"
            name = None
        else:
            releasetype = "album"
        
        ##### ADD THE ALBUM ############
        if albumid == None:
            
            utils.logMsg("ADD album to Kodi library","Id: %s - Title: %s" % (embyId, name))
            
            #create the album
            cursor.execute("select coalesce(max(idAlbum),0) as albumid from album")
            albumid = cursor.fetchone()[0]
            albumid = albumid + 1
            pathsql="insert into album(idAlbum, strAlbum, strMusicBrainzAlbumID, strArtists, iYear, strGenres, dateAdded) values(?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (albumid, name, musicBrainsId, artists, year, genres, dateadded))
            
            #create the reference in emby table
            pathsql = "INSERT into emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(pathsql, (MBitem["Id"], albumid, "album", API().getChecksum(MBitem)))
                        
        #### UPDATE THE ALBUM #####
        else:
            utils.logMsg("UPDATE album to Kodi library","Id: %s - Title: %s" % (embyId, name))
            pathsql="update album SET strAlbum = ?, strMusicBrainzAlbumID = ?, strArtists = ?, strGenres = ?, iYear = ?,  dateAdded = ?  WHERE idAlbum = ?"
            cursor.execute(pathsql, (name, musicBrainsId, artists, genres, year, dateadded, albumid))
            
            #update the checksum in emby table
            cursor.execute("UPDATE emby SET checksum = ? WHERE emby_id = ?", (API().getChecksum(MBitem),MBitem["Id"]))
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), albumid, "album", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "BoxRear"), albumid, "album", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), albumid, "album", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), albumid, "album", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), albumid, "album", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), albumid, "album", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), albumid, "album", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), albumid, "album", "fanart", cursor)
        
        #link album to artist
        artistid = None
        for artist in MBitem.get("AlbumArtists"):
            cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(artist["Id"],))
            result = cursor.fetchone()
            if result:
                artistid = result[0]
                sql="INSERT OR REPLACE into album_artist(idArtist, idAlbum, strArtist) values(?, ?, ?)"
                cursor.execute(sql, (artistid, albumid, artist["Name"]))
                #update discography
                sql="INSERT OR REPLACE into discography(idArtist, strAlbum, strYear) values(?, ?, ?)"
                cursor.execute(sql, (artistid, name, str(year)))
        
        #return the album id
        return albumid
        
    def addOrUpdateSongToKodiLibrary( self, embyId ,connection, cursor):
        
        addon = xbmcaddon.Addon(id='plugin.video.emby')
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        userid = WINDOW.getProperty('userId%s' % username)
        server = WINDOW.getProperty('server%s' % username)
        downloadUtils = DownloadUtils()
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(MBitem["Id"],))
        result = cursor.fetchone()
        if result != None:
            songid = result[0]
        else:
            songid = None
        

        #### The song details #########
        name = utils.convertEncoding(MBitem["Name"])
        musicBrainzId = None
        if MBitem.get("ProviderIds"):
            if MBitem.get("ProviderIds").get("MusicBrainzTrackId"):
                musicBrainzId = MBitem.get("ProviderIds").get("MusicBrainzTrackId")
                
        genres = " / ".join(MBitem.get("Genres"))
        artists = " / ".join(MBitem.get("Artists"))
        track = MBitem.get("IndexNumber")
        duration = int(timeInfo.get('Duration'))*60
        year = MBitem.get("ProductionYear")
        bio = utils.convertEncoding(API().getOverview(MBitem))
        dateadded = None
        if MBitem.get("DateCreated"):
            dateadded = MBitem["DateCreated"].split('.')[0].replace('T', " ")
        
        if userData.get("LastPlayedDate") != None:
            lastplayed = userData.get("LastPlayedDate")
        else:
            lastplayed = None
        
        playcount = None
        if userData.get("PlayCount"):
            playcount = int(userData.get("PlayCount"))
            
        #get the album
        albumid = None
        if MBitem.get("AlbumId"):
            cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(MBitem.get("AlbumId"),))
            result = cursor.fetchone()
            if result:
                albumid = result[0]
        if not albumid:
            #no album = single in kodi, we need to create a single album for that
            albumid = self.addOrUpdateAlbumToKodiLibrary(MBitem["Id"],connection, cursor, True)

        playurl = PlayUtils().getPlayUrl(server, MBitem["Id"], MBitem)
        #for transcoding we need to create a fake strm file because I couldn't figure out how to set a http or plugin path in the music DB
        if playurl.startswith("http"):
            #create fake strm file
            filename = item["Id"] + ".strm"
            path = dataPath
            strmFile = os.path.join(dataPath,filename)
            text_file = open(strmFile, "w")
            text_file.writelines(playurl)
            text_file.close()
        else:
            #use the direct file path
            if "\\" in playurl:
                filename = playurl.rsplit("\\",1)[-1]
                path = playurl.replace(filename,"")
            elif "/" in playurl:
                filename = playurl.rsplit("/",1)[-1]
                path = playurl.replace(filename,"")

        #get the path
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?",(path,))
        result = cursor.fetchone()
        if result != None:
            pathid = result[0]        
        else:
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0]
            pathid = pathid + 1
            pathsql = "insert into path(idPath, strPath) values(?, ?)"
            cursor.execute(pathsql, (pathid,path))
        
        
        ##### ADD THE SONG ############
        if songid == None:
            
            utils.logMsg("ADD song to Kodi library","Id: %s - Title: %s" % (embyId, name))

            #create the song
            cursor.execute("select coalesce(max(idSong),0) as songid from song")
            songid = cursor.fetchone()[0]
            songid = songid + 1
            pathsql="insert into song(idSong, idAlbum, idPath, strArtists, strGenres, strTitle, iTrack, iDuration, iYear, strFileName, strMusicBrainzTrackID, iTimesPlayed, lastplayed) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(pathsql, (songid, albumid, pathid, artists, genres, name, track, duration, year, filename, musicBrainzId, playcount, lastplayed))
            
            #create the reference in emby table
            pathsql = "INSERT into emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(pathsql, (MBitem["Id"], songid, "song", API().getChecksum(MBitem)))
            
        #### UPDATE THE SONG #####
        else:
            utils.logMsg("UPDATE song to Kodi library","Id: %s - Title: %s" % (embyId, name))
            pathsql="update song SET idAlbum=?, strArtists=?, strGenres=?, strTitle=?, iTrack=?, iDuration=?, iYear=?, strFileName=?,  strMusicBrainzTrackID=?, iTimesPlayed=?, lastplayed=?  WHERE idSong = ?"
            cursor.execute(pathsql, (albumid, artists, genres, name, track, duration, year, filename, musicBrainzId, playcount, lastplayed, songid))
            
            #update the checksum in emby table
            cursor.execute("UPDATE emby SET checksum = ? WHERE emby_id = ?", (API().getChecksum(MBitem),MBitem["Id"]))
        
        #add genres
        self.AddGenresToMedia(songid, MBitem.get("Genres"), "song", cursor)
        
        #link song to album
        if albumid:
            sql="INSERT OR REPLACE into albuminfosong(idAlbumInfoSong, idAlbumInfo, iTrack, strTitle, iDuration) values(?, ?, ?, ?, ?)"
            cursor.execute(sql, (songid, albumid, track, name, duration))
        
        #link song to artist
        for artist in MBitem.get("ArtistItems"):
            cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(artist["Id"],))
            result = cursor.fetchone()
            if result:
                artistid = result[0]
                sql="INSERT OR REPLACE into song_artist(idArtist, idSong, strArtist) values(?, ?, ?)"
                cursor.execute(sql, (artistid, songid, artist["Name"]))
        
        #update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), songid, "song", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary"), songid, "song", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner"), songid, "song", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo"), songid, "song", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art"), songid, "song", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb"), songid, "song", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc"), songid, "song", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop"), songid, "song", "fanart", cursor)
    
    def deleteItemFromKodiLibrary(self, id, connection, cursor ):
        
        cursor.execute("SELECT kodi_id, media_type FROM emby WHERE emby_id=?", (id,))
        result = cursor.fetchone()
        if result:
            kodi_id = result[0]
            media_type = result[1]
            if media_type == "artist":
                utils.logMsg("deleting artist from Kodi library --> ",id)
                cursor.execute("DELETE FROM artist WHERE idArtist = ?", (kodi_id,))
            if media_type == "song":
                utils.logMsg("deleting song from Kodi library --> ",id)
                cursor.execute("DELETE FROM song WHERE idSong = ?", (kodi_id,))
            if media_type == "album":
                utils.logMsg("deleting album from Kodi library --> ",id)
                cursor.execute("DELETE FROM album WHERE idAlbum = ?", (kodi_id,))
            
            #delete the record in emby table
            cursor.execute("DELETE FROM emby WHERE emby_id = ?", (id,))
                          
    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):
        updateDone = False
        if imageUrl:
            cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodiId, mediaType, imageType))
            result = cursor.fetchone()
            if(result == None):
                utils.logMsg("ArtworkSync", "Adding Art Link for kodiId: " + str(kodiId) + " (" + imageUrl + ")")
                cursor.execute("INSERT INTO art(media_id, media_type, type, url) values(?, ?, ?, ?)", (kodiId, mediaType, imageType, imageUrl))
            else:
                url = result[0];
                if(url != imageUrl):
                    utils.logMsg("ArtworkSync", "Updating Art Link for kodiId: " + str(kodiId) + " (" + url + ") -> (" + imageUrl + ")")
                    cursor.execute("UPDATE art set url = ? WHERE media_id = ? AND media_type = ? AND type = ?", (imageUrl, kodiId, mediaType, imageType))
                     
    def AddGenresToMedia(self, id, genres, mediatype, cursor):

        if genres:
            
            for genre in genres:

                idGenre = None
                cursor.execute("SELECT idGenre as idGenre FROM genre WHERE strGenre = ?",(genre,))
                result = cursor.fetchone()
                if result != None:
                    idGenre = result[0]
                #create genre
                if idGenre == None:
                    cursor.execute("select coalesce(max(idGenre),0) as idGenre from genre")
                    idGenre = cursor.fetchone()[0]
                    idGenre = idGenre + 1
                    sql="insert into genre(idGenre, strGenre) values(?, ?)"
                    cursor.execute(sql, (idGenre,genre))

                #assign genre to item    
                if mediatype == "album":
                    sql="INSERT OR REPLACE into album_genre(idGenre, idAlbum) values(?, ?)"
                    cursor.execute(sql, (idGenre,id))
                elif mediatype == "song":
                    sql="INSERT OR REPLACE into song_genre(idGenre, idSong) values(?, ?)"
                    cursor.execute(sql, (idGenre,id))
                else:
                    return
    

               
