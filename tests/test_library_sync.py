import queue
import threading
from unittest.mock import MagicMock, Mock

import pytest

import jellyfin_kodi.library as library_module
from jellyfin_kodi.helper.exceptions import LibraryException

SYNC_TIME = "Mon, 19 Oct 2026 14:48:05 GMT"
OLD_WATERMARK = "2026-10-14T00:00:00Z"


@pytest.fixture
def store(monkeypatch):
    values = {
        "LastIncrementalSync": OLD_WATERMARK,
        "SyncInstallRunDone.bool": True,
        "kodiCompanion.bool": True,
        "syncIndicator": "99",
    }

    def settings(setting, value=None):
        if value is not None:
            values[setting] = value
        return values.get(setting)

    monkeypatch.setattr(library_module, "settings", settings)
    monkeypatch.setattr(library_module, "get_sync", lambda: {"Whitelist": ["lib"]})
    return values


def make_library(sync_queue_result):
    lib = library_module.Library.__new__(library_module.Library)
    lib.server = Mock()
    lib.server.config.data = {"server-time": SYNC_TIME}
    lib.server.jellyfin.get_item.return_value = {"CollectionType": "movies"}

    def get_sync_queue(date, filters):
        if isinstance(sync_queue_result, Exception):
            raise sync_queue_result
        return sync_queue_result

    lib.server.jellyfin.get_sync_queue.side_effect = get_sync_queue
    lib.player = Mock()
    lib.player.isPlayingVideo.return_value = False
    lib.updated = Mock()
    lib.userdata = Mock()
    lib.removed = Mock()
    return lib


def queue_result(added=(), updated=(), userdata=(), removed=()):
    return {
        "ItemsAdded": list(added),
        "ItemsUpdated": list(updated),
        "UserDataChanged": list(userdata),
        "ItemsRemoved": list(removed),
    }


def test_watermark_waits_until_queued_updates_are_written(store):
    lib = make_library(queue_result(added=["new-episode"]))

    assert lib.fast_sync()
    lib.updated.assert_called_once_with(["new-episode"])
    assert store["LastIncrementalSync"] == OLD_WATERMARK

    # service() calls this once the worker threads have drained
    lib.commit_pending_sync()
    assert store["LastIncrementalSync"] == "2026-10-19T14:46:05Z"
    assert lib.pending_sync_time is None


def test_websocket_only_drain_does_not_move_watermark(store):
    lib = make_library(queue_result())
    lib.pending_sync_time = None

    lib.commit_pending_sync()

    assert store["LastIncrementalSync"] == OLD_WATERMARK


def test_empty_sync_queue_advances_watermark_immediately(store):
    lib = make_library(queue_result())

    assert lib.fast_sync()

    assert store["LastIncrementalSync"] == "2026-10-19T14:46:05Z"
    assert lib.pending_sync_time is None


def test_watermark_uses_sync_queue_response_time(store):
    lib = make_library(queue_result(added=["new-episode"]))
    assert lib.fast_sync()

    # A later, unrelated request must not shift the pending watermark
    lib.server.config.data["server-time"] = "Mon, 19 Oct 2026 18:00:00 GMT"
    lib.commit_pending_sync()

    assert store["LastIncrementalSync"] == "2026-10-19T14:46:05Z"


@pytest.mark.parametrize("result", [None, RuntimeError("server error")])
def test_failed_sync_queue_request_keeps_watermark(store, result):
    lib = make_library(result)

    lib.fast_sync()
    lib.commit_pending_sync()

    assert store["LastIncrementalSync"] == OLD_WATERMARK


def test_skipped_large_update_advances_watermark(store, monkeypatch):
    monkeypatch.setattr(library_module, "dialog", lambda *args, **kwargs: True)
    lib = make_library(queue_result(updated=["item-%d" % i for i in range(150)]))

    assert lib.fast_sync()

    lib.updated.assert_not_called()
    assert store["LastIncrementalSync"] == "2026-10-19T14:46:05Z"


def test_periodic_fast_sync_respects_interval(store, monkeypatch):
    now = [10000.0]
    monkeypatch.setattr(library_module.time, "monotonic", lambda: now[0])
    lib = make_library(queue_result())
    lib.pending_refresh = False
    lib.fast_sync = Mock()

    lib.last_fast_sync = now[0] - library_module.FAST_SYNC_INTERVAL + 1
    lib.periodic_fast_sync()
    lib.fast_sync.assert_not_called()

    now[0] += 1
    lib.periodic_fast_sync()
    lib.fast_sync.assert_called_once()


@pytest.mark.parametrize(
    "playing,pending,companion",
    [(True, False, True), (False, True, True), (False, False, False)],
)
def test_periodic_fast_sync_skips_when_busy_or_disabled(
    store, playing, pending, companion
):
    store["kodiCompanion.bool"] = companion
    lib = make_library(queue_result())
    lib.player.isPlayingVideo.return_value = playing
    lib.pending_refresh = pending
    lib.last_fast_sync = 0.0
    lib.fast_sync = Mock()

    lib.periodic_fast_sync()

    lib.fast_sync.assert_not_called()


def test_periodic_fast_sync_survives_errors(store):
    lib = make_library(queue_result())
    lib.pending_refresh = False
    lib.last_fast_sync = 0.0
    lib.server.jellyfin.get_item.side_effect = RuntimeError("server offline")

    # Must not raise, or the library thread's run loop would exit
    lib.periodic_fast_sync()


class FakeWriter:
    def __init__(self, is_done=True, failed=False):
        self.is_done = is_done
        self.failed = failed


