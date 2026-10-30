from unittest.mock import Mock

from jellyfin_kodi.objects.kodi.uniqueids import sync_unique_ids


def test_provider_ids():
    for media in ("movie", "tvshow", "episode"):
        cursor = Mock()
        cursor.fetchone.return_value = (7,)
        assert sync_unique_ids(cursor, media, 1, None) == 7
        assert cursor.execute.call_count == 1
        cursor.fetchall.return_value = [(7, "imdb", "")]
        cursor.lastrowid = 9
        assert sync_unique_ids(cursor, media, 1, {"Tmdb": "42"}) == 9
        assert cursor.execute.call_args.args[1] == (1, media, "42", "tmdb")
        rows = [(7, "imdb", "tt1"), (9, "tmdb", "42"), (11, "tvdb", "2")]
        cursor.fetchall.return_value = rows
        both = {"Imdb": "tt1", "Tmdb": "42"}
        default = 7 if media == "movie" else 11
        assert sync_unique_ids(cursor, media, 1, dict(both, Tvdb="2")) == default
        default = 7 if media == "movie" else 9
        assert sync_unique_ids(cursor, media, 1, both) == default
        assert sync_unique_ids(cursor, media, 1, {"Imdb": "tt1"}) == 7
        assert sync_unique_ids(cursor, media, 1, {}) is None
        assert "DELETE" in cursor.execute.call_args.args[0]
