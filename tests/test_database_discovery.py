import sqlite3
from types import SimpleNamespace

from jellyfin_kodi import database as database_module
from jellyfin_kodi.database import Database


def test_database_discovery_ignores_unexpected_files_and_opens_highest_version(
    monkeypatch, tmp_path
):
    for version in (130, 131):
        path = tmp_path / "MyVideos{}.db".format(version)
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE database_version (version INTEGER)")
            connection.execute("INSERT INTO database_version VALUES (?)", (version,))

    files = [
        "MyVideos131.db",
        "MyVideos132 - Copy.db",
        "MyVideos999.db-wal",
        "MyVideos998.db-shm",
        "MyVideos997.db-journal",
        "MyVideos130.db",
    ]
    database_prefix = "special://database/"

    def translate_database_path(path):
        if path.startswith(database_prefix):
            return str(tmp_path / path[len(database_prefix) :])
        return path

    monkeypatch.setattr(database_module.xbmcvfs, "listdir", lambda path: ([], files))
    monkeypatch.setattr(database_module, "translate_path", translate_database_path)
    monkeypatch.setattr(
        database_module.obj,
        "Objects",
        lambda: SimpleNamespace(objects={}),
    )

    with Database("video") as database:
        version = database.cursor.execute(
            "SELECT version FROM database_version"
        ).fetchone()

    assert version == (131,)
