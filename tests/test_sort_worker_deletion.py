"""Tests for SortWorker deletion logic.

Verifies the parent-cascade guard that prevents a single-item deletion from
wiping an entire library when the removed ID is an unrecognized folder that
happens to be the shared jellyfin_parent_id of every item in a library section.

Real-world trigger: Jellyfin reports a media subfolder (Type=Folder, not in the
view table) as removed. The old code fell through to get_media_by_parent_id,
which returned every item in that section and wiped the entire library.

These tests run the REAL jellyfin_kodi.library.SortWorker.run() end to end
(only the Database context manager is monkeypatched to an in-memory sqlite
connection, since it otherwise depends on xbmcvfs paths that don't exist in a
test environment) -- not a hand-copied reimplementation of the dispatch
if/else. A previous version of this file reimplemented the guarded dispatch
logic inline, which meant it passed on any commit regardless of whether the
guard was actually present in SortWorker.run() (confirmed empirically: it
passed unmodified against a96b2fd1808b211f8d604f5957ce56c38d19a5be, the
unpatched commit this PR fixes).
"""

import queue
import sqlite3
import unittest
from unittest.mock import patch

from jellyfin_kodi import library


MEDIA_TYPES = [
    "Movie",
    "BoxSet",
    "MusicVideo",
    "MusicAlbum",
    "MusicArtist",
    "Audio",
    "Episode",
    "Season",
    "Show",
]


class _FakeDatabaseContext:
    """Stand-in for jellyfin_kodi.database.Database("jellyfin") -- wraps a
    plain sqlite3 cursor instead of opening a real Kodi/xbmcvfs-backed file."""

    def __init__(self, cursor):
        self.cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def _make_conn():
    """In-memory DB with the real jellyfin.db schema (view + jellyfin tables)."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE view (
            view_id    TEXT PRIMARY KEY,
            view_name  TEXT,
            media_type TEXT
        )
    """
    )
    conn.execute(
        """
        CREATE TABLE jellyfin (
            jellyfin_id        TEXT PRIMARY KEY,
            jellyfin_parent_id TEXT,
            jellyfin_type      TEXT,
            kodi_id            INTEGER,
            kodi_fileid        INTEGER,
            kodi_pathid        INTEGER,
            parent_id          INTEGER,
            media_type         TEXT,
            checksum           TEXT
        )
    """
    )
    # view table only knows about the top-level library section
    conn.execute(
        "INSERT INTO view VALUES (?, ?, ?)",
        ("lib-view-id", "Movies", "movies"),
    )
    # all 5 items share a common subfolder parent (not in view table)
    for i in range(1, 6):
        conn.execute(
            "INSERT INTO jellyfin VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"item-{i:03d}", "subfolder-id", "Movie", i, i, 1, 1, "movies", "abc"),
        )
    conn.commit()
    return conn


class TestSortWorkerDeletion(unittest.TestCase):

    def setUp(self):
        self.conn = _make_conn()

    def tearDown(self):
        self.conn.close()

    def _dispatch(self, item_id):
        """Feed one id through the REAL SortWorker.run(), return queued items."""
        in_queue = queue.Queue()
        in_queue.put(item_id)
        output = {media: queue.Queue() for media in MEDIA_TYPES}
        worker = library.SortWorker(in_queue, output)

        cursor = self.conn.cursor()
        with patch.object(
            library, "Database", return_value=_FakeDatabaseContext(cursor)
        ):
            worker.run()

        result = []
        for q in output.values():
            while not q.empty():
                result.append(q.get_nowait())
        return result

    def test_direct_item_found(self):
        """A known item ID routes only that one item, no cascade."""
        queued = self._dispatch("item-001")
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["Id"], "item-001")
        self.assertEqual(queued[0]["Type"], "Movie")

    def test_subfolder_id_not_in_view_queues_nothing(self):
        """The prod bug case: subfolder is parent of all items but not a view.

        Before the fix, get_media_by_parent_id('subfolder-id') returned all 5
        items and wiped the entire library section. The guard must block this.
        """
        queued = self._dispatch("subfolder-id")
        self.assertEqual(
            queued, [], "Subfolder ID must not cascade when not in view table"
        )

    def test_unknown_id_not_a_view_queues_nothing(self):
        """A completely unrecognized ID must not cascade."""
        queued = self._dispatch("totally-unknown-id")
        self.assertEqual(queued, [])

    def test_view_id_cascades_children(self):
        """A top-level view/folder ID correctly cascades all its direct children.

        Note: in practice the view table stores top-level library sections.
        Children of those sections use subfolder IDs (not view IDs) as their
        jellyfin_parent_id, so a cascade on the view ID itself will usually
        return zero rows and be a no-op. This test covers the code path for
        completeness and for configurations where items ARE parented directly
        to the view ID.
        """
        # Re-parent one item directly to the view ID to exercise the cascade
        self.conn.execute(
            "UPDATE jellyfin SET jellyfin_parent_id = 'lib-view-id' WHERE jellyfin_id = 'item-001'"
        )
        self.conn.commit()

        queued = self._dispatch("lib-view-id")
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["Id"], "item-001")


if __name__ == "__main__":
    unittest.main()
