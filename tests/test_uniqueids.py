from unittest.mock import Mock

from jellyfin_kodi.objects.kodi.uniqueids import sync_unique_ids


def test_provider_ids():
    for media in ("movie", "tvshow", "episode"):
        cursor = Mock()
        cursor.fetchone.return_value = (7,)
        assert sync_unique_ids(cursor, media, 1, None) == 7
        assert cursor.execute.call_count == 1
        cursor.fetchall.return_value = [(7, "imdb", "")]
        assert sync_unique_ids(cursor, media, 1, {"Tmdb": "42"}) is None
        assert cursor.execute.call_args.args[1] == (1, media, "42", "tmdb")
        assert sync_unique_ids(cursor, media, 1, {}) is None
        assert "DELETE" in cursor.execute.call_args.args[0]
