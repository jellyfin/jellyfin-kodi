# -*- coding: utf-8 -*-

##################################################################################################

import logging

from _kodi_common import KodiItems

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class KodiTVShows(KodiItems):


    def __init__(self, cursor):
        self.cursor = cursor

        KodiItems.__init__(self)

    def create_entry(self):
        self.cursor.execute("select coalesce(max(idShow),0) from tvshow")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_season(self):
        self.cursor.execute("select coalesce(max(idSeason),0) from seasons")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def create_entry_episode(self):
        self.cursor.execute("select coalesce(max(idEpisode),0) from episode")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def get_tvshow(self, kodi_id):

        query = "SELECT * FROM tvshow WHERE idShow = ?"
        self.cursor.execute(query, (kodi_id,))
        try:
            kodi_id = self.cursor.fetchone()[0]
        except TypeError:
            kodi_id = None

        return kodi_id

    def get_episode(self, kodi_id):

        query = "SELECT * FROM episode WHERE idEpisode = ?"
        self.cursor.execute(query, (kodi_id,))
        try:
            kodi_id = self.cursor.fetchone()[0]
        except TypeError:
            kodi_id = None

        return kodi_id

    def add_tvshow(self, *args):

        query = (
            '''
            INSERT INTO tvshow(idShow, c00, c01, c04, c05, c08, c09, c12, c13, c14, c15)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def update_tvshow(self, *args):

        query = ' '.join((

            "UPDATE tvshow",
            "SET c00 = ?, c01 = ?, c04 = ?, c05 = ?, c08 = ?, c09 = ?,",
                "c12 = ?, c13 = ?, c14 = ?, c15 = ?",
            "WHERE idShow = ?"
        ))
        self.cursor.execute(query, (args))

    def link_tvshow(self, show_id, path_id):
        query = "INSERT OR REPLACE INTO tvshowlinkpath(idShow, idPath) values(?, ?)"
        self.cursor.execute(query, (show_id, path_id))

    def get_season(self, show_id, number, name=None):

        query = ' '.join((

            "SELECT idSeason",
            "FROM seasons",
            "WHERE idShow = ?",
            "AND season = ?"
        ))
        self.cursor.execute(query, (show_id, number,))
        try:
            season_id = self.cursor.fetchone()[0]
        except TypeError:
            season_id = self._add_season(show_id, number)

        if self.kodi_version > 15 and name is not None:
            query = "UPDATE seasons SET name = ? WHERE idSeason = ?"
            self.cursor.execute(query, (name, season_id))

        return season_id

    def _add_season(self, show_id, number):

        season_id = self.create_entry_season()
        query = "INSERT INTO seasons(idSeason, idShow, season) values(?, ?, ?)"
        self.cursor.execute(query, (season_id, show_id, number))

        return season_id

    def add_episode(self, *args):
        query = (
            '''
            INSERT INTO episode(
                idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                idShow, c15, c16)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def add_episode_16(self, *args):
        query = (
            '''
            INSERT INTO episode(
                idEpisode, idFile, c00, c01, c03, c04, c05, c09, c10, c12, c13, c14,
                idShow, c15, c16, idSeason)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def update_episode(self, *args):
        query = ' '.join((

            "UPDATE episode",
            "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idShow = ?",
            "WHERE idEpisode = ?"
        ))
        self.cursor.execute(query, (args))

    def update_episode_16(self, *args):
        query = ' '.join((

            "UPDATE episode",
            "SET c00 = ?, c01 = ?, c03 = ?, c04 = ?, c05 = ?, c09 = ?, c10 = ?,",
                "c12 = ?, c13 = ?, c14 = ?, c15 = ?, c16 = ?, idSeason = ?, idShow = ?",
            "WHERE idEpisode = ?"
        ))
        self.cursor.execute(query, (args))

    def remove_tvshow(self, kodi_id):
        self.cursor.execute("DELETE FROM tvshow WHERE idShow = ?", (kodi_id,))

    def remove_season(self, kodi_id):
        self.cursor.execute("DELETE FROM seasons WHERE idSeason = ?", (kodi_id,))

    def remove_episode(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM episode WHERE idEpisode = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))
