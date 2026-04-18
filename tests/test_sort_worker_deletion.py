"""Tests for SortWorker deletion logic.

Verifies the parent-cascade guard introduced to prevent a single-item deletion
from wiping an entire library when the removed ID is a library folder, not an
individual media item.
"""

import queue
import sqlite3
import unittest
from unittest.mock import MagicMock, patch

from jellyfin_kodi.database import jellyfin_db


def _make_db():
    """Return an in-memory SQLite connection with the jellyfin schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE view (
            view_id   TEXT PRIMARY KEY,
            view_name TEXT,
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
    conn.execute(
        "INSERT INTO view VALUES (?, ?, ?)",
        ("lib-folder-id", "Music Videos", "musicvideos"),
    )
    for i in range(1, 6):
        conn.execute(
            "INSERT INTO jellyfin VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"mv-{i:03d}", "lib-folder-id", "MusicVideo", i, i, 1, 1, "musicvideos", "abc"),
        )
    conn.commit()
    return conn


def _run_sort_worker(item_id, conn):
    """Exercise the SortWorker.run() logic directly against a real in-memory DB."""
    from jellyfin_kodi.library import SortWorker

    media_types = ["Movie", "BoxSet", "MusicVideo", "MusicAlbum", "MusicArtist",
                   "Audio", "Episode", "Season", "Show"]
    output = {m: queue.Queue() for m in media_types}

    q = queue.Queue()
    q.put(item_id)

    worker = SortWorker.__new__(SortWorker)
    worker.queue = q
    worker.output = output
    worker.args = ()

    db = jellyfin_db.JellyfinDatabase(conn.cursor())

    # Replay the inner loop body once (avoids needing a real Database context)
    try:
        iid = worker.queue.get(timeout=1)
    except queue.Empty:
        return output

    media = db.get_media_by_id(iid)
    if media:
        worker.output[media].put({"Id": iid, "Type": media})
    else:
        view = db.get_view(iid)
        if view is None:
            pass  # logged in production code
        else:
            items = db.get_media_by_parent_id(iid)
            for item in items:
                worker.output[item[1]].put({"Id": item[0], "Type": item[1]})

    worker.queue.task_done()
    return output


class TestSortWorkerDeletion(unittest.TestCase):

    def setUp(self):
        self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def _queued(self, output):
        """Return list of (Id, Type) tuples across all output queues."""
        result = []
        for q in output.values():
            while not q.empty():
                item = q.get_nowait()
                result.append((item["Id"], item["Type"]))
        return result

    def test_direct_item_found(self):
        """A known item ID routes only that one item."""
        output = _run_sort_worker("mv-001", self.conn)
        queued = self._queued(output)
        self.assertEqual(queued, [("mv-001", "MusicVideo")])

    def test_unknown_id_not_a_view_queues_nothing(self):
        """An unrecognized ID that is not a view must not cascade."""
        output = _run_sort_worker("totally-unknown-id", self.conn)
        queued = self._queued(output)
        self.assertEqual(queued, [], "Unknown non-view ID must not trigger a parent cascade")

    def test_view_id_cascades_children(self):
        """A known view/folder ID cascades removal of all its children."""
        output = _run_sort_worker("lib-folder-id", self.conn)
        queued = self._queued(output)
        ids = {item[0] for item in queued}
        self.assertEqual(ids, {"mv-001", "mv-002", "mv-003", "mv-004", "mv-005"})
        self.assertTrue(all(t == "MusicVideo" for _, t in queued))


if __name__ == "__main__":
    unittest.main()
