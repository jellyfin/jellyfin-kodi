# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc

import artwork

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class KodiItems(object):


    def __init__(self):

        self.artwork = artwork.Artwork()
        self.kodi_version = int(xbmc.getInfoLabel('System.BuildVersion')[:2])

    def create_entry_path(self):
        self.cursor.execute("select coalesce(max(idPath),0) from path")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_file(self):
        self.cursor.execute("select coalesce(max(idFile),0) from files")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_person(self):
        self.cursor.execute("select coalesce(max(actor_id),0) from actor")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_genre(self):
        self.cursor.execute("select coalesce(max(genre_id),0) from genre")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_studio(self):
        self.cursor.execute("select coalesce(max(studio_id),0) from studio")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_bookmark(self):
        self.cursor.execute("select coalesce(max(idBookmark),0) from bookmark")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_tag(self):
        self.cursor.execute("select coalesce(max(tag_id),0) from tag")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def add_path(self, path):

        path_id = self.get_path(path)
        if path_id is None:
            # Create a new entry
            path_id = self.create_entry_path()
            query = (
                '''
                INSERT INTO path(idPath, strPath)

                VALUES (?, ?)
                '''
            )
            self.cursor.execute(query, (path_id, path))

        return path_id

    def get_path(self, path):

        query = ' '.join((

            "SELECT idPath",
            "FROM path",
            "WHERE strPath = ?"
        ))
        self.cursor.execute(query, (path,))
        try:
            path_id = self.cursor.fetchone()[0]
        except TypeError:
            path_id = None

        return path_id

    def update_path(self, path_id, path, media_type, scraper):

        query = ' '.join((

            "UPDATE path",
            "SET strPath = ?, strContent = ?, strScraper = ?, noUpdate = ?",
            "WHERE idPath = ?"
        ))
        self.cursor.execute(query, (path, media_type, scraper, 1, path_id))

    def remove_path(self, path_id):
        self.cursor.execute("DELETE FROM path WHERE idPath = ?", (path_id,))

    def add_file(self, filename, path_id):

        query = ' '.join((

            "SELECT idFile",
            "FROM files",
            "WHERE strFilename = ?",
            "AND idPath = ?"
        ))
        self.cursor.execute(query, (filename, path_id,))
        try:
            file_id = self.cursor.fetchone()[0]
        except TypeError:
            # Create a new entry
            file_id = self.create_entry_file()
            query = (
                '''
                INSERT INTO files(idFile, idPath, strFilename)

                VALUES (?, ?, ?)
                '''
            )
            self.cursor.execute(query, (file_id, path_id, filename))

        return file_id

    def update_file(self, file_id, filename, path_id, date_added):

        query = ' '.join((

            "UPDATE files",
            "SET idPath = ?, strFilename = ?, dateAdded = ?",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (path_id, filename, date_added, file_id))

    def remove_file(self, path, filename):

        path_id = self.get_path(path)
        if path_id is not None:

            query = ' '.join((

                "DELETE FROM files",
                "WHERE idPath = ?",
                "AND strFilename = ?"
            ))
            self.cursor.execute(query, (path_id, filename,))

    def get_filename(self, file_id):

        query = ' '.join((

            "SELECT strFilename",
            "FROM files",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (file_id,))
        try:
            filename = self.cursor.fetchone()[0]
        except TypeError:
            filename = ""

        return filename

    def add_people(self, kodi_id, people, media_type):

        def add_thumbnail(person_id, person, type_):

            thumbnail = person['imageurl']
            if thumbnail:

                art = type_.lower()
                if "writing" in art:
                    art = "writer"

                self.artwork.add_update_art(thumbnail, person_id, art, "thumb", self.cursor)

        def add_link(link_type, person_id, kodi_id, media_type):

            query = (
                "INSERT OR REPLACE INTO " + link_type + "(actor_id, media_id, media_type)"
                "VALUES (?, ?, ?)"
            )
            self.cursor.execute(query, (person_id, kodi_id, media_type))

        cast_order = 1

        if self.kodi_version > 14:

            for person in people:

                name = person['Name']
                type_ = person['Type']
                person_id = self._get_person(name)

                # Link person to content
                if type_ == "Actor":
                    role = person.get('Role')
                    query = (
                        '''
                        INSERT OR REPLACE INTO actor_link(
                            actor_id, media_id, media_type, role, cast_order)

                        VALUES (?, ?, ?, ?, ?)
                        '''
                    )
                    self.cursor.execute(query, (person_id, kodi_id, media_type, role, cast_order))
                    cast_order += 1

                elif type_ == "Director":
                    add_link("director_link", person_id, kodi_id, media_type)

                elif type_ in ("Writing", "Writer"):
                    add_link("writer_link", person_id, kodi_id, media_type)

                elif type_ == "Artist":
                    add_link("actor_link", person_id, kodi_id, media_type)

                add_thumbnail(person_id, person, type_)
        else:
            # TODO: Remove Helix code when Krypton is RC
            for person in people:
                name = person['Name']
                type_ = person['Type']

                query = ' '.join((

                    "SELECT idActor",
                    "FROM actors",
                    "WHERE strActor = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (name,))

                try:
                    person_id = self.cursor.fetchone()[0]

                except TypeError:
                    # Cast entry does not exists
                    self.cursor.execute("select coalesce(max(idActor),0) from actors")
                    person_id = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO actors(idActor, strActor) values(?, ?)"
                    self.cursor.execute(query, (person_id, name))
                    log.debug("Add people to media, processing: %s", name)

                finally:
                    # Link person to content
                    if type_ == "Actor":
                        role = person.get('Role')

                        if media_type == "movie":
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinkmovie(
                                    idActor, idMovie, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        elif media_type == "tvshow":
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinktvshow(
                                    idActor, idShow, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        elif media_type == "episode":
                            query = (
                                '''
                                INSERT OR REPLACE INTO actorlinkepisode(
                                    idActor, idEpisode, strRole, iOrder)

                                VALUES (?, ?, ?, ?)
                                '''
                            )
                        else: return # Item is invalid

                        self.cursor.execute(query, (person_id, kodi_id, role, cast_order))
                        cast_order += 1

                    elif type_ == "Director":
                        if media_type == "movie":
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkmovie(idDirector, idMovie)
                                VALUES (?, ?)
                                '''
                            )
                        elif media_type == "tvshow":
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinktvshow(idDirector, idShow)
                                VALUES (?, ?)
                                '''
                            )
                        elif media_type == "musicvideo":
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkmusicvideo(idDirector, idMVideo)
                                VALUES (?, ?)
                                '''
                            )
                        elif media_type == "episode":
                            query = (
                                '''
                                INSERT OR REPLACE INTO directorlinkepisode(idDirector, idEpisode)
                                VALUES (?, ?)
                                '''
                            )
                        else: return # Item is invalid

                        self.cursor.execute(query, (person_id, kodi_id))

                    elif type_ in ("Writing", "Writer"):
                        if media_type == "movie":
                            query = (
                                '''
                                INSERT OR REPLACE INTO writerlinkmovie(idWriter, idMovie)
                                VALUES (?, ?)
                                '''
                            )
                        elif media_type == "episode":
                            query = (
                                '''
                                INSERT OR REPLACE INTO writerlinkepisode(idWriter, idEpisode)
                                VALUES (?, ?)
                                '''
                            )
                        else: return # Item is invalid

                        self.cursor.execute(query, (person_id, kodi_id))

                    elif type_ == "Artist":
                        query = (
                            '''
                            INSERT OR REPLACE INTO artistlinkmusicvideo(idArtist, idMVideo)
                            VALUES (?, ?)
                            '''
                        )
                        self.cursor.execute(query, (person_id, kodi_id))

                    add_thumbnail(person_id, person, type_)

    def _add_person(self, name):

        person_id = self.create_entry_person()
        query = "INSERT INTO actor(actor_id, name) values(?, ?)"
        self.cursor.execute(query, (person_id, name))
        log.debug("Add people to media, processing: %s", name)

        return person_id

    def _get_person(self, name):

        query = ' '.join((

            "SELECT actor_id",
            "FROM actor",
            "WHERE name = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (name,))

        try:
            person_id = self.cursor.fetchone()[0]
        except TypeError:
            person_id = self._add_person(name)

        return person_id

    def add_genres(self, kodi_id, genres, media_type):

        if self.kodi_version > 14:
            # Delete current genres for clean slate
            query = ' '.join((

                "DELETE FROM genre_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodi_id, media_type,))

            # Add genres
            for genre in genres:

                genre_id = self._get_genre(genre)
                query = (
                    '''
                    INSERT OR REPLACE INTO genre_link(
                        genre_id, media_id, media_type)

                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (genre_id, kodi_id, media_type))
        else:
            # TODO: Remove Helix code when Krypton is RC
            # Delete current genres for clean slate
            if media_type == "movie":
                self.cursor.execute("DELETE FROM genrelinkmovie WHERE idMovie = ?", (kodi_id,))
            elif media_type == "tvshow":
                self.cursor.execute("DELETE FROM genrelinktvshow WHERE idShow = ?", (kodi_id,))
            elif media_type == "musicvideo":
                self.cursor.execute("DELETE FROM genrelinkmusicvideo WHERE idMVideo = ?", (kodi_id,))

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
                    genre_id = self.cursor.fetchone()[0]

                except TypeError:
                    # Create genre in database
                    self.cursor.execute("select coalesce(max(idGenre),0) from genre")
                    genre_id = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO genre(idGenre, strGenre) values(?, ?)"
                    self.cursor.execute(query, (genre_id, genre))
                    log.debug("Add Genres to media, processing: %s", genre)

                finally:
                    # Assign genre to item
                    if media_type == "movie":
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinkmovie(idGenre, idMovie)
                            VALUES (?, ?)
                            '''
                        )
                    elif media_type == "tvshow":
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinktvshow(idGenre, idShow)
                            VALUES (?, ?)
                            '''
                        )
                    elif media_type == "musicvideo":
                        query = (
                            '''
                            INSERT OR REPLACE into genrelinkmusicvideo(idGenre, idMVideo)
                            VALUES (?, ?)
                            '''
                        )
                    else: return # Item is invalid

                    self.cursor.execute(query, (genre_id, kodi_id))

    def _add_genre(self, genre):

        genre_id = self.create_entry_genre()
        query = "INSERT INTO genre(genre_id, name) values(?, ?)"
        self.cursor.execute(query, (genre_id, genre))
        log.debug("Add Genres to media, processing: %s", genre)

        return genre_id

    def _get_genre(self, genre):

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
            genre_id = self._add_genre(genre)

        return genre_id

    def add_studios(self, kodi_id, studios, media_type):

        if self.kodi_version > 14:

            for studio in studios:

                studio_id = self._get_studio(studio)
                query = (
                    '''
                    INSERT OR REPLACE INTO studio_link(studio_id, media_id, media_type)
                    VALUES (?, ?, ?)
                    ''')
                self.cursor.execute(query, (studio_id, kodi_id, media_type))
        else:
            # TODO: Remove Helix code when Krypton is RC
            for studio in studios:

                query = ' '.join((

                    "SELECT idstudio",
                    "FROM studio",
                    "WHERE strstudio = ?",
                    "COLLATE NOCASE"
                ))
                self.cursor.execute(query, (studio,))
                try:
                    studio_id = self.cursor.fetchone()[0]

                except TypeError:
                    # Studio does not exists.
                    self.cursor.execute("select coalesce(max(idstudio),0) from studio")
                    studio_id = self.cursor.fetchone()[0] + 1

                    query = "INSERT INTO studio(idstudio, strstudio) values(?, ?)"
                    self.cursor.execute(query, (studio_id, studio))
                    log.debug("Add Studios to media, processing: %s", studio)

                finally: # Assign studio to item
                    if media_type == "movie":
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkmovie(idstudio, idMovie)
                            VALUES (?, ?)
                            ''')
                    elif media_type == "musicvideo":
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkmusicvideo(idstudio, idMVideo)
                            VALUES (?, ?)
                            ''')
                    elif media_type == "tvshow":
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinktvshow(idstudio, idShow)
                            VALUES (?, ?)
                            ''')
                    elif media_type == "episode":
                        query = (
                            '''
                            INSERT OR REPLACE INTO studiolinkepisode(idstudio, idEpisode)
                            VALUES (?, ?)
                            ''')
                    self.cursor.execute(query, (studio_id, kodi_id))

    def _add_studio(self, studio):

        studio_id = self.create_entry_studio()
        query = "INSERT INTO studio(studio_id, name) values(?, ?)"
        self.cursor.execute(query, (studio_id, studio))
        log.debug("Add Studios to media, processing: %s", studio)

        return studio_id

    def _get_studio(self, studio):

        query = ' '.join((

            "SELECT studio_id",
            "FROM studio",
            "WHERE name = ?",
            "COLLATE NOCASE"
        ))
        self.cursor.execute(query, (studio,))
        try:
            studio_id = self.cursor.fetchone()[0]
        except TypeError:
            studio_id = self._add_studio(studio)

        return studio_id

    def add_streams(self, file_id, streams, runtime):
        # First remove any existing entries
        self.cursor.execute("DELETE FROM streamdetails WHERE idFile = ?", (file_id,))
        if streams:
            # Video details
            for track in streams['video']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strVideoCodec, fVideoAspect,
                        iVideoWidth, iVideoHeight, iVideoDuration ,strStereoMode)

                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (file_id, 0, track['codec'], track['aspect'],
                                            track['width'], track['height'], runtime,
                                            track['video3DFormat']))
            # Audio details
            for track in streams['audio']:
                query = (
                    '''
                    INSERT INTO streamdetails(
                        idFile, iStreamType, strAudioCodec, iAudioChannels, strAudioLanguage)

                    VALUES (?, ?, ?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (file_id, 1, track['codec'], track['channels'],
                                            track['language']))
            # Subtitles details
            for track in streams['subtitle']:
                query = (
                    '''
                    INSERT INTO streamdetails(idFile, iStreamType, strSubtitleLanguage)
                    VALUES (?, ?, ?)
                    '''
                )
                self.cursor.execute(query, (file_id, 2, track))

    def add_playstate(self, file_id, resume, total, playcount, date_played):

        # Delete existing resume point
        self.cursor.execute("DELETE FROM bookmark WHERE idFile = ?", (file_id,))
        # Set watched count
        self.set_playcount(file_id, playcount, date_played)

        if resume:
            bookmark_id = self.create_entry_bookmark()
            query = (
                '''
                INSERT INTO bookmark(
                    idBookmark, idFile, timeInSeconds, totalTimeInSeconds, player, type)

                VALUES (?, ?, ?, ?, ?, ?)
                '''
            )
            self.cursor.execute(query, (bookmark_id, file_id, resume, total, "DVDPlayer", 1))

    def set_playcount(self, file_id, playcount, date_played):

        query = ' '.join((

            "UPDATE files",
            "SET playCount = ?, lastPlayed = ?",
            "WHERE idFile = ?"
        ))
        self.cursor.execute(query, (playcount, date_played, file_id))

    def add_tags(self, kodi_id, tags, media_type):

        if self.kodi_version > 14:
            
            query = ' '.join((

                "DELETE FROM tag_link",
                "WHERE media_id = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodi_id, media_type))

            # Add tags
            log.debug("Adding Tags: %s", tags)
            for tag in tags:
                tag_id = self.get_tag(kodi_id, tag, media_type)
        else:
            # TODO: Remove Helix code when Krypton is RC
            query = ' '.join((

                "DELETE FROM taglinks",
                "WHERE idMedia = ?",
                "AND media_type = ?"
            ))
            self.cursor.execute(query, (kodi_id, media_type))

            # Add tags
            log.debug("Adding Tags: %s", tags)
            for tag in tags:
                tag_id = self.get_tag_old(kodi_id, tag, media_type)

    def _add_tag(self, tag):

        tag_id = self.create_entry_tag()
        query = "INSERT INTO tag(tag_id, name) values(?, ?)"
        self.cursor.execute(query, (tag_id, tag))
        log.debug("Create tag_id: %s name: %s", tag_id, tag)

        return tag_id

    def get_tag(self, kodi_id, tag, media_type):

        if self.kodi_version > 14:

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
                tag_id = self._add_tag(tag)

            query = (
                '''
                INSERT OR REPLACE INTO tag_link(tag_id, media_id, media_type)
                VALUES (?, ?, ?)
                '''
            )
            self.cursor.execute(query, (tag_id, kodi_id, media_type))
        else:
            # TODO: Remove Helix code when Krypton is RC
            tag_id = self.get_tag_old(kodi_id, tag, media_type)

        return tag_id

    def get_tag_old(self, kodi_id, tag, media_type):
        # TODO: Remove Helix code when Krypton is RC
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
            self.cursor.execute("select coalesce(max(idTag),0) from tag")
            tag_id = self.cursor.fetchone()[0] + 1

            query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
            self.cursor.execute(query, (tag_id, tag))
            log.debug("Create idTag: %s name: %s", tag_id, tag)

        finally:
            # Assign tag to item
            query = (
                '''
                INSERT OR REPLACE INTO taglinks(
                    idTag, idMedia, media_type)
                
                VALUES (?, ?, ?)
                '''
            )
            self.cursor.execute(query, (tag_id, kodi_id, media_type))

        return tag_id

    def remove_tag(self, kodi_id, tag, media_type):

        if self.kodi_version > 14:

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
                return
            else:
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.cursor.execute(query, (kodi_id, media_type, tag_id,))
        else:
            # TODO: Remove Helix code when Krypton is RC
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
                return
            else:
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (kodi_id, media_type, tag_id,))
