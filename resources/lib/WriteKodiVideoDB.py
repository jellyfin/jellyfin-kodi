# -*- coding: utf-8 -*-

#################################################################################################
# WriteKodiVideoDB
#################################################################################################

import sqlite3
from os.path import basename

import xbmc
import xbmcgui
import xbmcaddon

from ClientInformation import ClientInformation
import Utils as utils
from API import API
from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ReadKodiDB import ReadKodiDB
from ReadEmbyDB import ReadEmbyDB
from TextureCache import TextureCache


class WriteKodiVideoDB():
    
    textureCache = TextureCache()
    doUtils = DownloadUtils()
    kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])

    addon = xbmcaddon.Addon()
    addonName = ClientInformation().getAddonName()
    WINDOW = xbmcgui.Window(10000)

    username = WINDOW.getProperty('currUser')
    userid = WINDOW.getProperty('userId%s' % username)
    server = WINDOW.getProperty('server%s' % username)

    directpath = addon.getSetting('useDirectPaths') == "true"

    def logMsg(self, msg, lvl = 1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))

    def updatePlayCountFromKodi(self, id, type, playcount = 0):
        
        # When user marks item watched from kodi interface update this in Emby
        # Erase resume point when user marks watched/unwatched to follow Emby behavior
        doUtils = self.doUtils
        self.logMsg("updatePlayCountFromKodi Called", 2)
        
        connection = utils.KodiSQL()
        cursor = connection.cursor()
        cursor.execute("SELECT emby_id FROM emby WHERE media_type = ? AND kodi_id = ?", (type, id,))

        try: # Find associated Kodi Id to Emby Id
            emby_id = cursor.fetchone()[0]
        except:
            # Could not find the Emby Id
            self.logMsg("Emby Id not found.", 2)
        else:
            # Found the Emby Id, let Emby server know of new playcount
            watchedurl = "{server}/mediabrowser/Users/{UserId}/PlayedItems/%s" % emby_id
            if playcount != 0:
                doUtils.downloadUrl(watchedurl, type = "POST")
            else:
                doUtils.downloadUrl(watchedurl, type = "DELETE")
            # Erase any resume point associated
            self.setKodiResumePoint(id, 0, 0, cursor)
        finally:
            cursor.close
        
    def addOrUpdateMovieToKodiLibrary(self, embyId, connection, cursor, viewTag):
        
        addon = self.addon
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        if not MBitem:
            self.logMsg("ADD movie to Kodi library FAILED", "Item %s not found on server!" % embyId)
            return
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (embyId,))
        try:
            movieid = cursor.fetchone()[0]
        except:
            movieid = None
            self.logMsg("Movie Id: %s not found." % embyId, 2)
        
        timeInfo = API().getTimeInfo(MBitem)
        userData = API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genres = MBitem.get('Genres')
        studios = API().getStudios(MBitem)

        #### The movie details ####
        playcount = userData.get('PlayCount')
        dateplayed = userData.get("LastPlayedDate")
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)

        title = MBitem['Name']
        plot = API().getOverview(MBitem)
        shortplot = MBitem.get('ShortOverview')
        tagline = API().getTagline(MBitem)
        votecount = MBitem.get('VoteCount')
        rating = MBitem.get('CommunityRating')
        writer = " / ".join(people.get('Writer'))
        year = MBitem.get('ProductionYear')
        imdb = API().getProvider(MBitem, "imdb")
        sorttitle = MBitem['SortName']
        runtime = timeInfo.get('TotalTime')
        mpaa = MBitem.get('OfficialRating')
        genre = " / ".join(genres)
        director = " / ".join(people.get('Director'))
        studio = " / ".join(studios)
        country = API().getCountry(MBitem)

        try: # Verify if there's a local trailer
            if MBitem.get('LocalTrailerCount'):
                itemTrailerUrl = "{server}/mediabrowser/Users/{UserId}/Items/%s/LocalTrailers?format=json" % embyId
                result = self.doUtils.downloadUrl(itemTrailerUrl)
                trailerUrl = "plugin://plugin.video.emby/trailer/?id=%s&mode=play" % result[0]['Id']
            # Or get youtube trailer
            else:
                trailerUrl = MBitem['RemoteTrailers'][0]['Url']
                trailerId = trailerUrl.split('=')[1]
                trailerUrl = "plugin://plugin.video.youtube/play/?video_id=%s" % trailerId
        except:
            trailerUrl = None
            
        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### NOTE THAT LASTPLAYED AND PLAYCOUNT ARE STORED AT THE FILE ENTRY

        # Get the real filename for direct path or media flags for plugin path
        playurl = PlayUtils().directPlay(MBitem)
        try:
            if "plugin://" in playurl:
                fileext = ""
            else:
                fileext = basename(playurl)
        except: return # playurl returned False
        else: # Set filename and path
            
            if self.directpath:
                # Use direct paths instead of add-on redirect
                filename = fileext
                path = playurl.replace(filename, "")

            else: # Set plugin path and media flags using real filename
                filename = "plugin://plugin.video.emby/movies/%s/?filename=%s&id=%s&mode=play" % (embyId, fileext, embyId)
                path = "plugin://plugin.video.emby/movies/%s/" % embyId

                # If the bookmark was created from widget
                cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ?", (fileext,))
                try: # Remove Kodi bookmark - messes with plugin path bookmark
                    result = cursor.fetchone()[0]
                    self.setKodiResumePoint(result, 0, 0, cursor)
                except: pass

                # If the bookmark was created within the library
                plugindummy = "plugin://plugin.video.emby/"
                cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (plugindummy,))
                try: 
                    pathiddummy = cursor.fetchone()[0]
                except: pass
                else:
                    cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?", (filename, pathiddummy,))
                    try: # Remove Kodi bookmark - creates a ghost bookmark for widgets
                        result = cursor.fetchone()[0]
                        self.setKodiResumePoint(result, 0, 0, cursor)
                    except: pass


        # Validate the path in database
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?", (path,))
        try:
            pathid = cursor.fetchone()[0]
        except:
            # Path does not exist yet
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0] + 1
            query = "INSERT into path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(query, (pathid, path, "movies", "metadata.local", 1))

        # Validate the file in database
        cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?", (filename, pathid,))
        try:
            fileid = cursor.fetchone()[0]
        except:
            # File does not exist yet
            cursor.execute("select coalesce(max(idFile),0) as fileid from files")
            fileid = cursor.fetchone()[0] + 1
            query = "INSERT INTO files(idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (fileid, pathid, filename, playcount, dateplayed, dateadded))
        else: # File exists
            query = "UPDATE files SET playCount = ?, lastPlayed = ? WHERE idFile = ?"
            cursor.execute(query, (playcount, dateplayed, fileid))


        ##### UPDATE THE MOVIE #####
        if movieid:
            self.logMsg("UPDATE movie to Kodi Library, Id: %s - Title: %s" % (embyId, title), 1)

            query = "UPDATE movie SET c00 = ?, c01 = ?, c02 = ?, c03 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ?, c14 = ?, c15 = ?, c16 = ?, c18 = ?, c19 = ?, c21 = ? WHERE idMovie = ?"
            cursor.execute(query, (title, plot, shortplot, tagline, votecount, rating, writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio, trailerUrl, country, movieid))

            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))

        ##### OR ADD THE MOVIE #####
        else:
            self.logMsg("ADD movie to Kodi Library, Id: %s - Title: %s" % (embyId, title), 1)

            # Create the movie
            cursor.execute("select coalesce(max(idMovie),0) as movieid from movie")
            movieid = cursor.fetchone()[0] + 1
            query = "INSERT INTO movie(idMovie, idFile, c00, c01, c02, c03, c04, c05, c06, c07, c09, c10, c11, c12, c14, c15, c16, c18, c19, c21) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (movieid, fileid, title, plot, shortplot, tagline, votecount, rating, writer, year, imdb, sorttitle, runtime, mpaa, genre, director, title, studio, trailerUrl, country))

            # Add the viewtag
            self.AddTagToMedia(movieid, viewTag, "movie", cursor)

            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(query, (embyId, movieid, "movie", checksum))


        # Update or insert actors
        self.AddPeopleToMedia(movieid ,MBitem.get('People'), "movie", connection, cursor)
        
        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "movie"), movieid, "movie", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "movie"), movieid, "movie", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner", mediaType = "movie"), movieid, "movie", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo", mediaType = "movie"), movieid, "movie", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art", mediaType = "movie"), movieid, "movie", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb", mediaType = "movie"), movieid, "movie", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc", mediaType = "movie"), movieid, "movie", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop", mediaType = "movie"), movieid, "movie", "fanart", cursor)
        
        # Update genres
        self.AddGenresToMedia(movieid, genres, "movie", cursor)
        
        # Update countries
        self.AddCountriesToMedia(movieid, MBitem.get('ProductionLocations'), "movie", cursor)
        
        # Update studios
        self.AddStudiosToMedia(movieid, studios, "movie", cursor)
        
        # Add streamdetails
        self.AddStreamDetailsToMedia(API().getMediaStreams(MBitem), fileid, cursor)
        
        # Add to or remove from favorites tag
        if userData.get('Favorite'):
            self.AddTagToMedia(movieid, "Favorite movies", "movie", cursor)
        else:
            self.AddTagToMedia(movieid, "Favorite movies", "movie", cursor, True)
        
        # Set resume point and round to 6th decimal
        resume = round(float(timeInfo.get('ResumeTime')), 6)
        total = round(float(timeInfo.get('TotalTime')), 6)
        jumpback = int(addon.getSetting('resumeJumpBack'))
        if resume > jumpback:
            # To avoid negative bookmark
            resume = resume - jumpback
        self.setKodiResumePoint(fileid, resume, total, cursor)
        
    def addOrUpdateMusicVideoToKodiLibrary(self, embyId ,connection, cursor):
        
        addon = self.addon
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        if not MBitem:
            self.logMsg("ADD musicvideo to Kodi library FAILED", "Item %s not found on server!" % embyId, 1)
            return
        
        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (embyId,))
        try:
            idMVideo = cursor.fetchone()[0]
        except:
            idMVideo = None
        
        timeInfo = API().getTimeInfo(MBitem)
        userData = API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genres = MBitem.get('Genres')
        studios = API().getStudios(MBitem)

        #### The video details ####
        playcount = userData.get('PlayCount')
        dateplayed = userData.get('LastPlayedDate')
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)

        title = MBitem['Name']
        runtime = timeInfo.get('TotalTime')
        director = " / ".join(people.get('Director'))
        studio = " / ".join(studios)
        year = MBitem.get('ProductionYear')
        plot = API().getOverview(MBitem)
        album = MBitem.get('Album')
        artist = " / ".join(MBitem.get('Artists'))
        genre = " / ".join(genres)
        track = MBitem.get('Track')
            
        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### NOTE THAT LASTPLAYED AND PLAYCOUNT ARE STORED AT THE FILE ENTRY

        # Set filename and path
        if addon.getSetting('useDirectPaths') == "true":
            # playurl can return False
            playurl = PlayUtils().directPlay(MBitem)
            try:
                filename = basename(playurl)
                path = playurl.replace(filename, "")
            except: return# Should we return instead? - for transcoding we just use the server's streaming path because I couldn't figure out how to set the plugin path in the music DB'
        else: # Set plugin path
            path = "plugin://plugin.video.emby/musicvideos/%s/" % embyId
            filename = "plugin://plugin.video.emby/musicvideos/%s/?id=%s&mode=play" % (embyId, embyId)

        
        # Validate the path in database
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?", (path,))
        try:
            pathid = cursor.fetchone()[0]
        except:
            # Path does not exist yet
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0] + 1
            query = "INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(query, (pathid, path, "musicvideos", "metadata.local", 1))

        # Validate the file in database
        cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?", (filename, pathid,))
        try:
            fileid = cursor.fetchone()[0]
            query = "UPDATE files SET playCount = ?, lastPlayed = ? WHERE idFile = ?"
            cursor.execute(query, (playcount, dateplayed, fileid))
        except:
            # File does not exist yet
            cursor.execute("select coalesce(max(idFile),0) as fileid from files")
            fileid = cursor.fetchone()[0] + 1
            query = "INSERT INTO files(idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (fileid, pathid, filename, playcount, dateplayed, dateadded))

        
        ##### UPDATE THE MVIDEO #####
        if idMVideo:
            self.logMsg("UPDATE musicvideo to Kodi Library, Id: %s - Title: %s" % (embyId, title), 1)

            query = "UPDATE musicvideo SET c00 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c08 = ?, c09 = ?, c10 = ?, c11 = ?, c12 = ? WHERE idMVideo = ?"
            cursor.execute(query, (title, runtime, director, studio, year, plot, album, artist, genre, track, idMVideo))

            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))

        ##### OR ADD THE MVIDEO #####
        else:
            self.logMsg("ADD musicvideo to Kodi Library, Id: %s - Title: %s" % (embyId, title), 1)

            # Create the video
            cursor.execute("select coalesce(max(idMVideo),0) as idMVideo from musicvideo")
            idMVideo = cursor.fetchone()[0] + 1
            query = "INSERT INTO musicvideo(idMVideo, idFile, c00, c04, c05, c06, c07, c08, c09, c10, c11, c12) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (idMVideo, fileid, title, runtime, director, studio, year, plot, album, artist, genre, track))

            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(query, (embyId, idMVideo, "musicvideo", checksum))

        
        # Update or insert actors
        self.AddPeopleToMedia(idMVideo,MBitem.get("People"),"musicvideo", connection, cursor)
        
        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "musicvideo"), idMVideo, "musicvideo", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "musicvideo"), idMVideo, "musicvideo", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner", mediaType = "musicvideo"), idMVideo, "musicvideo", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo", mediaType = "musicvideo"), idMVideo, "musicvideo", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art", mediaType = "musicvideo"), idMVideo, "musicvideo", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb", mediaType = "musicvideo"), idMVideo, "musicvideo", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc", mediaType = "musicvideo"), idMVideo, "musicvideo", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop", mediaType = "musicvideo"), idMVideo, "musicvideo", "fanart", cursor)
        
        # Update genres
        self.AddGenresToMedia(idMVideo, genres, "musicvideo", cursor)
               
        # Update studios
        self.AddStudiosToMedia(idMVideo, studios, "musicvideo", cursor)
        
        # Add streamdetails
        self.AddStreamDetailsToMedia(API().getMediaStreams(MBitem), fileid, cursor)
    
    def addOrUpdateTvShowToKodiLibrary(self, embyId, connection, cursor, viewTag):
        
        MBitem = ReadEmbyDB().getFullItem(embyId)
        
        if not MBitem:
            self.logMsg("ADD tvshow to Kodi library FAILED", "Item %s not found on server!" % embyId)
            return

        # If the item already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?", (embyId,))
        try:
            showid = cursor.fetchone()[0]
        except:
            showid = None

        timeInfo = API().getTimeInfo(MBitem)
        userData = API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genres = MBitem.get('Genres')
        studios = API().getStudios(MBitem)

        #### The tv show details ####
        playcount = userData.get('PlayCount')
        dateplayed = userData.get("LastPlayedDate")
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)

        title = MBitem['Name']
        plot = API().getOverview(MBitem)
        rating = MBitem.get('CommunityRating')
        premieredate = API().getPremiereDate(MBitem)
        genre = " / ".join(genres)
        tvdb = API().getProvider(MBitem, "tvdb")
        mpaa = MBitem.get('OfficialRating')
        studio = " / ".join(studios)
        sorttitle = MBitem['SortName']

        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### TOP LEVEL PATH AS MONITORED SOURCE IS REQUIRED - for actors, etc. (no clue why)

        # Set filename and path
        if self.directpath:
            playurl = PlayUtils().directPlay(MBitem)
            try: # playurl can return False
                filename = basename(playurl)
                path = playurl.replace(filename, "")
                if "\\" in playurl:
                    temp = "%s\\" % path.rsplit("\\", 2)[1]
                elif "/" in playurl:
                    temp = "%s/" % path.rsplit("/", 2)[1]
                toplevelpath = path.replace(temp,"")
            except: pass
        else: # Set plugin path
            path = "plugin://plugin.video.emby/tvshows/%s/" % embyId       
            toplevelpath = "plugin://plugin.video.emby/"
            

        ##### UPDATE THE TV SHOW #####
        if showid:
            self.logMsg("UPDATE tvshow to Kodi library, Id: %s - Title: %s" % (embyId, title))
            
            query = "UPDATE tvshow SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ? WHERE idShow = ?"
            cursor.execute(query, (title, plot, rating, premieredate, genre, title, tvdb, mpaa, studio, sorttitle, showid))
            
            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))

        ##### OR ADD THE TV SHOW #####
        else:
            self.logMsg("ADD tvshow to Kodi library, Id: %s - Title: %s" % (embyId, title))
            
            # Create the TV show path
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0] + 1
            query = "INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(query, (pathid, path, None, None, 1))

            # Validate the top level path in database
            cursor.execute("SELECT idPath as tlpathid FROM path WHERE strPath = ?", (toplevelpath,))
            try:
                cursor.fetchone()[0]
            except:
                # Top level path does not exist yet
                cursor.execute("select coalesce(max(idPath),0) as tlpathid from path")
                tlpathid = cursor.fetchone()[0] + 1
                query = "INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
                cursor.execute(query, (tlpathid, toplevelpath, "tvshows", "metadata.local", 1))
                
            # Create the TV show
            cursor.execute("select coalesce(max(idShow),0) as showid from tvshow")
            showid = cursor.fetchone()[0] + 1
            query = "INSERT INTO tvshow(idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14, c15) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (showid, title, plot, rating, premieredate, genre, title, tvdb, mpaa, studio, sorttitle))
            
            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum) values(?, ?, ?, ?)"
            cursor.execute(query, (embyId, showid, "tvshow", checksum))
            
            # Link the path
            query = "INSERT INTO tvshowlinkpath(idShow, idPath) values(?, ?)"
            cursor.execute(query, (showid, pathid))
                        
            # Add the viewtag
            self.AddTagToMedia(showid, viewTag, "tvshow", cursor)

            
        # Update or insert people
        self.AddPeopleToMedia(showid, MBitem.get('People'),"tvshow", connection, cursor)
        
        # Update genres
        self.AddGenresToMedia(showid, genres, "tvshow", cursor)
        
        # Update studios
        self.AddStudiosToMedia(showid, studios, "tvshow", cursor)
        
        # Add to or remove from favorites tag
        if userData.get('Favorite'):
            self.AddTagToMedia(showid, "Favorite tvshows", "tvshow", cursor)
        else:
            self.AddTagToMedia(showid, "Favorite tvshows", "tvshow", cursor, True)
                
        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "tvshow"), showid, "tvshow", "thumb", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "tvshow"), showid, "tvshow", "poster", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Banner", mediaType = "tvshow"), showid, "tvshow", "banner", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Logo", mediaType = "tvshow"), showid, "tvshow", "clearlogo", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Art", mediaType = "tvshow"), showid, "tvshow", "clearart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Thumb", mediaType = "tvshow"), showid, "tvshow", "landscape", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Disc", mediaType = "tvshow"), showid, "tvshow", "discart", cursor)
        self.addOrUpdateArt(API().getArtwork(MBitem, "Backdrop", mediaType = "tvshow"), showid, "tvshow", "fanart", cursor)
        
        # Update season details
        self.updateSeasons(embyId, showid, connection, cursor)
        
    def addOrUpdateEpisodeToKodiLibrary(self, embyId, showid, connection, cursor):
        
        addon = self.addon
        MBitem = ReadEmbyDB().getFullItem(embyId)

        if not MBitem:
            self.logMsg("ADD episode to Kodi library FAILED, Item %s not found on server!" % embyId, 1)
            return

        # If the episode already exist in the local Kodi DB we'll perform a full item update
        # If the item doesn't exist, we'll add it to the database
        
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(embyId,))
        try:
            episodeid = cursor.fetchone()[0]
        except:
            episodeid = None

        timeInfo = API().getTimeInfo(MBitem)
        userData = API().getUserData(MBitem)
        people = API().getPeople(MBitem)

        ##### The episode details #####
        seriesId = MBitem['SeriesId']
        seriesName = MBitem['SeriesName']
        season = MBitem.get('ParentIndexNumber')
        episode = MBitem.get('IndexNumber', 0)

        playcount = userData.get('PlayCount')
        dateplayed = userData.get("LastPlayedDate")
        dateadded = API().getDateCreated(MBitem)
        checksum = API().getChecksum(MBitem)

        title = MBitem['Name']
        plot = API().getOverview(MBitem)
        rating = MBitem.get('CommunityRating')
        writer = " / ".join(people.get("Writer"))
        premieredate = API().getPremiereDate(MBitem)
        runtime = timeInfo.get('TotalTime')
        director = " / ".join(people.get("Director"))

        #### ADD OR UPDATE THE FILE AND PATH ###########
        #### NOTE THAT LASTPLAYED AND PLAYCOUNT ARE STORED AT THE FILE ENTRY
        #### ORDERING FOR SORTING C15 C16 TO DISPLAY SPECIALS WITHIN REGULAR EPISODES

        # Get the real filename
        playurl = PlayUtils().directPlay(MBitem)
        try:
            if "plugin://" in playurl:
                fileext = ""
            else:
                fileext = basename(playurl)
        except: return # playurl returned False
        else: # Set filename and path

            if self.directpath:
                filename = fileext
                path = playurl.replace(filename, "")

            else: # Set plugin path and media flags - real filename with extension
                filename = "plugin://plugin.video.emby/tvshows/%s/?filename=%s&id=%s&mode=play" % (seriesId, fileext, embyId)
                path = "plugin://plugin.video.emby/tvshows/%s/" % seriesId

                # If the bookmark was created from widget
                cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ?", (fileext,))
                try: # Remove Kodi bookmark - messes with plugin path bookmark
                    result = cursor.fetchone()[0]
                    self.setKodiResumePoint(result, 0, 0, cursor)
                except: pass

                # If the bookmark was created within the library
                plugindummy = "plugin://plugin.video.emby/"
                cursor.execute("SELECT idPath FROM path WHERE strPath = ?", (plugindummy,))
                try: 
                    pathiddummy = cursor.fetchone()[0]
                except: pass
                else:
                    cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?", (filename, pathiddummy,))
                    try: # Remove Kodi bookmark - creates a ghost bookmark for widgets
                        result = cursor.fetchone()[0]
                        self.setKodiResumePoint(result, 0, 0, cursor)
                    except: pass
        
        # Validate the path in database
        cursor.execute("SELECT idPath as pathid FROM path WHERE strPath = ?", (path,))
        try:
            pathid = cursor.fetchone()[0]
        except:
            # Path does not exist yet
            cursor.execute("select coalesce(max(idPath),0) as pathid from path")
            pathid = cursor.fetchone()[0] + 1
            query = "INSERT INTO path(idPath, strPath, strContent, strScraper, noUpdate) values(?, ?, ?, ?, ?)"
            cursor.execute(query, (pathid, path, None, None, 1))

        # Validate the file in database
        cursor.execute("SELECT idFile as fileid FROM files WHERE strFilename = ? and idPath = ?", (filename, pathid,))
        try:
            fileid = cursor.fetchone()[0]
        except:
            # File does not exist yet
            cursor.execute("select coalesce(max(idFile),0) as fileid from files")
            fileid = cursor.fetchone()[0] + 1
            query = "INSERT INTO files(idFile, idPath, strFilename, playCount, lastPlayed, dateAdded) values(?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (fileid, pathid, filename, playcount, dateplayed, dateadded))
        else: # File exists
            query = "UPDATE files SET playCount = ?, lastPlayed = ? WHERE idFile = ?"
            cursor.execute(query, (playcount, dateplayed, fileid))

        # Validate the season exists in Emby and in database
        if season is None:
            self.logMsg("SKIP adding episode to Kodi Library, no ParentIndexNumber - ID: %s - %s" % (embyId, title))
            return False
            
        cursor.execute("SELECT idSeason FROM seasons WHERE idShow = ? and season = ?", (showid, season,))
        try:
            cursor.fetchone()[0]
        except: # Season does not exist, update seasons
            self.updateSeasons(seriesId, showid, connection, cursor)


        ##### UPDATE THE EPISODE #####
        if episodeid:
            self.logMsg("UPDATE episode from // %s - S%s // to Kodi library, Id: %s - E%s: %s" % (seriesName, season, embyId, episode, title))

            query = "UPDATE episode SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?, c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ? WHERE idEpisode = ?"
            cursor.execute(query, (title, plot, rating, writer, premieredate, runtime, director, season, episode, title, "-1", "-1", episodeid))
            
            #update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (checksum, embyId))
        
        ##### OR ADD THE EPISODE #####
        else:
            self.logMsg("ADD episode from // %s - S%s // to Kodi library, Id: %s - E%s: %s" % (seriesName, season, embyId, episode, title))

            # Create the episode
            cursor.execute("select coalesce(max(idEpisode),0) as episodeid from episode")
            episodeid = cursor.fetchone()[0] + 1
            query = "INSERT INTO episode(idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14, idShow, c15, c16) values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (episodeid, fileid, title, plot, rating, writer, premieredate, runtime, director, season, episode, title, showid, "-1", "-1"))
            
            # Create the reference in emby table
            query = "INSERT INTO emby(emby_id, kodi_id, media_type, checksum, parent_id) values(?, ?, ?, ?, ?)"
            cursor.execute(query, (embyId, episodeid, "episode", checksum, showid))

        
        # Update or insert actors
        self.AddPeopleToMedia(episodeid, MBitem.get('People'), "episode", connection, cursor)

        # Add streamdetails
        self.AddStreamDetailsToMedia(API().getMediaStreams(MBitem), fileid, cursor)
        
        # Update artwork
        self.addOrUpdateArt(API().getArtwork(MBitem, "Primary", mediaType = "episode"), episodeid, "episode", "thumb", cursor)

        # Set resume point and round to 6th decimal
        resume = round(float(timeInfo.get('ResumeTime')), 6)
        total = round(float(timeInfo.get('TotalTime')), 6)
        jumpback = int(addon.getSetting('resumeJumpBack'))
        if resume > jumpback:
            # To avoid negative bookmark
            resume = resume - jumpback
        self.setKodiResumePoint(fileid, resume, total, cursor)

    def deleteItemFromKodiLibrary(self, id, connection, cursor ):
        
        cursor.execute("SELECT kodi_id, media_type FROM emby WHERE emby_id = ?", (id,))
        try:
            result = cursor.fetchone()
            kodi_id = result[0]
            media_type = result[1]
        except: pass
        else: # Delete entry from database
            if "movie" in media_type:
                self.logMsg("Deleting movie from Kodi library, Id: %s" % id, 1)
                cursor.execute("DELETE FROM movie WHERE idMovie = ?", (kodi_id,))
            
            elif "episode" in media_type:
                cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodi_id,))
                self.logMsg("Deleting episode from Kodi library, Id: %s" % id, 1)
            
            elif "tvshow" in media_type:
                cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (kodi_id,))
                self.logMsg("Deleting tvshow from Kodi library, Id: %s" % id, 1)
            
            elif "musicvideo" in media_type:
                cursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (kodi_id,))
                self.logMsg("Deleting musicvideo from Kodi library, Id: %s" % id, 1)

            # Delete the record in emby table
            cursor.execute("DELETE FROM emby WHERE emby_id = ?", (id,))
     
    def updateSeasons(self,embyTvShowId, kodiTvShowId, connection, cursor):
        
        seasonData = ReadEmbyDB().getTVShowSeasons(embyTvShowId)
        
        if seasonData: # Verify every season
            for season in seasonData:
                
                seasonNum = season.get('IndexNumber')
                
                cursor.execute("SELECT idSeason as seasonid FROM seasons WHERE idShow = ? and season = ?", (kodiTvShowId, seasonNum,))
                try:
                    seasonid = cursor.fetchone()[0]
                except: # Create the season
                    cursor.execute("select coalesce(max(idSeason),0) as seasonid from seasons")
                    seasonid = cursor.fetchone()[0] + 1
                    query = "INSERT INTO seasons(idSeason, idShow, season) values(?, ?, ?)"
                    cursor.execute(query, (seasonid, kodiTvShowId, seasonNum))
                finally: # Update artwork
                    imageUrl = API().getArtwork(season, "Thumb", mediaType = "season")
                    self.addOrUpdateArt(imageUrl, seasonid, "season", "landscape", cursor)
                    
                    imageUrl = API().getArtwork(season, "Primary", mediaType = "season")
                    self.addOrUpdateArt(imageUrl, seasonid, "season", "poster", cursor)
                    
                    imageUrl = API().getArtwork(season, "Banner", mediaType = "season")
                    self.addOrUpdateArt(imageUrl, seasonid, "season", "banner", cursor)
            
            # All season entry
            MBitem = ReadEmbyDB().getFullItem(embyTvShowId)
            seasonNum = -1

            cursor.execute("SELECT idSeason as seasonid FROM seasons WHERE idShow = ? and season = ?", (kodiTvShowId, seasonNum,))
            try:
                seasonid = cursor.fetchone()[0]
            except: # Create all season entry
                cursor.execute("select coalesce(max(idSeason),0) as seasonid from seasons")
                seasonid = cursor.fetchone()[0] + 1
                query = "INSERT INTO seasons(idSeason, idShow, season) values(?, ?, ?)"
                cursor.execute(query, (seasonid, kodiTvShowId, seasonNum))
            finally: # Update the artwork
                imageUrl = API().getArtwork(MBitem, "Primary", mediaType = "season")
                self.addOrUpdateArt(imageUrl, seasonid, "season", "poster", cursor)
                            
    def addOrUpdateArt(self, imageUrl, kodiId, mediaType, imageType, cursor):

        if imageUrl:

            cacheimage = False
            
            cursor.execute("SELECT url FROM art WHERE media_id = ? AND media_type = ? AND type = ?", (kodiId, mediaType, imageType,))
            try: # Update the artwork
                url = cursor.fetchone()[0]
            except: # Add the artwork
                cacheimage = True
                self.logMsg("Adding Art Link for kodiId: %s (%s)" % (kodiId, imageUrl), 1)
                query = "INSERT INTO art(media_id, media_type, type, url) values(?, ?, ?, ?)"
                cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))
            else:
                if url != imageUrl:
                    cacheimage = True
                    self.logMsg("Updating Art Link for kodiId: %s (%s) -> (%s)" % (kodiId, url, imageUrl), 1)
                    query = "INSERT INTO art(media_id, media_type, type, url) values(?, ?, ?, ?)"
                    cursor.execute(query, (kodiId, mediaType, imageType, imageUrl))
                    
            # Cache fanart and poster in Kodi texture cache
            if cacheimage and imageType in ("fanart", "poster"):
                self.textureCache.CacheTexture(imageUrl)
        
    def setKodiResumePoint(self, fileid, resume_seconds, total_seconds, cursor):
        
        cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (fileid,))
        if resume_seconds:
            cursor.execute("select coalesce(max(idBookmark),0) as bookmarkId from bookmark")
            bookmarkId =  cursor.fetchone()[0] + 1
            query = "INSERT INTO bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, playerState, type) values(?, ?, ?, ?, ?, ?, ?, ?)"
            cursor.execute(query, (bookmarkId, fileid, resume_seconds, total_seconds, None, "DVDPlayer", None, 1))
     
    def AddPeopleToMedia(self, id, people, mediatype, connection, cursor):
        
        kodiVersion = self.kodiversion
        
        if people:
            castorder = 1

            for person in people:

                name = person['Name']
                type = person['Type']

                if kodiVersion == 15:
                    # Kodi Isengard
                    cursor.execute("SELECT actor_id as actorid FROM actor WHERE name = ?", (name,))
                else:
                    # Kodi Gotham or Helix
                    cursor.execute("SELECT idActor as actorid FROM actors WHERE strActor = ?",(name,))

                try: # Update person in database
                    actorid = cursor.fetchone()[0]
                except:
                    # Person entry does not exist yet.
                    if kodiVersion == 15:
                        # Kodi Isengard
                        cursor.execute("select coalesce(max(actor_id),0) as actorid from actor")
                        query = "INSERT INTO actor(actor_id, name) values(?, ?)"
                    else:
                        # Kodi Gotham or Helix
                        cursor.execute("select coalesce(max(idActor),0) as actorid from actors")
                        query = "INSERT INTO actors(idActor, strActor) values(?, ?)"
                    
                    actorid = cursor.fetchone()[0] + 1
                    self.logMsg("Adding people to Media, processing: %s" % name, 2)
                    
                    cursor.execute(query, (actorid, name))
                finally:
                    # Add person image to art table
                    thumb = API().imageUrl(person['Id'], "Primary", 0, 400, 400)
                    if thumb:
                        arttype = type.lower()

                        if "writing" in arttype:
                            arttype = "writer"

                        self.addOrUpdateArt(thumb, actorid, arttype, "thumb", cursor)

                    # Link person to content in database
                    if kodiVersion == 15:
                        # Kodi Isengard
                        if "Actor" in type:
                            Role = person.get('Role')
                            query = "INSERT OR REPLACE INTO actor_link(actor_id, media_id, media_type, role, cast_order) values(?, ?, ?, ?, ?)"
                            cursor.execute(query, (actorid, id, mediatype, Role, castorder))
                            castorder += 1
                        
                        elif "Director" in type:
                            query = "INSERT OR REPLACE INTO director_link(actor_id, media_id, media_type) values(?, ?, ?)"
                            cursor.execute(query, (actorid, id, mediatype))
                        
                        elif type in ("Writing", "Writer"):
                            query = "INSERT OR REPLACE INTO writer_link(actor_id, media_id, media_type) values(?, ?, ?)"
                            cursor.execute(query, (actorid, id, mediatype))

                    else:
                        # Kodi Gotham or Helix
                        if "Actor" in type:
                            Role = person.get('Role')

                            if "movie" in mediatype:
                                query = "INSERT OR REPLACE INTO actorlinkmovie(idActor, idMovie, strRole, iOrder) values(?, ?, ?, ?)"
                            elif "tvshow" in mediatype:
                                query = "INSERT OR REPLACE INTO actorlinktvshow(idActor, idShow, strRole, iOrder) values(?, ?, ?, ?)"
                            elif "episode" in mediatype:
                                query = "INSERT OR REPLACE INTO actorlinkepisode(idActor, idEpisode, strRole, iOrder) values(?, ?, ?, ?)"
                            
                            cursor.execute(query, (actorid, id, Role, castorder))
                            castorder += 1

                        elif "Director" in type:

                            if "movie" in mediatype:
                                query = "INSERT OR REPLACE INTO directorlinkmovie(idDirector, idMovie) values(?, ?)"
                            elif "tvshow" in mediatype:
                                query = "INSERT OR REPLACE INTO directorlinktvshow(idDirector, idShow) values(?, ?)"
                            elif "musicvideo" in mediatype:
                                query = "INSERT OR REPLACE INTO directorlinkmusicvideo(idDirector, idMVideo) values(?, ?)"
                            elif "episode" in mediatype:
                                query = "INSERT OR REPLACE INTO directorlinkepisode(idDirector, idEpisode) values(?, ?)"
                            
                            cursor.execute(query, (actorid, id))

                        elif type in ("Writing", "Writer"):

                            if "movie" in mediatype:
                                query = "INSERT OR REPLACE INTO writerlinkmovie(idWriter, idMovie) values(?, ?)"
                            elif "episode" in mediatype:
                                query = "INSERT OR REPLACE INTO writerlinkepisode(idWriter, idEpisode) values(?, ?)"

                            cursor. execute(query, (actorid, id))
                        
    def AddGenresToMedia(self, id, genres, mediatype, cursor):

        kodiVersion = self.kodiversion

        if genres:

            # Delete current genres for clean slate
            if kodiVersion == 15:
                cursor.execute("DELETE FROM genre_link WHERE media_id = ? AND media_type = ?", (id, mediatype,))
            else:
                if "movie" in mediatype:
                    cursor.execute("DELETE FROM genrelinkmovie WHERE idMovie = ?", (id,))
                elif "tvshow" in mediatype:
                    cursor.execute("DELETE FROM genrelinktvshow WHERE idShow = ?", (id,))
                elif "musicvideo" in mediatype:
                    cursor.execute("DELETE FROM genrelinkmusicvideo WHERE idMVideo = ?", (id,))

            # Add Genres
            for genre in genres:

                if kodiVersion == 15:
                    # Kodi Isengard
                    cursor.execute("SELECT genre_id as genre_id FROM genre WHERE name = ?", (genre,))
                    try:
                        genre_id = cursor.fetchone()[0]
                    except:
                        # Create genre in database
                        cursor.execute("select coalesce(max(genre_id),0) as genre_id from genre")
                        genre_id = cursor.fetchone()[0] + 1
                        
                        query = "INSERT INTO genre(genre_id, name) values(?, ?)"
                        cursor.execute(query, (genre_id,genre))
                        self.logMsg("Add Genres to media, processing: %s" % genre, 1)
                    finally:
                        # Assign genre to item
                        query = "INSERT OR REPLACE INTO genre_link(genre_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(query, (genre_id, id, mediatype))
                else:
                    # Kodi Gotham or Helix
                    cursor.execute("SELECT idGenre as idGenre FROM genre WHERE strGenre = ?", (genre,))
                    try:
                        idGenre = cursor.fetchone()[0]
                    except:
                        # Create genre in database
                        cursor.execute("select coalesce(max(idGenre),0) as idGenre from genre")
                        idGenre = cursor.fetchone()[0] + 1

                        query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                        cursor.execute(query, (idGenre,genre))
                        self.logMsg("Add Genres to media, processing: %s" % genre, 1)
                    finally:
                        # Assign genre to item
                        if "movie" in mediatype:
                            query = "INSERT OR REPLACE into genrelinkmovie(idGenre, idMovie) values(?, ?)"
                        elif "tvshow" in mediatype:
                            query = "INSERT OR REPLACE into genrelinktvshow(idGenre, idShow) values(?, ?)"
                        elif "musicvideo" in mediatype:
                            query = "INSERT OR REPLACE into genrelinkmusicvideo(idGenre, idMVideo) values(?, ?)"
                        cursor.execute(query, (idGenre, id))

    def AddCountriesToMedia(self, id, countries, mediatype, cursor):
        
        kodiVersion = self.kodiversion
        
        if countries:
            for country in countries:

                if kodiVersion == 15:
                    # Kodi Isengard
                    cursor.execute("SELECT country_id as country_id FROM country WHERE name = ?", (country,))
                    try:
                        country_id = cursor.fetchone()[0]
                    except:
                        # Country entry does not exists
                        cursor.execute("select coalesce(max(country_id),0) as country_id from country")
                        country_id = cursor.fetchone()[0] + 1

                        query = "INSERT INTO country(country_id, name) values(?, ?)"
                        cursor.execute(query, (country_id, country))
                        self.logMsg("Add Countries to Media, processing: %s" % country)
                    finally:
                        # Assign country to content
                        query = "INSERT OR REPLACE INTO country_link(country_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(query, (country_id, id, mediatype))
                else:
                    # Kodi Gotham or Helix
                    cursor.execute("SELECT idCountry as idCountry FROM country WHERE strCountry = ?", (country,))
                    try:
                        idCountry = cursor.fetchone()[0]
                    except:
                        # Country entry does not exists
                        cursor.execute("select coalesce(max(idCountry),0) as idCountry from country")
                        idCountry = cursor.fetchone()[0] + 1

                        query = "INSERT INTO country(idCountry, strCountry) values(?, ?)"
                        cursor.execute(query, (idCountry, country))
                    finally:
                        # Only movies have a country field
                        if "movie" in mediatype:
                            query = "INSERT OR REPLACE INTO countrylinkmovie(idCountry, idMovie) values(?, ?)"
                            cursor.execute(query, (idCountry, id))
                            
    def AddStudiosToMedia(self, id, studios, mediatype, cursor):

        kodiVersion = self.kodiversion

        if studios:
            for studio in studios:

                if kodiVersion == 15:
                    # Kodi Isengard
                    cursor.execute("SELECT studio_id as studio_id FROM studio WHERE name = ?",(studio,))
                    try:
                        studio_id = cursor.fetchone()[0]
                    except: # Studio does not exists.
                        cursor.execute("select coalesce(max(studio_id),0) as studio_id from studio")
                        studio_id = cursor.fetchone()[0] + 1
  
                        query = "INSERT INTO studio(studio_id, name) values(?, ?)"
                        cursor.execute(query, (studio_id,studio))
                        self.logMsg("Add Studios to media, processing: %s" % studio, 1)
                    
                    finally: # Assign studio to item
                        query = "INSERT OR REPLACE INTO studio_link(studio_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(query, (studio_id, id, mediatype))
                else:
                    # Kodi Gotham or Helix
                    cursor.execute("SELECT idstudio as idstudio FROM studio WHERE strstudio = ?",(studio,))
                    try:
                        idstudio = cursor.fetchone()[0]
                    
                    except: # Studio does not exists.
                        cursor.execute("select coalesce(max(idstudio),0) as idstudio from studio")
                        idstudio = cursor.fetchone()[0] + 1

                        query = "INSERT INTO studio(idstudio, strstudio) values(?, ?)"
                        cursor.execute(query, (idstudio,studio))
                        self.logMsg("Add Studios to media, processing: %s" % studio, 1)
                    
                    finally: # Assign studio to item
                        if "movie" in mediatype:
                            query = "INSERT OR REPLACE INTO studiolinkmovie(idstudio, idMovie) values(?, ?)"
                        elif "musicvideo" in mediatype:
                            query = "INSERT OR REPLACE INTO studiolinkmusicvideo(idstudio, idMVideo) values(?, ?)"
                        elif "tvshow" in mediatype:
                            query = "INSERT OR REPLACE INTO studiolinktvshow(idstudio, idShow) values(?, ?)"
                        elif "episode" in mediatype:
                            query = "INSERT OR REPLACE INTO studiolinkepisode(idstudio, idEpisode) values(?, ?)"
                        cursor.execute(query, (idstudio, id))
        
    def AddTagToMedia(self, id, tag, mediatype, cursor, doRemove = False):

        kodiVersion = self.kodiversion

        if tag:

            if kodiVersion == 15:
                # Kodi Isengard
                cursor.execute("SELECT tag_id as tag_id FROM tag WHERE name = ?", (tag,))
                try:
                    tag_id = cursor.fetchone()[0]
                except:
                    # Create the tag
                    cursor.execute("select coalesce(max(tag_id),0) as tag_id from tag")
                    tag_id = cursor.fetchone()[0] + 1
                    
                    query = "INSERT INTO tag(tag_id, name) values(?, ?)"
                    cursor.execute(query, (tag_id, tag))
                    self.logMsg("Add Tag to media, adding tag: %s" % tag, 1)
                finally:
                    # Assign tag to item
                    if not doRemove:
                        query = "INSERT OR REPLACE INTO tag_link(tag_id, media_id, media_type) values(?, ?, ?)"
                        cursor.execute(query, (tag_id, id, mediatype))
                    else:
                        cursor.execute("DELETE FROM tag_link WHERE media_id = ? AND media_type = ? AND tag_id = ?", (id, mediatype, tag_id,))
            else:
                # Kodi Gotham or Helix
                cursor.execute("SELECT idTag as idTag FROM tag WHERE strTag = ?", (tag,))
                try:
                    idTag = cursor.fetchone()[0]
                except:
                    # Create the tag
                    cursor.execute("select coalesce(max(idTag),0) as idTag from tag")
                    idTag = cursor.fetchone()[0] + 1

                    query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
                    cursor.execute(query, (idTag, tag))
                    self.logMsg("Add Tag to media, adding tag: %s" % tag, 1)
                finally:
                    # Assign tag to item
                    if not doRemove:
                        query = "INSERT OR REPLACE INTO taglinks(idTag, idMedia, media_type) values(?, ?, ?)"
                        cursor.execute(query, (idTag, id, mediatype))
                    else:    
                        cursor.execute("DELETE FROM taglinks WHERE idMedia = ? AND media_type = ? AND idTag = ?", (id, mediatype, idTag,))
    
    def AddStreamDetailsToMedia(self, streamdetails, fileid, cursor):
        
        # First remove any existing entries
        cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (fileid,))
        if streamdetails:
            # Video details
            for videotrack in streamdetails['videocodec']:
                query = "INSERT INTO streamdetails(idFile, iStreamType, strVideoCodec, fVideoAspect, iVideoWidth, iVideoHeight, strStereoMode) values(?, ?, ?, ?, ?, ?, ?)"
                cursor.execute(query, (fileid, 0, videotrack.get('videocodec'), videotrack.get('aspectratio'), videotrack.get('width'), videotrack.get('height'), videotrack.get('Video3DFormat')))
            
            # Audio details
            for audiotrack in streamdetails['audiocodec']:
                query = "INSERT INTO streamdetails(idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage) values(?, ?, ?, ?, ?)"
                cursor.execute(query, (fileid, 1, audiotrack.get('audiocodec'), audiotrack.get('channels'), audiotrack.get('audiolanguage')))

            # Subtitles details
            for subtitletrack in streamdetails['subtitlelanguage']:
                query = "INSERT INTO streamdetails(idFile, iStreamType, strSubtitleLanguage) values(?, ?, ?)"
                cursor.execute(query, (fileid, 2, subtitletrack))
  
    def addBoxsetToKodiLibrary(self, boxset, connection, cursor):
        
        strSet = boxset['Name']
        cursor.execute("SELECT idSet FROM sets WHERE strSet = ?", (strSet,))
        try:
            setid = cursor.fetchone()[0]
        except:
            # Boxset does not exists
            query = "INSERT INTO sets(idSet, strSet) values(?, ?)"
            cursor.execute(query, (None, strSet))
            # Get the setid of the new boxset
            cursor.execute("SELECT idSet FROM sets WHERE strSet = ?", (strSet,))
            setid = cursor.fetchone()[0]
        finally:
            # Assign artwork
            currentsetartsql = 'SELECT type, url FROM art where media_type = ? and media_id = ? and url != ""'
            cursor.execute(currentsetartsql, ("set", setid))
            existing_type_map = {}
            rows = cursor.fetchall()
            for row in rows:
                existing_type_map[row[0] ] = row[1]
          
            artwork = {}
            artwork['poster'] = API().getArtwork(boxset, "Primary", mediaType = "boxset")
            artwork['banner'] = API().getArtwork(boxset, "Banner", mediaType = "boxset")
            artwork['clearlogo'] = API().getArtwork(boxset, "Logo", mediaType = "boxset")
            artwork['clearart'] = API().getArtwork(boxset, "Art", mediaType = "boxset")
            artwork['landscape'] = API().getArtwork(boxset, "Thumb", mediaType = "boxset")
            artwork['discart'] = API().getArtwork(boxset, "Disc", mediaType = "boxset")
            artwork['fanart'] = API().getArtwork(boxset, "Backdrop", mediaType = "boxset")
           
            art_types = ['poster','fanart','landscape','clearlogo','clearart','banner','discart']
            for update_type in art_types:
                if ( update_type in existing_type_map ):
                    if ( existing_type_map[update_type] != artwork[update_type] ) and artwork[update_type] != '':
                        setupdateartsql = "UPDATE art SET url = ? where media_type = ? and media_id = ? and type = ?"
                        cursor.execute(setupdateartsql,(artwork[update_type],"set",setid,update_type))
                elif artwork[update_type] != '':
                    setartsql = "INSERT INTO art(media_id, media_type, type, url) VALUES(?, ?, ?, ?)"
                    cursor.execute(setartsql,(setid,"set",update_type,artwork[update_type]))

        return True
    
    def updateBoxsetToKodiLibrary(self, boxsetmovie, boxset, connection, cursor):
        
        strSet = boxset['Name']
        boxsetmovieid = boxsetmovie['Id']
        cursor.execute("SELECT kodi_id FROM emby WHERE emby_id = ?",(boxsetmovieid,))
        try:
            movieid = cursor.fetchone()[0]
            cursor.execute("SELECT idSet FROM sets WHERE strSet = ?", (strSet,))
            setid  =  cursor.fetchone()[0]
        except: pass
        else:
            query = "UPDATE movie SET idSet = ? WHERE idMovie = ?"
            cursor.execute(query, (setid, movieid))

            # Update the checksum in emby table
            query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
            cursor.execute(query, (API().getChecksum(boxsetmovie), boxsetmovieid))