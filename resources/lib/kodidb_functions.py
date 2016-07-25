# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc

import api
import artwork
import clientinfo

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################

class Kodidb_Functions():

    kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])
    

    def __init__(self, cursor):
        
        self.cursor = cursor
        
        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()
        self.artwork = artwork.Artwork()
        

    def addPath(self, path):

        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        self.cursor.execute(query, (path,))
        try:
            pathid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute("select coalesce(max(idPath),0) from path")
            pathid = self.cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO path(
                    idPath, strPath)

                VALUES (?, ?)
                '''
            )
            self.cursor.execute(query, (pathid, path))

        return pathid

    def getPath(self, path):

        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        self.cursor.execute(query, (path,))
        try:
            pathid = self.cursor.fetchone()[0]
        except TypeError:
            pathid = None

        return pathid

    def addFile(self, filename, pathid):

        query = ' '.join((

            "SELECT idFile",
            "FROM files",
            "WHERE strFilename = ?",
            "AND idPath = ?"
        ))
        self.cursor.execute(query, (filename, pathid,))
        try:
            fileid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute("select coalesce(max(idFile),0) from files")
            fileid = self.cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO files(
                    idFile, strFilename)

                VALUES (?, ?)
                '''
            )
            self.cursor.execute(query, (fileid, filename))

        return fileid

    def getFile(self, fileid):

        query = ' '.join((

            "SELECT strFilename",
            "FROM files",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (fileid,))
        try:
            filename = self.cursor.fetchone()[0]
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
        
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            for country in countries:
                query = ' '.join((

                    "SELECT country_id",
                    "FROM country",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (country,))

                try:
                    country_id = self.cursor.fetchone()[0]

                except TypeError:
                    # Country entry does not exists
                    self.cursor.execute("select coalesce(max(country_id),0) from country")
                    country_id = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO country(country_id, name) values(?, ?)"
                    self.cursor.execute(query, (country_id, country))
                    log.debug("Add country to media, processing: %s" % country)

                finally: # Assign country to content
                    query = (
                        '''
                        INSERT OR REPLACE INTO country_link(
                            country_id, media_id, media_type)
                        
                        VALUES (?, ?, ?)
                        '''
                    )
                    self.cursor.execute(query, (country_id, kodiid, mediatype))
        else:
            # Kodi Helix
            for country in countries:
                query = ' '.join((

                    "SELECT idCountry",
                    "FROM country",
                    "WHERE strCountry = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (country,))

                try:
                    idCountry = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Country entry does not exists
                    self.cursor.execute("select coalesce(max(idCountry),0) from country")
                    idCountry = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO country(idCountry, strCountry) values(?, ?)"
                    self.cursor.execute(query, (idCountry, country))
                    log.debug("Add country to media, processing: %s" % country)
                
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
                        self.cursor.execute(query, (idCountry, kodiid))

    def addPeople(self, kodiid, people, mediatype):
        
        castorder = 1
        for person in people:

            name = person['Name']
            person_type = person['Type']
            thumb = person['imageurl']
            
            # Kodi Isengard, Jarvis, Krypton
            if self.kodiversion in (15, 16, 17):
                query = ' '.join((

                    "SELECT actor_id",
                    "FROM actor",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (name,))
                
                try:
                    actorid = self.cursor.fetchone()[0]

                except TypeError:
                    # Cast entry does not exists
                    self.cursor.execute("select coalesce(max(actor_id),0) from actor")
                    actorid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO actor(actor_id, name) values(?, ?)"
                    self.cursor.execute(query, (actorid, name))
                    log.debug("Add people to media, processing: %s" % name)

                finally:
                    # Link person to content
                    if "Actor" in person_type:
                        role = person.get('Role')
                        query = (
                            '''
                            INSERT OR REPLACE INTO actor_link(
                                actor_id, media_id, media_type, role, cast_order)

                            VALUES (?, ?, ?, ?, ?)
                            '''
                        )
                        self.cursor.execute(query, (actorid, kodiid, mediatype, role, castorder))
                        castorder += 1
                    
                    elif "Director" in person_type:
                        query = (
                            '''
                            INSERT OR REPLACE INTO director_link(
                                actor_id, media_id, media_type)

                            VALUES (?, ?, ?)
                            '''
                        )
                        self.cursor.execute(query, (actorid, kodiid, mediatype))
                    
                    elif person_type in ("Writing", "Writer"):
                        query = (
                            '''
                            INSERT OR REPLACE INTO writer_link(
                                actor_id, media_id, media_type)

                            VALUES (?, ?, ?)
                            '''
                        )
                        self.cursor.execute(query, (actorid, kodiid, mediatype))

                    elif "Artist" in person_type:
                        query = (
                            '''
                            INSERT OR REPLACE INTO actor_link(
                                actor_id, media_id, media_type)
                            
                            VALUES (?, ?, ?)
                            '''
                        )
                        self.cursor.execute(query, (actorid, kodiid, mediatype))
            # Kodi Helix
            else:
                query = ' '.join((

                    "SELECT idActor",
                    "FROM actors",
                    "WHERE strActor = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (name,))
                
                try:
                    actorid = self.cursor.fetchone()[0]

                except TypeError:
                    # Cast entry does not exists
                    self.cursor.execute("select coalesce(max(idActor),0) from actors")
                    actorid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO actors(idActor, strActor) values(?, ?)"
                    self.cursor.execute(query, (actorid, name))
                    log.debug("Add people to media, processing: %s" % name)

                finally:
                    # Link person to content
                    if "Actor" in person_type:
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
                            
                        self.cursor.execute(query, (actorid, kodiid, role, castorder))
                        castorder += 1

                    elif "Director" in person_type:
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

                        self.cursor.execute(query, (actorid, kodiid))

                    elif person_type in ("Writing", "Writer"):
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
                            
                        self.cursor.execute(query, (actorid, kodiid))

                    elif "Artist" in person_type:
                        query = (
                            '''
                            INSERT OR REPLACE INTO artistlinkmusicvideo(
                                idArtist, idMVideo)
                            
                            VALUES (?, ?)
                            '''
                        )
                        self.cursor.execute(query, (actorid, kodiid))

            # Add person image to art table
            if thumb:
                arttype = person_type.lower()

                if "writing" in arttype:
                    arttype = "writer"

                self.artwork.addOrUpdateArt(thumb, actorid, arttype, "thumb", self.cursor)

    def addGenres(self, kodiid, genres, mediatype):

        
        # Kodi Isengard, Jarvis, Krypton
        if self.kodiversion in (15, 16, 17):
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM genre_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype,))

            # Add genres
            for genre in genres:
                
                query = ' '.join((

                    "SELECT genre_id",
                    "FROM genre",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                
                try:
                    genre_id = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Create genre in database
                    self.cursor.execute("select coalesce(max(genre_id),0) from genre")
                    genre_id = self.cursor.fetchone()[0] + 1
                    
                    query = "INSERT INTO genre(genre_id, name) values(?, ?)"
                    self.cursor.execute(query, (genre_id, genre))
                    log.debug("Add Genres to media, processing: %s" % genre)
                
                finally:
                    # Assign genre to item
                    query = (
                        '''
                        INSERT OR REPLACE INTO genre_link(
                            genre_id, media_id, media_type)

                        VALUES (?, ?, ?)
                        '''
                    )
                    self.cursor.execute(query, (genre_id, kodiid, mediatype))
        else:
            # Kodi Helix
            # Delete current genres for clean slate
            if "movie" in mediatype:
                self.cursor.execute("DELETE FROM genrelinkmovie WHERE idMovie = ?", (kodiid,))
            elif "tvshow" in mediatype:
                self.cursor.execute("DELETE FROM genrelinktvshow WHERE idShow = ?", (kodiid,))
            elif "musicvideo" in mediatype:
                self.cursor.execute("DELETE FROM genrelinkmusicvideo WHERE idMVideo = ?", (kodiid,))

            # Add genres
            for genre in genres:

                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                
                try:
                    idGenre = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Create genre in database
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
                    idGenre = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (idGenre, genre))
                    log.debug("Add Genres to media, processing: %s" % genre)
                
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
                        
                    self.cursor.execute(query, (idGenre, kodiid))

    def addStudios(self, kodiid, studios, mediatype):

        for studio in studios:

            if self.kodiversion in (15, 16, 17):
                # Kodi Isengard, Jarvis, Krypton
                query = ' '.join((

                    "SELECT studio_id",
                    "FROM studio",
                    "WHERE name = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (studio,))
                try:
                    studioid = self.cursor.fetchone()[0]
                
                except TypeError:
                    # Studio does not exists.
                    self.cursor.execute("select coalesce(max(studio_id),0) from studio")
                    studioid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(studio_id, name) values(?, ?)"
                    self.cursor.execute(query, (studioid, studio))
                    log.debug("Add Studios to media, processing: %s" % studio)

                finally: # Assign studio to item
                    query = (
                        '''
                        INSERT OR REPLACE INTO studio_link(
                            studio_id, media_id, media_type)
                        
                        VALUES (?, ?, ?)
                        ''')
                    self.cursor.execute(query, (studioid, kodiid, mediatype))
            else:
                # Kodi Helix
                query = ' '.join((

                    "SELECT idstudio",
                    "FROM studio",
                    "WHERE strstudio = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (studio,))
                try:
                    studioid = self.cursor.fetchone()[0]

                except TypeError:
                    # Studio does not exists.
                    self.cursor.execute("select coalesce(max(idstudio),0) from studio")
                    studioid = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(idstudio, strstudio) values(?, ?)"
                    self.cursor.execute(query, (studioid, studio))
                    log.debug("Add Studios to media, processing: %s" % studio)

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
                    self.cursor.execute(query, (studioid, kodiid))

    def addStreams(self, fileid, streamdetails, runtime):
        
        # First remove any existing entries
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (fileid,))
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
                self.cursor.execute(query, (fileid, 0, videotrack['codec'],
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
                self.cursor.execute(query, (fileid, 1, audiotrack['codec'],
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
                self.cursor.execute(query, (fileid, 2, subtitletrack))

    def addPlaystate(self, fileid, resume_seconds, total_seconds, playcount, dateplayed):
        
        # Delete existing resume point
        query = ' '.join((

            "DELETE FROM bookmark",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (fileid,))
        
        # Set watched count
        query = ' '.join((

            "UPDATE files",
            "SET playCount = ?, lastPlayed = ?",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (playcount, dateplayed, fileid))
        
        # Set the resume bookmark
        if resume_seconds:
            self.cursor.execute("select coalesce(max(idBookmark),0) from bookmark")
            bookmarkId =  self.cursor.fetchone()[0] + 1
            query = (
                '''
                INSERT INTO bookmark(
                    idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type)
                
                VALUES (?, ?, ?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (bookmarkId, fileid, resume_seconds, total_seconds,
                "DVDPlayer", 1))

    def addTags(self, kodiid, tags, mediatype):
        
        # First, delete any existing tags associated to the id
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "DELETE FROM tag_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype))
        else:
            # Kodi Helix
            query = ' '.join((

                "DELETE FROM taglinks",
                "WHERE idMedia = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodiid, mediatype))
    
        # Add tags
        log.debug("Adding Tags: %s" % tags)
        for tag in tags:
            self.addTag(kodiid, tag, mediatype)

    def addTag(self, kodiid, tag, mediatype):

        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tag,))
            try:
                tag_id = self.cursor.fetchone()[0]
            
            except TypeError:
                # Create the tag, because it does not exist
                tag_id = self.createTag(tag)
                log.debug("Adding tag: %s" % tag)

            finally:
                # Assign tag to item
                query = (
                    '''
                    INSERT OR REPLACE INTO tag_link(
                        tag_id, media_id, media_type)
                    
                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (tag_id, kodiid, mediatype))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tag,))
            try:
                tag_id = self.cursor.fetchone()[0]
            
            except TypeError:
                # Create the tag
                tag_id = self.createTag(tag)
                log.debug("Adding tag: %s" % tag)
            
            finally:
                # Assign tag to item
                query = (
                    '''
                    INSERT OR REPLACE INTO taglinks(
                        idTag, idMedia, media_type)
                    
                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (tag_id, kodiid, mediatype))

    def createTag(self, name):
        
        # This will create and return the tag_id
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                tag_id = self.cursor.fetchone()[0]
            
            except TypeError:
                self.cursor.execute("select coalesce(max(tag_id),0) from tag")
                tag_id = self.cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(tag_id, name) values(?, ?)"
                self.cursor.execute(query, (tag_id, name))
                log.debug("Create tag_id: %s name: %s" % (tag_id, name))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                tag_id = self.cursor.fetchone()[0]

            except TypeError:
                self.cursor.execute("select coalesce(max(idTag),0) from tag")
                tag_id = self.cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
                self.cursor.execute(query, (tag_id, name))
                log.debug("Create idTag: %s name: %s" % (tag_id, name))

        return tag_id

    def updateTag(self, oldtag, newtag, kodiid, mediatype):

        log.debug("Updating: %s with %s for %s: %s" % (oldtag, newtag, mediatype, kodiid))
        
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
                self.cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception as e:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, oldtag,))
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
                self.cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception as e:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, oldtag,))

    def removeTag(self, kodiid, tagname, mediatype):

        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tagname,))
            try:
                tag_id = self.cursor.fetchone()[0]
            except TypeError:
                return
            else:
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, tag_id,))
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (tagname,))
            try:
                tag_id = self.cursor.fetchone()[0]
            except TypeError:
                return
            else:
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, tag_id,))

    def createBoxset(self, boxsetname):

        log.debug("Adding boxset: %s" % boxsetname)
        query = ' '.join((

            "SELECT idSet",
            "FROM sets",
            "WHERE strSet = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (boxsetname,))
        try:
            setid = self.cursor.fetchone()[0]

        except TypeError:
            self.cursor.execute("select coalesce(max(idSet),0) from sets")
            setid = self.cursor.fetchone()[0] + 1

            query = "INSERT INTO sets(idSet, strSet) values(?, ?)"
            self.cursor.execute(query, (setid, boxsetname))

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

        query = ' '.join((

            "SELECT idSeason",
            "FROM seasons",
            "WHERE idShow = ?",
            "AND season = ?"
        ))
        self.cursor.execute(query, (showid, seasonnumber,))
        try:
            seasonid = self.cursor.fetchone()[0]
        except TypeError:
            self.cursor.execute("select coalesce(max(idSeason),0) from seasons")
            seasonid = self.cursor.fetchone()[0] + 1
            query = "INSERT INTO seasons(idSeason, idShow, season) values(?, ?, ?)"
            self.cursor.execute(query, (seasonid, showid, seasonnumber))

        return seasonid

    def addArtist(self, name, musicbrainz):

        query = ' '.join((

            "SELECT idArtist, strArtist",
            "FROM artist",
            "WHERE strMusicBrainzArtistID = ?"
        ))
        self.cursor.execute(query, (musicbrainz,))
        try:
            result = self.cursor.fetchone()
            artistid = result[0]
            artistname = result[1]

        except TypeError:

            query = ' '.join((

                "SELECT idArtist",
                "FROM artist",
                "WHERE strArtist = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                artistid = self.cursor.fetchone()[0]
            except TypeError:
                self.cursor.execute("select coalesce(max(idArtist),0) from artist")
                artistid = self.cursor.fetchone()[0] + 1
                query = (
                    '''
                    INSERT INTO artist(idArtist, strArtist, strMusicBrainzArtistID)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (artistid, name, musicbrainz))
        else:
            if artistname != name:
                query = "UPDATE artist SET strArtist = ? WHERE idArtist = ?"
                self.cursor.execute(query, (name, artistid,))

        return artistid

    def addAlbum(self, name, musicbrainz):

        query = ' '.join((

            "SELECT idAlbum",
            "FROM album",
            "WHERE strMusicBrainzAlbumID = ?"
        ))
        self.cursor.execute(query, (musicbrainz,))
        try:
            albumid = self.cursor.fetchone()[0]
        except TypeError:
            # Create the album
            self.cursor.execute("select coalesce(max(idAlbum),0) from album")
            albumid = self.cursor.fetchone()[0] + 1
            if self.kodiversion in (15, 16, 17):
                query = (
                    '''
                    INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID, strReleaseType)

                    VALUES (?, ?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (albumid, name, musicbrainz, "album"))
            else: # Helix
                query = (
                    '''
                    INSERT INTO album(idAlbum, strAlbum, strMusicBrainzAlbumID)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (albumid, name, musicbrainz))

        return albumid

    def addMusicGenres(self, kodiid, genres, mediatype):

        if mediatype == "album":

            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM album_genre",
                "WHERE idAlbum = ?"
            ))
            self.cursor.execute(query, (kodiid,))

            for genre in genres:
                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                try:
                    genreid = self.cursor.fetchone()[0]
                except TypeError:
                    # Create the genre
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
                    genreid = self.cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (genreid, genre))

                query = "INSERT OR REPLACE INTO album_genre(idGenre, idAlbum) values(?, ?)"
                self.cursor.execute(query, (genreid, kodiid))

        elif mediatype == "song":
            
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM song_genre",
                "WHERE idSong = ?"
            ))
            self.cursor.execute(query, (kodiid,))

            for genre in genres:
                query = ' '.join((

                    "SELECT idGenre",
                    "FROM genre",
                    "WHERE strGenre = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (genre,))
                try:
                    genreid = self.cursor.fetchone()[0]
                except TypeError:
                    # Create the genre
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
                    genreid = self.cursor.fetchone()[0] + 1
                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (genreid, genre))

                query = "INSERT OR REPLACE INTO song_genre(idGenre, idSong) values(?, ?)"
                self.cursor.execute(query, (genreid, kodiid))