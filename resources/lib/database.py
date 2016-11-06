# -*- coding: utf-8 -*-

#################################################################################################

import logging
import sqlite3
from contextlib import closing
import sys
import traceback

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from views import Playlist, VideoNodes
from utils import window, should_stop, settings, language

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

    def __init__(self, database_file="video", commit_on_close=True, timeout=120):
        """
        database_file can be custom: emby, texture, music, video, :memory: or path to the file
        commit_mode set to None to autocommit (isolation_level). See python documentation.
        """
        self.db_file = database_file
        self.commit_on_close = commit_on_close
        self.timeout = timeout

    def __enter__(self):
        # Open the connection
        self.path = self._SQL(self.db_file)
        log.info("opening: %s", self.path)
        #traceback.print_stack()
        
        if settings('dblock') == "true":
            self.conn = sqlite3.connect(self.path, isolation_level=None, timeout=self.timeout)
        else:
            self.conn = sqlite3.connect(self.path, timeout=self.timeout)

        log.info("opened: %s - %s", self.path, id(self.conn))
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

        if self.commit_on_close == True and changes:
            log.info("number of rows updated: %s", changes)
            if self.db_file == "video":
                kodi_commit()
            self.conn.commit()
            log.info("commit: %s", self.path)

        log.info("closing: %s - %s", self.path, id(self.conn))
        self.conn.close()

        
def db_reset():

    dialog = xbmcgui.Dialog()

    if not dialog.yesno(language(29999), language(33074)):
        return

    # first stop any db sync
    window('emby_online', value="reset")
    window('emby_shouldStop', value="true")
    count = 10
    while window('emby_dbScan') == "true":
        log.info("Sync is running, will retry: %s..." % count)
        count -= 1
        if count == 0:
            dialog.ok(language(29999), language(33085))
            return
        xbmc.sleep(1000)

    # Clean up the playlists
    Playlist().delete_playlists()

    # Clean up the video nodes
    VideoNodes().deleteNodes()

    # Wipe the kodi databases
    log.warn("Resetting the Kodi video database.")
    with DatabaseConn('video') as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
            rows = cursor.fetchall()
            for row in rows:
                tablename = row[0]
                if tablename != "version":
                    cursor.execute("DELETE FROM " + tablename)

    if settings('enableMusic') == "true":
        log.warn("Resetting the Kodi music database.")
        with DatabaseConn('music') as conn:
            with closing(conn.cursor()) as cursor:           
                cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
                rows = cursor.fetchall()
                for row in rows:
                    tablename = row[0]
                    if tablename != "version":
                        cursor.execute("DELETE FROM " + tablename)

    # Wipe the emby database
    log.warn("Resetting the Emby database.")
    with DatabaseConn('emby') as conn:
        with closing(conn.cursor()) as cursor:    
            cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
            rows = cursor.fetchall()
            for row in rows:
                tablename = row[0]
                if tablename != "version":
                    cursor.execute("DELETE FROM " + tablename)
            cursor.execute('DROP table IF EXISTS emby')
            cursor.execute('DROP table IF EXISTS view')
            cursor.execute("DROP table IF EXISTS version")

    # Offer to wipe cached thumbnails
    if dialog.yesno(language(29999), language(33086)):
        log.warn("Resetting all cached artwork")
        # Remove all existing textures first
        import artwork
        artwork.Artwork().delete_cache()

    # reset the install run flag
    settings('SyncInstallRunDone', value="false")

    # Remove emby info
    resp = dialog.yesno(language(29999), language(33087))
    if resp:
        import connectmanager
        # Delete the settings
        addon = xbmcaddon.Addon()
        addondir = xbmc.translatePath(
                   "special://profile/addon_data/plugin.video.emby/").decode('utf-8')
        dataPath = "%ssettings.xml" % addondir
        xbmcvfs.delete(dataPath)
        connectmanager.ConnectManager().clear_data()

    dialog.ok(heading=language(29999), line1=language(33088))
    xbmc.executebuiltin('RestartApp')
    return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())
    