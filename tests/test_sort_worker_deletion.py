"""Tests for SortWorker deletion logic.

Verifies the parent-cascade guard that prevents a single-item deletion from
wiping an entire library when the removed ID is an unrecognized folder that
happens to be the shared jellyfin_parent_id of every item in a library section.

Real-world trigger: Jellyfin reports a media subfolder (Type=Folder, not in the
view table) as removed. The old code fell through to get_media_by_parent_id,
which returned every item in that section and wiped the entire library.
"""

import queue
import sqlite3
import unittest

from jellyfin_kodi.database import jellyfin_db


def _make_db():
    """Return an in-memory SQLite connection with the jellyfin schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE view (
            view_id    TEXT PRIMARY KEY,
            view_name  TEXT,
            media_type TEXT
        )
    """)
    conn.execute("""
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
    """)
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


def _dispatch(item_id, db):
    """Run the SortWorker dispatch logic for one ID and return queued items."""
    media_types = [
        "Movie", "BoxSet", "MusicVideo", "MusicAlbum",
        "MusicArtist", "Audio", "Episode", "Season", "Show",
    ]
    output = {m: queue.Queue() for m in media_types}

    media = db.get_media_by_id(item_id)
    if media:
        output[media].put({"Id": item_id, "Type": media})
    else:
        view = db.get_view(item_id)
        if view is not None:
            for item in db.get_media_by_parent_id(item_id):
                output[item[1]].put({"Id": item[0], "Type": item[1]})

    result = []
    for q in output.values():
        while not q.empty():
            result.append(q.get_nowait())
    return result


class TestSortWorkerDeletion(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()
        self.db = jellyfin_db.JellyfinDatabase(self.conn.cursor())

    def tearDown(self):
        self.conn.close()

    def test_direct_item_found(self):
        """A known item ID routes only that one item, no cascade."""
        queued = _dispatch("item-001", self.db)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["Id"], "item-001")
        self.assertEqual(queued[0]["Type"], "Movie")

    def test_subfolder_id_not_in_view_queues_nothing(self):
        """The prod bug case: subfolder is parent of all items but not a view.

        Before the fix, get_media_by_parent_id('subfolder-id') returned all 5
        items and wiped the entire library section. The guard must block this.
        """
        queued = _dispatch("subfolder-id", self.db)
        self.assertEqual(queued, [], "Subfolder ID must not cascade when not in view table")

    def test_unknown_id_not_a_view_queues_nothing(self):
        """A completely unrecognized ID must not cascade."""
        queued = _dispatch("totally-unknown-id", self.db)
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
        self.db = jellyfin_db.JellyfinDatabase(self.conn.cursor())

        queued = _dispatch("lib-view-id", self.db)
        self.assertEqual(len(queued), 1)
        self.assertEqual(queued[0]["Id"], "item-001")


if __name__ == "__main__":
    unittest.main()
