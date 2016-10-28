# -*- coding: utf-8 -*-

##################################################################################################

import logging

from _kodi_common import KodiItems

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class KodiMusicVideos(KodiItems):


    def __init__(self, cursor):
        self.cursor = cursor

        KodiItems.__init__(self)

    def create_entry(self):
        self.cursor.execute("select coalesce(max(idMVideo),0) from musicvideo")
        kodi_id = self.cursor.fetchone()[0] + 1

        return kodi_id

    def get_musicvideo(self, kodi_id):

        query = "SELECT * FROM musicvideo WHERE idMVideo = ?"
        self.cursor.execute(query, (kodi_id,))
        try:
            kodi_id = self.cursor.fetchone()[0]
        except TypeError:
            kodi_id = None

        return kodi_id

    def add_musicvideo(self, *args):

        query = (
            '''
            INSERT INTO musicvideo(
                idMVideo, idFile, c00, c04, c05, c06, c07, c08, c09, c10, c11, c12)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.cursor.execute(query, (args))

    def update_musicvideo(self, *args):

        query = ' '.join((

            "UPDATE musicvideo",
            "SET c00 = ?, c04 = ?, c05 = ?, c06 = ?, c07 = ?, c08 = ?, c09 = ?, c10 = ?,",
                "c11 = ?, c12 = ?"
            "WHERE idMVideo = ?"
        ))
        self.cursor.execute(query, (args))

    def remove_musicvideo(self, kodi_id, file_id):
        self.cursor.execute("DELETE FROM musicvideo WHERE idMVideo = ?", (kodi_id,))
        self.cursor.execute("DELETE FROM files WHERE idFile = ?", (file_id,))
