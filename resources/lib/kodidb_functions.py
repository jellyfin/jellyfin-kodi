# -*- coding: utf-8 -*-

##################################################################################################

import xbmc

import api
import artwork
import clientinfo
import utils

##################################################################################################


class Kodidb_Functions():

    kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])
    

    def __init__(self, cursor):

        self.cursor = cursor
        
        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.artwork = artwork.Artwork()

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)
        

    def addPath(self, path):

        cursor = self.cursor

        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        cursor.execute(query, (path,))
        try:
            pathid = cursor.fetchone()[0]
        except TypeError:
            cursor.execute("select coalesce(max(idPath),0) from path")
            pathid = cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO path(
                    idPath, strPath)

                VALUES (?, ?)
                '''
            )
            cursor.execute(query, (pathid, path))

        return pathid

    def getPath(self, path):

        cursor = self.cursor

        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        cursor.execute(query, (path,))
        try:
            pathid = cursor.fetchone()[0]
        except TypeError:
            pathid = None

        return pathid

    def addFile(self, filename, pathid):

        cursor = self.cursor

        query = ' '.join((

            "SELECT idFile",
            "FROM files",
            "WHERE strFilename = ?",
            "AND idPath = ?"
        ))
        cursor.execute(query, (filename, pathid,))
        try:
            fileid = cursor.fetchone()[0]
        except TypeError:
            cursor.execute("select coalesce(max(idFile),0) from files")
            fileid = cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO files(
                    idFile, strFilename)

                VALUES (?, ?)
                '''
            )
            cursor.execute(query, (fileid, filename))

        return fileid

    def getFile(self, fileid):

        cursor = self.cursor

        query = ' '.join((

            "SELECT strFilename",
            "FROM files",
            "WHERE idFile = ?"
        ))
        cursor.execute(query, (fileid,))
        try:
            filename = cursor.fetchone()[0]
        except TypeError:
            filename = ""

        return filename

    def removeFile(self, path, filename):
        
        pathid = self.getPath(path)

        if pathid is not None:
            query = ' '.join((

                "DELETE FROM files",
                "WHERE idPath = ?",
                "AND strFilename = ?"
            ))
            self.cursor.execute(query, (pathid, filename,))

    def addCountries(self, kodiid, countries, mediatype):
        
        cursor = self.cursor
        
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            for country in countries:
                query = ' '.join((

                    "SELECT country_id",
                    "FROM country",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (country,))

                try:
                    country_id = cursor.fetchone()[0]

                except TypeError:
                    # Country entry does not exists
                    cursor.execute("select coalesce(max(country_id),0) from country")
                    country_id = cursor.fetchone()[0] + 1

                    query = "INSERT INTO country(country_id, name) values(?, ?)"
                    cursor.execute(query, (country_id, country))
                    self.logMsg("Add country to media, processing: %s" % country, 2)

                finally: # Assign country to content
                    query = (
                        '''
                        INSERT OR REPLACE INTO country_link(
                            country_id, media_id, media_type)
                        
                        VALUES (?, ?, ?)
                        '''
                    )
                    cursor.execute(query, (country_id, kodiid, mediatype))
        else:
            # Kodi Helix
            for country in countries:
                query = ' '.join((

                    "SELECT idCountry",
                    "FROM country",
                    "WHERE strCountry = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (country,))

                try:
                    idCountry = cursor.fetchone()[0]
                
                except TypeError:
                    # Country entry does not exists
                    cursor.execute("select coalesce(max(idCountry),0) from country")
                    idCountry = cursor.fetchone()[0] + 1

                    query = "INSERT INTO country(idCountry, strCountry) values(?, ?)"
                    cursor.execute(query, (idCountry, country))
                    self.logMsg("Add country to media, processing: %s" % country, 2)
                
                finally:
                    # Only movies have a country field
                    if "movie" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO countrylinkmovie(
                                idCountry, idMovie)

                            VALUES (?, ?)
                            '''
                        )
                        cursor.execute(query, (idCountry, kodiid))

    def addPeople(self, kodiid, people, mediatype):
        
        cursor = self.cursor
        artwork = self.artwork
        kodiversion = self.kodiversion

        castorder = 1
        for person in people:

            name = person['Name']
            type = person['Type']
            thumb = person['imageurl']
            
            # Kodi Isengard, Jarvis, Krypton
            if kodiversion in (15, 16, 17):
                query = ' '.join((

                    "SELECT actor_id",
                    "FROM actor",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (name,))
                
                try:
                    actorid = cursor.fetchone()[0]

                except TypeError:
                    # Cast entry does not exists
                    cursor.execute("select coalesce(max(actor_id),0) from actor")
                    actorid = cursor.fetchone()[0] + 1

                    query = "INSERT INTO actor(actor_id, name) values(?, ?)"
                    cursor.execute(query, (actorid, name))
                    self.logMsg("Add people to media, processing: %s" % name, 2)

                finally:
                    # Link person to content
                    if "Actor" in type:
                        role = person.get('Role')
                        query = (
                            '''
                            INSERT OR REPLACE INTO actor_link(
                                actor_id, media_id, media_type, role, cast_order)

                            VALUES (?, ?, ?, ?, ?)
                            '''
                        )
                        cursor.execute(query, (actorid, kodiid, mediatype, role, castorder))
                        castorder += 1
                    
                    elif "Director" in type:
                        query = (
                            '''
                            INSERT OR REPLACE INTO director_link(
                                actor_id, media_id, media_type)

                            VALUES (?, ?, ?)
                            '''
                        )
                        cursor.execute(query, (actorid, kodiid, mediatype))
                    
                    elif type in ("Writing", "Writer"):
                        query = (
                            '''
                            INSERT OR REPLACE INTO writer_link(
                                actor_id, media_id, media_type)

                            VALUES (?, ?, ?)
                            '''
                        )
                        cursor.execute(query, (actorid, kodiid, mediatype))
            # Kodi Helix
            else:
                query = ' '.join((

                    "SELECT idActor",
                    "FROM actors",
                    "WHERE strActor = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (name,))
                
                try:
                    actorid = cursor.fetchone()[0]

                except TypeError:
                    # Cast entry does not exists
                    cursor.execute("select coalesce(max(idActor),0) from actors")
                    actorid = cursor.fetchone()[0] + 1

                    query = "INSERT INTO actors(idActor, strActor) values(?, ?)"
                    cursor.execute(query, (actorid, name))
                    self.logMsg("Add people to media, processing: %s" % name, 2)

                finally:
                    # Link person to content
                    if "Actor" in type:
                        role = person.get('Role')

                        if "movie" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinkmovie(
                                    idActor, idMovie, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        elif "tvshow" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinktvshow(
                                    idActor, idShow, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        elif "episode" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinkepisode(
                                    idActor, idEpisode, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        else: return # Item is invalid
                            
                        cursor.execute(query, (actorid, kodiid, role, castorder))
                        castorder += 1

                    elif "Director" in type:
                        if "movie" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkmovie(
                                    idDirector, idMovie)

                                VALUES (?, ?)
                                '''
                            )
                        elif "tvshow" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinktvshow(
                                    idDirector, idShow)

                                VALUES (?, ?)
                                '''
                            )
                        elif "musicvideo" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkmusicvideo(
                                    idDirector, idMVideo)

                                VALUES (?, ?)
                                '''
                            )

                        elif "episode" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkepisode(
                                    idDirector, idEpisode)

                                VALUES (?, ?)
                                '''
                            )
                        else: return # Item is invalid

                        cursor.execute(query, (actorid, kodiid))

                    elif type in ("Writing", "Writer"):
                        if "movie" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO writerlinkmovie(
                                    idWriter, idMovie)

                                VALUES (?, ?)
                                '''
                            )
                        elif "episode" in mediatype:
                            query = (
                                '''
                                INSERT OR REPLACE INTO writerlinkepisode(
                                    idWriter, idEpisode)

                                VALUES (?, ?)
                                '''
                            )
                        else: return # Item is invalid
                            
                        cursor.execute(query, (actorid, kodiid))

            # Add person image to art table
            if thumb:
                arttype = type.lower()

                if "writing" in arttype:
                    arttype = "writer"

                artwork.addOrUpdateArt(thumb, actorid, arttype, "thumb", cursor)

    def addGenres(self, kodiid, genres, mediatype):

        cursor = self.cursor
        
        # Kodi Isengard, Jarvis, Krypton
        if self.kodiversion in (15, 16, 17):
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM genre_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            cursor.execute(query, (kodiid, mediatype,))

            # Add genres
            for genre in genres:
                
                query = ' '.join((

                    "SELECT genre_id",
                    "FROM genre",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (genre,))
                
                try:
                    genre_id = cursor.fetchone()[0]
                
                except TypeError:
                    # Create genre in database
                    cursor.execute("select coalesce(max(genre_id),0) from genre")
                    genre_id = cursor.fetchone()[0] + 1
                    
                    query = "INSERT INTO genre(genre_id, name) values(?, ?)"
                    cursor.execute(query, (genre_id, genre))
                    self.logMsg("Add Genres to media, processing: %s" % genre, 2)
                
                finally:
                    # Assign genre to item
                    query = (
                        '''
                        INSERT OR REPLACE INTO genre_link(
                            genre_id, media_id, media_type)

                        VALUES (?, ?, ?)
                        '''
                    )
                    cursor.execute(query, (genre_id, kodiid, mediatype))
        else:
            # Kodi Helix
            # Delete current genres for clean slate
            if "movie" in mediatype:
                cursor.execute("DELETE FROM genrelinkmovie WHERE idMovie = ?", (kodiid,))
            elif "tvshow" in mediatype:
                cursor.execute("DELETE FROM genrelinktvshow WHERE idShow = ?", (kodiid,))
            elif "musicvideo" in mediatype:
                cursor.execute("DELETE FROM genrelinkmusicvideo WHERE idMVideo = ?", (kodiid,))

            # Add genres
            for genre in genres:

                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (genre,))
                
                try:
                    idGenre = cursor.fetchone()[0]
                
                except TypeError:
                    # Create genre in database
                    cursor.execute("select coalesce(max(idGenre),0) from genre")
                    idGenre = cursor.fetchone()[0] + 1

                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    cursor.execute(query, (idGenre, genre))
                    self.logMsg("Add Genres to media, processing: %s" % genre, 2)
                
                finally:
                    # Assign genre to item
                    if "movie" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinkmovie(
                                idGenre, idMovie)

                            VALUES (?, ?)
                            '''
                        )
                    elif "tvshow" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinktvshow(
                                idGenre, idShow)

                            VALUES (?, ?)
                            '''
                        )
                    elif "musicvideo" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinkmusicvideo(
                                idGenre, idMVideo)

                            VALUES (?, ?)
                            '''
                        )
                    else: return # Item is invalid
                        
                    cursor.execute(query, (idGenre, kodiid))

    def addStudios(self, kodiid, studios, mediatype):

        cursor = self.cursor
        kodiversion = self.kodiversion

        for studio in studios:

            if kodiversion in (15, 16, 17):
                # Kodi Isengard, Jarvis, Krypton
                query = ' '.join((

                    "SELECT studio_id",
                    "FROM studio",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (studio,))
                try:
                    studioid = cursor.fetchone()[0]
                
                except TypeError:
                    # Studio does not exists.
                    cursor.execute("select coalesce(max(studio_id),0) from studio")
                    studioid = cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(studio_id, name) values(?, ?)"
                    cursor.execute(query, (studioid, studio))
                    self.logMsg("Add Studios to media, processing: %s" % studio, 2)

                finally: # Assign studio to item
                    query = (
                        '''
                        INSERT OR REPLACE INTO studio_link(
                            studio_id, media_id, media_type)
                        
                        VALUES (?, ?, ?)
                        ''')
                    cursor.execute(query, (studioid, kodiid, mediatype))
            else:
                # Kodi Helix
                query = ' '.join((

                    "SELECT idstudio",
                    "FROM studio",
                    "WHERE strstudio = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (studio,))
                try:
                    studioid = cursor.fetchone()[0]

                except TypeError:
                    # Studio does not exists.
                    cursor.execute("select coalesce(max(idstudio),0) from studio")
                    studioid = cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(idstudio, strstudio) values(?, ?)"
                    cursor.execute(query, (studioid, studio))
                    self.logMsg("Add Studios to media, processing: %s" % studio, 2)

                finally: # Assign studio to item
                    if "movie" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkmovie(idstudio, idMovie) 
                            VALUES (?, ?)
                            ''')
                    elif "musicvideo" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkmusicvideo(idstudio, idMVideo) 
                            VALUES (?, ?)
                            ''')
                    elif "tvshow" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinktvshow(idstudio, idShow) 
                            VALUES (?, ?)
                            ''')
                    elif "episode" in mediatype:
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkepisode(idstudio, idEpisode) 
                            VALUES (?, ?)
                            ''')
                    cursor.execute(query, (studioid, kodiid))

    def addStreams(self, fileid, streamdetails, runtime):
        
        cursor = self.cursor

        # First remove any existing entries
        cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (fileid,))
        if streamdetails:
            # Video details
            for videotrack in streamdetails['video']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strVideoCodec, fVideoAspect, 
                        iVideoWidth, iVideoHeight, iVideoDuration ,strStereoMode)
                    
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                cursor.execute(query, (fileid, 0, videotrack['codec'],
                    videotrack['aspect'], videotrack['width'], videotrack['height'],
                    runtime ,videotrack['video3DFormat']))
            
            # Audio details
            for audiotrack in streamdetails['audio']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage)
                    
                    VALUES (?, ?, ?, ?, ?)
                    '''
                )
                cursor.execute(query, (fileid, 1, audiotrack['codec'],
                    audiotrack['channels'], audiotrack['language']))

            # Subtitles details
            for subtitletrack in streamdetails['subtitle']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strSubtitleLanguage)

                    VALUES (?, ?, ?)
                    '''
                )
                cursor.execute(query, (fileid, 2, subtitletrack))

    def addPlaystate(self, fileid, resume_seconds, total_seconds, playcount, dateplayed):
        
        cursor = self.cursor

        # Delete existing resume point
        query = ' '.join((

            "DELETE FROM bookmark",
            "WHERE idFile = ?"
        ))
        cursor.execute(query, (fileid,))
        
        # Set watched count
        query = ' '.join((

            "UPDATE files",
            "SET playCount = ?, lastPlayed = ?",
            "WHERE idFile = ?"
        ))
        cursor.execute(query, (playcount, dateplayed, fileid))
        
        # Set the resume bookmark
        if resume_seconds:
            cursor.execute("select coalesce(max(idBookmark),0) from bookmark")
            bookmarkId =  cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO bookmark(
                    idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type)
                
                VALUES (?, ?, ?, ?, ?, ?)
                '''
            )
            cursor.execute(query, (bookmarkId, fileid, resume_seconds, total_seconds,
                "DVDPlayer", 1))

    def addTags(self, kodiid, tags, mediatype):

        cursor = self.cursor
        
        # First, delete any existing tags associated to the id
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "DELETE FROM tag_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            cursor.execute(query, (kodiid, mediatype))
        else:
            # Kodi Helix
            query = ' '.join((

                "DELETE FROM taglinks",
                "WHERE idMedia = ?",
                "AND media_type = ?"
            ))
            cursor.execute(query, (kodiid, mediatype))
    
        # Add tags
        self.logMsg("Adding Tags: %s" % tags, 2)
        for tag in tags:
            self.addTag(kodiid, tag, mediatype)

    def addTag(self, kodiid, tag, mediatype):

        cursor = self.cursor

        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (tag,))
            try:
                tag_id = cursor.fetchone()[0]
            
            except TypeError:
                # Create the tag, because it does not exist
                tag_id = self.createTag(tag)
                self.logMsg("Adding tag: %s" % tag, 2)

            finally:
                # Assign tag to item
                query = (
                    '''
                    INSERT OR REPLACE INTO tag_link(
                        tag_id, media_id, media_type)
                    
                    VALUES (?, ?, ?)
                    '''
                )
                cursor.execute(query, (tag_id, kodiid, mediatype))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (tag,))
            try:
                tag_id = cursor.fetchone()[0]
            
            except TypeError:
                # Create the tag
                tag_id = self.createTag(tag)
                self.logMsg("Adding tag: %s" % tag, 2)
            
            finally:
                # Assign tag to item
                query = (
                    '''
                    INSERT OR REPLACE INTO taglinks(
                        idTag, idMedia, media_type)
                    
                    VALUES (?, ?, ?)
                    '''
                )
                cursor.execute(query, (tag_id, kodiid, mediatype))

    def createTag(self, name):
        
        cursor = self.cursor

        # This will create and return the tag_id
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (name,))
            try:
                tag_id = cursor.fetchone()[0]
            
            except TypeError:
                cursor.execute("select coalesce(max(tag_id),0) from tag")
                tag_id = cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(tag_id, name) values(?, ?)"
                cursor.execute(query, (tag_id, name))
                self.logMsg("Create tag_id: %s name: %s" % (tag_id, name), 2)
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (name,))
            try:
                tag_id = cursor.fetchone()[0]

            except TypeError:
                cursor.execute("select coalesce(max(idTag),0) from tag")
                tag_id = cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
                cursor.execute(query, (tag_id, name))
                self.logMsg("Create idTag: %s name: %s" % (tag_id, name), 2)

        return tag_id

    def updateTag(self, oldtag, newtag, kodiid, mediatype):

        cursor = self.cursor
        self.logMsg("Updating: %s with %s for %s: %s" % (oldtag, newtag, mediatype, kodiid), 2)
        
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            try: 
                query = ' '.join((

                    "UPDATE tag_link",
                    "SET tag_id = ?",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception as e:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                self.logMsg("Exception: %s" % e, 1)
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                cursor.execute(query, (kodiid, mediatype, oldtag,))
        else:
            # Kodi Helix
            try:
                query = ' '.join((

                    "UPDATE taglinks",
                    "SET idTag = ?",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception as e:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                self.logMsg("Exception: %s" % e, 1)
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                cursor.execute(query, (kodiid, mediatype, oldtag,))

    def removeTag(self, kodiid, tagname, mediatype):

        cursor = self.cursor

        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (tagname,))
            try:
                tag_id = cursor.fetchone()[0]
            except TypeError:
                return
            else:
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                cursor.execute(query, (kodiid, mediatype, tag_id,))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (tagname,))
            try:
                tag_id = cursor.fetchone()[0]
            except TypeError:
                return
            else:
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                cursor.execute(query, (kodiid, mediatype, tag_id,))

    def createBoxset(self, boxsetname):

        cursor = self.cursor
        self.logMsg("Adding boxset: %s" % boxsetname, 2)
        query = ' '.join((

            "SELECT idSet",
            "FROM sets",
            "WHERE strSet = ?",
            "COLLATE NOCASE"
        ))
        cursor.execute(query, (boxsetname,))
        try:
            setid = cursor.fetchone()[0]

        except TypeError:
            cursor.execute("select coalesce(max(idSet),0) from sets")
            setid = cursor.fetchone()[0] + 1

            query = "INSERT INTO sets(idSet, strSet) values(?, ?)"
            cursor.execute(query, (setid, boxsetname))

        return setid

    def assignBoxset(self, setid, movieid):
        
        query = ' '.join((

            "UPDATE movie",
            "SET idSet = ?",
            "WHERE idMovie = ?"
        ))
        self.cursor.execute(query, (setid, movieid,))

    def removefromBoxset(self, movieid):

        query = ' '.join((

            "UPDATE movie",
            "SET idSet = null",
            "WHERE idMovie = ?"
        ))
        self.cursor.execute(query, (movieid,))

    def addSeason(self, showid, seasonnumber):

        cursor = self.cursor

        query = ' '.join((

            "SELECT idSeason",
            "FROM seasons",
            "WHERE idShow = ?",
            "AND season = ?"
        ))
        cursor.execute(query, (showid, seasonnumber,))
        try:
            seasonid = cursor.fetchone()[0]
        except TypeError:
            cursor.execute("select coalesce(max(idSeason),0) from seasons")
            seasonid = cursor.fetchone()[0] + 1
            query = "INSERT INTO seasons(idSeason, idShow, season) values(?, ?, ?)"
            cursor.execute(query, (seasonid, showid, seasonnumber))

        return seasonid

    def addArtist(self, name, musicbrainz):

        cursor = self.cursor

        query = ' '.join((

            "SELECT idArtist, strArtist",
            "FROM artist",
            "WHERE strMusicBrainzArtistID = ?"
        ))
        cursor.execute(query, (musicbrainz,))
        try:
            result = cursor.fetchone()
            artistid = result[0]
            artistname = result[1]

        except TypeError:

            query = ' '.join((

                "SELECT idArtist",
                "FROM artist",
                "WHERE strArtist = ?",
                "COLLATE NOCASE"
            ))
            cursor.execute(query, (name,))
            try:
                artistid = cursor.fetchone()[0]
            except TypeError:
                cursor.execute("select coalesce(max(idArtist),0) from artist")
                artistid = cursor.fetchone()[0] + 1
                query = (
                    '''
                    INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID)

                    VALUES (?, ?, ?)
                    '''
                )
                cursor.execute(query, (artistid, name, musicbrainz))
        else:
            if artistname != name:
                query = "UPDATE artist SET strArtist = ? WHERE idArtist = ?"
                cursor.execute(query, (name, artistid,))

        return artistid

    def addAlbum(self, name, musicbrainz):

        cursor = self.cursor

        query = ' '.join((

            "SELECT idAlbum",
            "FROM album",
            "WHERE strMusicBrainzAlbumID = ?"
        ))
        cursor.execute(query, (musicbrainz,))
        try:
            albumid = cursor.fetchone()[0]
        except TypeError:
            # Create the album
            cursor.execute("select coalesce(max(idAlbum),0) from album")
            albumid = cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID)

                VALUES (?, ?, ?)
                '''
            )
            cursor.execute(query, (albumid, name, musicbrainz))

        return albumid

    def addMusicGenres(self, kodiid, genres, mediatype):

        cursor = self.cursor

        if mediatype == "album":

            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM album_genre",
                "WHERE idAlbum = ?"
            ))
            cursor.execute(query, (kodiid,))

            for genre in genres:
                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (genre,))
                try:
                    genreid = cursor.fetchone()[0]
                except TypeError:
                    # Create the genre
                    cursor.execute("select coalesce(max(idGenre),0) from genre")
                    genreid = cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    cursor.execute(query, (genreid, genre))

                query = "INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) values(?, ?)"
                cursor.execute(query, (genreid, kodiid))

        elif mediatype == "song":
            
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM song_genre",
                "WHERE idSong = ?"
            ))
            cursor.execute(query, (kodiid,))

            for genre in genres:
                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                cursor.execute(query, (genre,))
                try:
                    genreid = cursor.fetchone()[0]
                except TypeError:
                    # Create the genre
                    cursor.execute("select coalesce(max(idGenre),0) from genre")
                    genreid = cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    cursor.execute(query, (genreid, genre))

                query = "INSERT OR REPLACE INTO song_genre(idGenre, idSong) values(?, ?)"
                cursor.execute(query, (genreid, kodiid))