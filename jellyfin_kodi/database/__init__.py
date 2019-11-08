# -*- coding: utf-8 -*-

#################################################################################################

import datetime
import logging
import json
import os
import sqlite3

import xbmc
import xbmcvfs

import jellyfin_db
from helper import _, settings, window, dialog
from objects import obj

#################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

#################################################################################################


UNICODE = type(u"")


class Database(object):

    ''' This should be called like a context.
        i.e. with Database('jellyfin') as db:
            db.cursor
            db.conn.commit()
    '''
    timeout = 120
    discovered = False
    discovered_file = None

    def __init__(self, file=None, commit_close=True):

        ''' file: jellyfin, texture, music, video, :memory: or path to file
        '''
        self.db_file = file or "video"
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

        return self

    def _get_database(self, path, silent=False):

        path = xbmc.translatePath(path).decode('utf-8')

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

        databases = xbmc.translatePath("special://database/").decode('utf-8')
        types = {
            'video': "MyVideos",
            'music': "MyMusic",
            'texture': "Textures"
        }
        database = types[database]
        dirs, files = xbmcvfs.listdir(databases)
        modified = {'file': None, 'time': 0}

        for file in reversed(files):

            if (file.startswith(database) and not file.endswith('-wal') and not file.endswith('-shm') and not file.endswith('db-journal')):

                st = xbmcvfs.Stat(databases + file.decode('utf-8'))
                modified_int = st.st_mtime()
                LOG.debug("Database detected: %s time: %s", file.decode('utf-8'), modified_int)

                if modified_int > modified['time']:

                    modified['time'] = modified_int
                    modified['file'] = file.decode('utf-8')

        LOG.info("Discovered database: %s", modified)
        self.discovered_file = modified['file']

        return xbmc.translatePath("special://database/%s" % modified['file']).decode('utf-8')

    def _sql(self, file):

        ''' Get the database path based on the file objects/obj_map.json
            Compatible check, in the event multiple db version are supported with the same Kodi version.
            Discover by file as a last resort.
        '''
        databases = obj.Objects().objects

        if file not in ('video', 'music', 'texture') or databases.get('database_set%s' % file):
            return self._get_database(databases[file], True)

        discovered = self._discover_database(file) if not databases.get('database_set%s' % file) else None

        try:
            loaded = self._get_database(databases[file]) if file in databases else file
        except Exception as error:
            LOG.exception(error)

            for i in range(1, 10):
                alt_file = "%s-%s" % (file, i)

                try:
                    loaded = self._get_database(databases[alt_file])

                    break
                except KeyError:  # No other db options
                    loaded = None

                    break
                except Exception as error:
                    LOG.exception(error)

        if discovered and discovered != loaded:

            databases[file] = discovered
            self.discovered = True
        else:
            databases[file] = loaded

        databases['database_set%s' % file] = True
        LOG.info("Database locked in: %s", databases[file])

        return databases[file]

    def __exit__(self, exc_type, exc_val, exc_tb):

        ''' Close the connection and cursor.
        '''
        changes = self.conn.total_changes

        if exc_type is not None:  # errors raised
            LOG.error("type: %s value: %s", exc_type, exc_val)

        if self.commit_close and changes:

            LOG.info("[%s] %s rows updated.", self.db_file, changes)
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

        LOG.info("Add missing column jellyfin_parent_id")
        cursor.execute("ALTER TABLE jellyfin ADD COLUMN jellyfin_parent_id 'TEXT'")


