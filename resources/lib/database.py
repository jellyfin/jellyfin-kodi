# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sqlite3

import xbmc

#################################################################################################

log = logging.getLogger("EMBY."+__name__)
KODI = xbmc.getInfoLabel('System.BuildVersion')[:2]

#################################################################################################

def video_database():
        
    db_version = {

        '13': 78, # Gotham
        '14': 90, # Helix
        '15': 93, # Isengard
        '16': 99, # Jarvis
        '17': 107 # Krypton
    }

    path = xbmc.translatePath("special://database/MyVideos%s.db"
        % db_version.get(KODI, "")).decode('utf-8')

    return path

def music_database():
    
    db_version = {

        '13': 46, # Gotham
        '14': 48, # Helix
        '15': 52, # Isengard
        '16': 56, # Jarvis
        '17': 60  # Krypton
    }

    path = xbmc.translatePath("special://database/MyMusic%s.db"
        % db_version.get(KODI, "")).decode('utf-8')

    return path


class DatabaseConn(object):
    # To be called as context manager - i.e. with DatabaseConn() as dbconn

    def __init__(self, database_file="video", commit_mode="", timeout=20):
        """
        database_file can be custom: emby, texture, music, video, :memory: or path to the file
        commit_mode set to None to autocommit (isolation_level). See python documentation.
        """
        self.db_file = database_file
        self.commit_mode = commit_mode
        self.timeout = timeout

    def __enter__(self):
        # Open the connection
        self.path = self._SQL(self.db_file)
        log.warn("opening database: %s", self.path)
        self.conn = sqlite3.connect(self.path,
                                    isolation_level=self.commit_mode,
                                    timeout=self.timeout)
        return self.conn

    def _SQL(self, media_type):

        if media_type == "emby":
            return xbmc.translatePath("special://database/emby.db").decode('utf-8')
        elif media_type == "texture":
            return xbmc.translatePath("special://database/Textures13.db").decode('utf-8')
        elif media_type == "music":
            return music_database()
        elif media_type == "video":
            return video_database()
        else: # custom path
            return self.db_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close the connection
        if exc_type is not None:
            # Errors were raised in the with statement
            log.error("rollback: Type: %s Value: %s", exc_type, exc_val)
            self.conn.rollback()
            if not "database is locked" in exc_val:
                raise

        elif self.commit_mode is not None:
            log.warn("commit: %s", self.path)
            self.conn.commit()

        self.conn.close()
