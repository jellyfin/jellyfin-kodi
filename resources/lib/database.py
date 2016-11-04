# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sqlite3

import xbmc

from utils import window, should_stop

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

def texture_database():
    return xbmc.translatePath("special://database/Textures13.db").decode('utf-8')

def emby_database():
    return xbmc.translatePath("special://database/emby.db").decode('utf-8')

def kodi_commit():
    # verification for the Kodi video scan
    kodi_scan = window('emby_kodiScan') == "true"
    count = 0

    while kodi_scan:
        log.info("kodi scan is running, waiting...")

        if count == 10:
            log.info("flag still active, but will try to commit")
            window('emby_kodiScan', clear=True)

        elif should_stop() or xbmc.Monitor().waitForAbort(1):
            log.info("commit unsuccessful. sync terminating")
            return False

        kodi_scan = window('emby_kodiScan') == "true"
        count += 1

    return True


class DatabaseConn(object):
    # To be called as context manager - i.e. with DatabaseConn() as conn: #dostuff

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
        log.info("opening database: %s", self.path)
        self.conn = sqlite3.connect(self.path,
                                    isolation_level=self.commit_mode,
                                    timeout=self.timeout)
        return self.conn

    def _SQL(self, media_type):

        databases = {
            'emby': emby_database,
            'texture': texture_database,
            'music': music_database,
            'video': video_database
        }
        return databases[media_type]() if media_type in databases else self.db_file

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close the connection
        changes = self.conn.total_changes

        if exc_type is not None:
            # Errors were raised in the with statement
            log.error("Type: %s Value: %s", exc_type, exc_val)
            if "database is locked" in exc_val:
                self.conn.rollback()
            else:
                raise

        elif self.commit_mode is not None and changes:
            log.info("number of rows updated: %s", changes)
            if self.db_file == "video" and kodi_commit():
                self.conn.commit()
            else:
                self.conn.commit()

        log.info("close: %s", self.path)
        self.conn.close()
