# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals
#################################################################################################

import datetime
import json
import os
import sqlite3
import sys
import re

from kodi_six import xbmc, xbmcvfs
from six import text_type

from . import jellyfin_db
from ..helper import translate, settings, window, dialog
from ..helper.utils import translate_path
from ..objects import obj
from ..helper import LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)

ADDON_DATA = translate_path("special://profile/addon_data/plugin.video.jellyfin/")

#################################################################################################


class Database(object):

    ''' This should be called like a context.
        i.e. with Database('jellyfin') as db:
            db.cursor
            db.conn.commit()
    '''
    timeout = 120
    discovered = False
    discovered_file = None

    def __init__(self, db_file=None, commit_close=True):

        ''' file: jellyfin, texture, music, video, :memory: or path to file
        '''
        self.db_file = db_file or "video"
        self.commit_close = commit_close

    def __enter__(self):

        ''' Open the connection and return the Database class.
            This is to allow for the cursor, conn and others to be accessible.
        '''
        self.path = self._sql(self.db_file)
        self.conn = sqlite3.connect(self.path, timeout=self.timeout)
        self.cursor = self.conn.cursor()

        if self.db_file in ('video', 'music', 'texture', 'jellyfin'):
            self.conn.execute("PRAGMA journal_mode=WAL")  # to avoid writing conflict with kodi

        LOG.debug("--->[ database: %s ] %s", self.db_file, id(self.conn))

        if not window('jellyfin_db_check.bool') and self.db_file == 'jellyfin':

            window('jellyfin_db_check.bool', True)
            jellyfin_tables(self.cursor)
            self.conn.commit()

        # Migration for #162
        if self.db_file == 'music':
            query = self.conn.execute('SELECT * FROM path WHERE strPath LIKE "%/emby/%"')
            contents = query.fetchall()
            if contents:
                for item in contents:
                    new_path = item[1].replace('/emby/', '/')
                    self.conn.execute('UPDATE path SET strPath = "{}" WHERE idPath = "{}"'.format(new_path, item[0]))

        return self

    def _get_database(self, path, silent=False):

        path = translate_path(path)

        if not silent:

            if not xbmcvfs.exists(path):
                raise Exception("Database: %s missing" % path)

            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()

            if not len(tables):
                raise Exception("Database: %s malformed?" % path)

        return path

    def _discover_database(self, database):

        ''' Use UpdateLibrary(video) to update the date modified
            on the database file used by Kodi.
        '''
        if database == 'video':

            xbmc.executebuiltin('UpdateLibrary(video)')
            xbmc.sleep(200)

        databases = translate_path("special://database/")
        types = {
            'video': "MyVideos",
            'music': "MyMusic",
            'texture': "Textures"
        }
        database = types[database]
        dirs, files = xbmcvfs.listdir(databases)
        target = {'db_file': '', 'version': 0}

        for db_file in reversed(files):
            if (db_file.startswith(database)
                    and not db_file.endswith('-wal')
                    and not db_file.endswith('-shm')
                    and not db_file.endswith('db-journal')):

                version_string = re.search('{}(.*).db'.format(database), db_file)
                version = int(version_string.group(1))

                if version > target['version']:
                    target['db_file'] = db_file
                    target['version'] = version

        LOG.debug("Discovered database: %s", target)
        self.discovered_file = target['db_file']

        return translate_path("special://database/%s" % target['db_file'])

    def _sql(self, db_file):

        ''' Get the database path based on the file objects/obj_map.json
            Compatible check, in the event multiple db version are supported with the same Kodi version.
            Discover by file as a last resort.
        '''
        databases = obj.Objects().objects

        if db_file not in ('video', 'music', 'texture') or databases.get('database_set%s' % db_file):
            return self._get_database(databases[db_file], True)

        discovered = self._discover_database(db_file) if not databases.get('database_set%s' % db_file) else None

        databases[db_file] = discovered
        self.discovered = True

        databases['database_set%s' % db_file] = True
        LOG.info("Database locked in: %s", databases[db_file])

        return databases[db_file]

    def __exit__(self, exc_type, exc_val, exc_tb):

        ''' Close the connection and cursor.
        '''
        changes = self.conn.total_changes

        if exc_type is not None:  # errors raised
            LOG.error("type: %s value: %s", exc_type, exc_val)

        if self.commit_close and changes:

            LOG.debug("[%s] %s rows updated.", self.db_file, changes)
            self.conn.commit()

        LOG.debug("---<[ database: %s ] %s", self.db_file, id(self.conn))
        self.cursor.close()
        self.conn.close()


