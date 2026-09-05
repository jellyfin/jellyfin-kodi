"""Tests for the shared-path guard in remove_path.

When multiple items (e.g. all music videos) share a single path record,
removing any one of them must NOT delete the path while other files still
reference it.  Previously remove_path deleted unconditionally, causing the
entire musicvideo_view JOIN to return 0 rows.

These tests import the real jellyfin_kodi.objects.kodi.kodi.Kodi.remove_path
directly, rather than a local re-implementation of the guard -- so they
actually fail against an unpatched checkout instead of always passing.
"""

import sqlite3
import unittest

from jellyfin_kodi.objects.kodi.kodi import Kodi


def _make_kodi_cursor():
    """In-memory DB with minimal path/files/musicvideo schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE path (idPath INTEGER PRIMARY KEY, strPath TEXT)")
    conn.execute(
        "CREATE TABLE files (idFile INTEGER PRIMARY KEY, idPath INTEGER, strFileName TEXT)"
    )
    conn.execute(
        "CREATE TABLE musicvideo (idMVideo INTEGER PRIMARY KEY, idFile INTEGER)"
    )
    conn.execute("INSERT INTO path VALUES (1, 'smb://nas/music-videos/')")
    for i in range(1, 4):
        conn.execute(f"INSERT INTO files VALUES ({i}, 1, 'mv{i}.mkv')")
        conn.execute(f"INSERT INTO musicvideo VALUES ({i}, {i})")
    conn.commit()
    return conn


def _make_real_kodi_db(cursor):
    """Real Kodi instance with only .cursor wired up. Bypasses __init__ (artwork
    setup, people cache -- irrelevant to remove_path) so only the actual,
    unmodified remove_path method is exercised."""
    kodi = object.__new__(Kodi)
    kodi.cursor = cursor
    return kodi


class TestRemovePathGuard(unittest.TestCase):

    def setUp(self):
        self.conn = _make_kodi_cursor()
        self.db = _make_real_kodi_db(self.conn.cursor())

    def tearDown(self):
        self.conn.close()

    def test_path_retained_while_other_files_reference_it(self):
        """Removing one file must not delete the path that two others still need."""
        self.conn.execute("DELETE FROM files WHERE idFile = 1")
        self.conn.commit()
        self.db.cursor = self.conn.cursor()

        self.db.remove_path(1)

        row = self.conn.execute("SELECT idPath FROM path WHERE idPath = 1").fetchone()
        self.assertIsNotNone(
            row, "Path must not be deleted while files 2 and 3 still reference it"
        )

    def test_path_deleted_when_no_files_remain(self):
        """Path must be cleaned up once the last referencing file is gone."""
        self.conn.execute("DELETE FROM files WHERE idPath = 1")
        self.conn.commit()
        self.db.cursor = self.conn.cursor()

        self.db.remove_path(1)

        row = self.conn.execute("SELECT idPath FROM path WHERE idPath = 1").fetchone()
        self.assertIsNone(row, "Path should be deleted when no files reference it")

    def test_last_file_triggers_path_cleanup(self):
        """After deleting the last file, remove_path cleans up correctly."""
        self.conn.execute("DELETE FROM files WHERE idFile IN (1, 2)")
        self.conn.commit()
        self.db.cursor = self.conn.cursor()

        # One file still references the path — must survive
        self.db.remove_path(1)
        row = self.conn.execute("SELECT idPath FROM path WHERE idPath = 1").fetchone()
        self.assertIsNotNone(row)

        # Now remove the last file
        self.conn.execute("DELETE FROM files WHERE idFile = 3")
        self.conn.commit()
        self.db.cursor = self.conn.cursor()

        self.db.remove_path(1)
        row = self.conn.execute("SELECT idPath FROM path WHERE idPath = 1").fetchone()
        self.assertIsNone(row, "Path should be removed after the last file is gone")


if __name__ == "__main__":
    unittest.main()
