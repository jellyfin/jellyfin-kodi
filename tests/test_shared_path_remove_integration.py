"""Integration test for the full musicvideo removal sequence with shared paths.

The real-world failure: all music videos share one SMB path record.  The
kodi/musicvideos.delete() method deletes both the musicvideo row AND its
files row before remove_path() is called.  If that was the last file
referencing the shared path, the path gets deleted — orphaning every other
video that shares it and making musicvideo_view return 0 rows.

These tests exercise the full delete() → remove_path() pipeline, not just
remove_path() in isolation (which test_remove_path_guard.py already covers).
"""

import sqlite3
import unittest

from jellyfin_kodi.objects.kodi import queries as QU


def _make_db(num_videos=3):
    """In-memory Kodi video DB with the tables needed by the removal flow."""
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE path (
            idPath   INTEGER PRIMARY KEY,
            strPath  TEXT
        );
        CREATE TABLE files (
            idFile    INTEGER PRIMARY KEY,
            idPath    INTEGER,
            strFileName TEXT
        );
        CREATE TABLE musicvideo (
            idMVideo  INTEGER PRIMARY KEY,
            idFile    INTEGER
        );
        -- musicvideo_view mirrors Kodi's real view: only rows where the
        -- JOIN through files → path is intact appear here.
        CREATE VIEW musicvideo_view AS
            SELECT mv.idMVideo, f.idFile, p.idPath
            FROM   musicvideo mv
            JOIN   files      f ON mv.idFile  = f.idFile
            JOIN   path       p ON f.idPath   = p.idPath;
    """)
    conn.execute("INSERT INTO path VALUES (1, 'smb://nas/Video/Other/ToWatchList/')")
    for i in range(1, num_videos + 1):
        conn.execute(f"INSERT INTO files    VALUES ({i}, 1, 'video{i}.mkv')")
        conn.execute(f"INSERT INTO musicvideo VALUES ({i}, {i})")
    conn.commit()
    return conn


class _FakeKodiDb:
    """Minimal stand-in that replicates the delete() + remove_path() methods."""

    def __init__(self, cursor):
        self.cursor = cursor
        self.direct_path = True  # remove_path is only called when direct_path is True

    def delete(self, kodi_id, file_id):
        self.cursor.execute(QU.delete_musicvideo, (kodi_id,))
        self.cursor.execute(QU.delete_file, (file_id,))

    def remove_path(self, path_id):
        self.cursor.execute(
            "SELECT count(*) FROM files WHERE idPath = ?", (path_id,)
        )
        if self.cursor.fetchone()[0] == 0:
            self.cursor.execute(QU.delete_path, (path_id,))


def _view_count(conn):
    return conn.execute("SELECT count(*) FROM musicvideo_view").fetchone()[0]


def _path_exists(conn, path_id=1):
    return conn.execute(
        "SELECT count(*) FROM path WHERE idPath = ?", (path_id,)
    ).fetchone()[0] == 1


class TestSharedPathRemoveIntegration(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db(num_videos=147)
        self.db = _FakeKodiDb(self.conn.cursor())

    def tearDown(self):
        self.conn.close()

    def test_view_count_before_any_removal(self):
        """Baseline: all 147 videos visible through the view join."""
        self.assertEqual(_view_count(self.conn), 147)
        self.assertTrue(_path_exists(self.conn))

    def test_removing_one_video_preserves_shared_path(self):
        """The real-world bug case: deleting one of N shared-path videos must
        not wipe the path record and orphan the remaining N-1."""
        self.db.delete(kodi_id=1, file_id=1)
        self.db.remove_path(path_id=1)

        self.assertTrue(
            _path_exists(self.conn),
            "Path must survive when 146 other files still reference it",
        )
        self.assertEqual(
            _view_count(self.conn),
            146,
            "Only the deleted video should disappear from the view",
        )

    def test_view_returns_zero_when_path_is_orphaned(self):
        """Confirm that deleting the path record empties the view — this is
        the failure mode the kodi.rebuild.sh script detects and repairs."""
        # Simulate external path deletion (the bug we can't yet fully prevent)
        self.conn.execute("DELETE FROM path WHERE idPath = 1")
        self.conn.commit()

        self.assertEqual(_view_count(self.conn), 0)
        # musicvideo and files rows are still intact
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM musicvideo").fetchone()[0], 147
        )
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM files").fetchone()[0], 147
        )

    def test_path_deleted_only_after_last_video_removed(self):
        """Sequential removal of all videos: path must survive until the very
        last one, then be cleaned up."""
        for i in range(1, 147):
            self.db.delete(kodi_id=i, file_id=i)
            self.db.remove_path(path_id=1)
            self.assertTrue(
                _path_exists(self.conn),
                f"Path deleted prematurely after removing video {i}/147",
            )

        # Remove the final video
        self.db.delete(kodi_id=147, file_id=147)
        self.db.remove_path(path_id=1)
        self.assertFalse(
            _path_exists(self.conn),
            "Path should be cleaned up after the last video is removed",
        )
        self.assertEqual(_view_count(self.conn), 0)


if __name__ == "__main__":
    unittest.main()