def jellyfin_tables(cursor):

    ''' Create the tables for the jellyfin database.
        jellyfin, view, version
    '''
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS jellyfin(
        jellyfin_id TEXT UNIQUE, media_folder TEXT, jellyfin_type TEXT, media_type TEXT,
        kodi_id INTEGER, kodi_fileid INTEGER, kodi_pathid INTEGER, parent_id INTEGER,
        checksum INTEGER, jellyfin_parent_id TEXT)""")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS view(
        view_id TEXT UNIQUE, view_name TEXT, media_type TEXT)""")
    cursor.execute("CREATE TABLE IF NOT EXISTS version(idVersion TEXT)")

    columns = cursor.execute("SELECT * FROM jellyfin")
    if 'jellyfin_parent_id' not in [description[0] for description in columns.description]:

        LOG.debug("Add missing column jellyfin_parent_id")
        cursor.execute("ALTER TABLE jellyfin ADD COLUMN jellyfin_parent_id 'TEXT'")


def reset():

    ''' Reset both the jellyfin database and the kodi database.
    '''
    from ..views import Views
    views = Views()

    if not dialog("yesno", "{jellyfin}", translate(33074)):
        return

    window('jellyfin_should_stop.bool', True)
    count = 10

    while window('jellyfin_sync.bool'):

        LOG.info("Sync is running...")
        count -= 1

        if not count:
            dialog("ok", "{jellyfin}", translate(33085))

            return

        if xbmc.Monitor().waitForAbort(1):
            return

    reset_kodi()
    reset_jellyfin()
    views.delete_playlists()
    views.delete_nodes()

    if dialog("yesno", "{jellyfin}", translate(33086)):
        reset_artwork()

    if dialog("yesno", "{jellyfin}", translate(33087)):

        xbmcvfs.delete(os.path.join(ADDON_DATA, "settings.xml"))
        xbmcvfs.delete(os.path.join(ADDON_DATA, "data.json"))
        LOG.info("[ reset settings ]")

    if xbmcvfs.exists(os.path.join(ADDON_DATA, "sync.json")):
        xbmcvfs.delete(os.path.join(ADDON_DATA, "sync.json"))

    settings('enableMusic.bool', False)
    settings('MinimumSetup', "")
    settings('MusicRescan.bool', False)
    settings('SyncInstallRunDone.bool', False)
    dialog("ok", "{jellyfin}", translate(33088))
    xbmc.executebuiltin('RestartApp')


def reset_kodi():

    with Database() as videodb:
        videodb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

        for table in videodb.cursor.fetchall():
            name = table[0]

            # These tables are populated by Kodi and we shouldn't wipe them
            if name not in ['version', 'videoversiontype']:
                videodb.cursor.execute("DELETE FROM " + name)

    if settings('enableMusic.bool') or dialog("yesno", "{jellyfin}", translate(33162)):

        with Database('music') as musicdb:
            musicdb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

            for table in musicdb.cursor.fetchall():
                name = table[0]

                if name != 'version':
                    musicdb.cursor.execute("DELETE FROM " + name)

    LOG.info("[ reset kodi ]")


def reset_jellyfin():

    with Database('jellyfin') as jellyfindb:
        jellyfindb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

        for table in jellyfindb.cursor.fetchall():
            name = table[0]

            if name not in ('version', 'view'):
                jellyfindb.cursor.execute("DELETE FROM " + name)

            jellyfindb.cursor.execute("DROP table IF EXISTS jellyfin")
            jellyfindb.cursor.execute("DROP table IF EXISTS view")
            jellyfindb.cursor.execute("DROP table IF EXISTS version")

    LOG.info("[ reset jellyfin ]")