def reset():

    ''' Reset both the jellyfin database and the kodi database.
    '''
    from views import Views
    views = Views()

    if not dialog("yesno", heading="{jellyfin}", line1=_(33074)):
        return

    window('jellyfin_should_stop.bool', True)
    count = 10

    while window('jellyfin_sync.bool'):

        LOG.info("Sync is running...")
        count -= 1

        if not count:
            dialog("ok", heading="{jellyfin}", line1=_(33085))

            return

        if xbmc.Monitor().waitForAbort(1):
            return

    reset_kodi()
    reset_jellyfin()
    views.delete_playlists()
    views.delete_nodes()

    if dialog("yesno", heading="{jellyfin}", line1=_(33086)):
        reset_artwork()

    addon_data = xbmc.translatePath("special://profile/addon_data/plugin.video.jellyfin/").decode('utf-8')

    if dialog("yesno", heading="{jellyfin}", line1=_(33087)):

        xbmcvfs.delete(os.path.join(addon_data, "settings.xml"))
        xbmcvfs.delete(os.path.join(addon_data, "data.json"))
        LOG.info("[ reset settings ]")

    if xbmcvfs.exists(os.path.join(addon_data, "sync.json")):
        xbmcvfs.delete(os.path.join(addon_data, "sync.json"))

    settings('enableMusic.bool', False)
    settings('MinimumSetup', "")
    settings('MusicRescan.bool', False)
    settings('SyncInstallRunDone.bool', False)
    dialog("ok", heading="{jellyfin}", line1=_(33088))
    xbmc.executebuiltin('RestartApp')


def reset_kodi():

    with Database() as videodb:
        videodb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

        for table in videodb.cursor.fetchall():
            name = table[0]

            if name != 'version':
                videodb.cursor.execute("DELETE FROM " + name)

    if settings('enableMusic.bool') or dialog("yesno", heading="{jellyfin}", line1=_(33162)):

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
    thumbnails = xbmc.translatePath('special://thumbnails/').decode('utf-8')

    if xbmcvfs.exists(thumbnails):
        dirs, ignore = xbmcvfs.listdir(thumbnails)

        for directory in dirs:
            ignore, thumbs = xbmcvfs.listdir(os.path.join(thumbnails, directory.decode('utf-8')))

            for thumb in thumbs:
                LOG.debug("DELETE thumbnail %s", thumb)
                xbmcvfs.delete(os.path.join(thumbnails, directory.decode('utf-8'), thumb.decode('utf-8')))

    with Database('texture') as texdb:
        texdb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")

        for table in texdb.cursor.fetchall():
            name = table[0]

            if name != 'version':
                texdb.cursor.execute("DELETE FROM " + name)

    LOG.info("[ reset artwork ]")


def get_sync():

    path = xbmc.translatePath("special://profile/addon_data/plugin.video.jellyfin/").decode('utf-8')

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)

    try:
        with open(os.path.join(path, 'sync.json'), 'rb') as infile:
            sync = json.load(infile, encoding='utf-8')
    except Exception:
        sync = {}

    sync['Libraries'] = sync.get('Libraries', [])
    sync['RestorePoint'] = sync.get('RestorePoint', {})
    sync['Whitelist'] = list(set(sync.get('Whitelist', [])))
    sync['SortedViews'] = sync.get('SortedViews', [])

    return sync


def save_sync(sync):

    path = xbmc.translatePath("special://profile/addon_data/plugin.video.jellyfin/").decode('utf-8')

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)

    sync['Date'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    with open(os.path.join(path, 'sync.json'), 'wb') as outfile:
        data = json.dumps(sync, sort_keys=True, indent=4, ensure_ascii=False)
        if isinstance(data, UNICODE):
            data = data.encode('utf-8')
        outfile.write(data)


def get_credentials():

    path = xbmc.translatePath("special://profile/addon_data/plugin.video.jellyfin/").decode('utf-8')

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)

    try:
        with open(os.path.join(path, 'data.json'), 'rb') as infile:
            credentials = json.load(infile, encoding='utf8')
    except Exception:

        try:
            with open(os.path.join(path, 'data.txt'), 'rb') as infile:
                credentials = json.load(infile, encoding='utf-8')
                save_credentials(credentials)

            xbmcvfs.delete(os.path.join(path, 'data.txt'))
        except Exception:
            credentials = {}

    credentials['Servers'] = credentials.get('Servers', [])

    return credentials


def save_credentials(credentials):
    credentials = credentials or {}
    path = xbmc.translatePath("special://profile/addon_data/plugin.video.jellyfin/").decode('utf-8')

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)
    try:
        with open(os.path.join(path, 'data.json'), 'wb') as outfile:
            data = json.dumps(credentials, sort_keys=True, indent=4, ensure_ascii=False)
            if isinstance(data, UNICODE):
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