def run_service(monkeypatch, lib, **writers):
    """Run one pass of the real service() loop with the workers stubbed out."""
    monkeypatch.setattr(library_module, "window", lambda *args, **kwargs: None)
    monkeypatch.setattr(library_module, "get_screensaver", lambda: "screensaver")
    monkeypatch.setattr(library_module, "set_screensaver", Mock())
    monkeypatch.setattr(library_module.xbmc, "executebuiltin", Mock())
    monkeypatch.setattr(library_module.xbmc, "getCondVisibility", lambda cond: False)
    for worker in (
        "worker_downloads",
        "worker_sort",
        "worker_updates",
        "worker_userdata",
        "worker_remove",
        "worker_notify",
    ):
        setattr(lib, worker, Mock())
    lib.download_threads = []
    lib.writer_threads = {"updated": [], "userdata": [], "removed": []}
    lib.writer_threads.update({name: list(w) for name, w in writers.items()})
    lib.pending_refresh = True
    lib.total_updates = 0
    lib.progress_updates = None
    lib.screensaver = None
    lib.progress_display = 50
    # service() is wrapped by @stop, which needs a running Kodi
    library_module.Library.service.__wrapped__(lib)


def test_service_commits_watermark_when_writers_finish(store, monkeypatch):
    lib = make_library(queue_result(added=["new-episode"]))
    assert lib.fast_sync()

    run_service(monkeypatch, lib, updated=[FakeWriter()])

    assert store["LastIncrementalSync"] == "2026-10-19T14:46:05Z"
    assert lib.pending_sync_time is None
    assert not lib.pending_refresh


@pytest.mark.parametrize("name", ["updated", "userdata", "removed"])
def test_service_keeps_watermark_while_writer_is_running(store, monkeypatch, name):
    lib = make_library(queue_result(added=["new-episode"], removed=["old-episode"]))
    assert lib.fast_sync()

    run_service(monkeypatch, lib, **{name: [FakeWriter(is_done=False)]})

    assert store["LastIncrementalSync"] == OLD_WATERMARK
    assert lib.pending_sync_time is not None
    assert lib.pending_refresh


@pytest.mark.parametrize("name", ["updated", "userdata", "removed"])
def test_service_keeps_watermark_when_a_writer_failed(store, monkeypatch, name):
    lib = make_library(queue_result(added=["new-episode"], removed=["old-episode"]))
    assert lib.fast_sync()

    # One writer failed on an item, another finished cleanly
    writers = {"updated": [FakeWriter()]}
    writers[name] = writers.get(name, []) + [FakeWriter(failed=True)]
    run_service(monkeypatch, lib, **writers)

    assert store["LastIncrementalSync"] == OLD_WATERMARK
    assert lib.pending_sync_time is None
    assert not lib.pending_refresh


def test_failed_writer_does_not_block_the_next_fast_sync(store, monkeypatch):
    lib = make_library(queue_result(added=["new-episode"]))
    assert lib.fast_sync()
    run_service(monkeypatch, lib, updated=[FakeWriter(failed=True)])
    assert store["LastIncrementalSync"] == OLD_WATERMARK

    assert lib.fast_sync()
    run_service(monkeypatch, lib, updated=[FakeWriter()])

    assert store["LastIncrementalSync"] == "2026-10-19T14:46:05Z"


def mock_database(monkeypatch):
    """Replace the Kodi database with a mock that opens as the video database."""
    database = MagicMock()
    database.return_value.__enter__.return_value.db_file = "video"
    monkeypatch.setattr(library_module, "Database", database)
    monkeypatch.setattr(library_module, "window", lambda *args, **kwargs: None)


@pytest.mark.parametrize(
    "worker_name,item,target",
    [
        ("UpdateWorker", {"Type": "Movie", "Name": "x"}, "movie"),
        ("UserDataWorker", {"Type": "Movie"}, "userdata"),
        ("RemovedWorker", {"Type": "Movie", "Id": "x"}, "remove"),
    ],
)
@pytest.mark.parametrize("error", [RuntimeError("boom"), LibraryException("bad")])
def test_writer_marks_failed_when_an_item_raises(
    monkeypatch, worker_name, item, target, error
):
    mock_database(monkeypatch)
    handler = Mock(side_effect=error)
    for cls in ("Movies", "TVShows", "MusicVideos", "Music"):
        monkeypatch.setattr(library_module, cls, Mock())
    monkeypatch.setattr(
        library_module, "Movies", Mock(return_value=Mock(**{target: handler}))
    )
    work = queue.Queue()
    work.put(item)
    kwargs = {"direct_path": False, "server": Mock()}
    if worker_name == "UpdateWorker":
        worker = library_module.UpdateWorker(
            work, queue.Queue(), threading.Lock(), "video", **kwargs
        )
    else:
        worker_class = getattr(library_module, worker_name)
        worker = worker_class(work, threading.Lock(), "video", **kwargs)

    worker.run()

    handler.assert_called_once()
    assert worker.failed
    assert worker.is_done


def test_writer_not_marked_failed_on_success(monkeypatch):
    mock_database(monkeypatch)
    movies = Mock()
    monkeypatch.setattr(library_module, "Movies", Mock(return_value=movies))
    monkeypatch.setattr(library_module, "TVShows", Mock())
    work = queue.Queue()
    work.put({"Type": "Movie", "Id": "x"})
    worker = library_module.RemovedWorker(
        work, threading.Lock(), "video", server=Mock(), direct_path=False
    )

    worker.run()

    movies.remove.assert_called_once_with("x")
    assert not worker.failed