def reset_artwork():

    ''' Remove all existing texture.
    '''
    thumbnails = translate_path('special://thumbnails/')

    if xbmcvfs.exists(thumbnails):
        dirs, ignore = xbmcvfs.listdir(thumbnails)

        for directory in dirs:
            ignore, thumbs = xbmcvfs.listdir(os.path.join(thumbnails, directory))

            for thumb in thumbs:
                LOG.debug("DELETE thumbnail %s", thumb)
                xbmcvfs.delete(os.path.join(thumbnails, directory, thumb))

    with Database('texture') as texdb:
        texdb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

        for table in texdb.cursor.fetchall():
            name = table[0]

            if name != 'version':
                texdb.cursor.execute("DELETE FROM " + name)

    LOG.info("[ reset artwork ]")


def get_sync():
    if (3, 0) <= sys.version_info < (3, 6):
        LOG.error("Python versions 3.0-3.5 are NOT supported.")

    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)

    try:
        with open(os.path.join(ADDON_DATA, 'sync.json'), 'rb') as infile:
            sync = json.load(infile)
    except Exception:
        sync = {}

    sync['Libraries'] = sync.get('Libraries', [])
    sync['RestorePoint'] = sync.get('RestorePoint', {})
    sync['Whitelist'] = list(set(sync.get('Whitelist', [])))
    sync['SortedViews'] = sync.get('SortedViews', [])

    # Temporary cleanup from #494/#511, remove in a future version
    sync['Libraries'] = [lib_id for lib_id in sync['Libraries'] if ',' not in lib_id]

    return sync


def save_sync(sync):

    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)

    sync['Date'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    with open(os.path.join(ADDON_DATA, 'sync.json'), 'wb') as outfile:
        data = json.dumps(sync, sort_keys=True, indent=4, ensure_ascii=False)
        if isinstance(data, text_type):
            data = data.encode('utf-8')
        outfile.write(data)


def get_credentials():
    if (3, 0) <= sys.version_info < (3, 6):
        LOG.error("Python versions 3.0-3.5 are NOT supported.")

    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)

    try:
        with open(os.path.join(ADDON_DATA, 'data.json'), 'rb') as infile:
            credentials = json.load(infile)
    except IOError:
        credentials = {}

    credentials['Servers'] = credentials.get('Servers', [])

    # Migration for #145
    # TODO: CLEANUP for 1.0.0 release
    for server in credentials['Servers']:
        # Functionality removed in #60
        if 'RemoteAddress' in server:
            del server['RemoteAddress']
        if 'ManualAddress' in server:
            server['address'] = server['ManualAddress']
            del server['ManualAddress']
            # If manual is present, local should always be here, but better to be safe
            if 'LocalAddress' in server:
                del server['LocalAddress']
        elif 'LocalAddress' in server:
            server['address'] = server['LocalAddress']
            del server['LocalAddress']
        if 'LastConnectionMode' in server:
            del server['LastConnectionMode']

    return credentials


def save_credentials(credentials):
    credentials = credentials or {}

    if not xbmcvfs.exists(ADDON_DATA):
        xbmcvfs.mkdirs(ADDON_DATA)
    try:
        with open(os.path.join(ADDON_DATA, 'data.json'), 'wb') as outfile:
            data = json.dumps(credentials, sort_keys=True, indent=4, ensure_ascii=False)
            if isinstance(data, text_type):
                data = data.encode('utf-8')
            outfile.write(data)
    except Exception:
        LOG.exception("Failed to save credentials:")


def get_item(kodi_id, media):

    ''' Get jellyfin item based on kodi id and media.
    '''
    with Database('jellyfin') as jellyfindb:
        item = jellyfin_db.JellyfinDatabase(jellyfindb.cursor).get_full_item_by_kodi_id(kodi_id, media)

        if not item:
            LOG.debug("Not an jellyfin item")

            return

    return item
