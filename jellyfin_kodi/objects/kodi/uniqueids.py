"""Sync Jellyfin provider IDs with Kodi."""

from contextlib import contextmanager

_PROVIDER_KEYS = {
    "movie": {"imdb": "Imdb", "tmdb": "Tmdb"},
    "tvshow": {"tvdb": "Tvdb", "imdb": "Imdb", "tmdb": "Tmdb"},
    "episode": {"tvdb": "Tvdb", "imdb": "Imdb", "tmdb": "Tmdb"},
}
_DEFAULT_PROVIDER = {"movie": "imdb", "tvshow": "tvdb", "episode": "tvdb"}
_DEFAULT_ID_COLUMNS = {
    "movie": ("idMovie", "c09"),
    "tvshow": ("idShow", "c12"),
    "episode": ("idEpisode", "c20"),
}


@contextmanager
def sync_savepoint(cursor):
    """Undo ID changes if an item cannot be inserted."""
    if not cursor.connection.in_transaction:
        cursor.execute("BEGIN")
    cursor.execute("SAVEPOINT jellyfin_provider_ids")
    try:
        yield
    except Exception:
        cursor.execute("ROLLBACK TO SAVEPOINT jellyfin_provider_ids")
        raise
    finally:
        cursor.execute("RELEASE SAVEPOINT jellyfin_provider_ids")


def _clean_provider_id(provider, value):
    """Clean up a provider ID, or return None if its format is invalid."""
    if value is None:
        return None

    value = str(value).strip()
    if provider == "imdb":
        if value[:2].lower() == "tt" and value[2:].isascii() and value[2:].isdigit():
            return "tt" + value[2:]
    elif value.isascii() and value.isdigit() and value.strip("0"):
        return value

    return None


def sync_unique_ids(cursor, media_type, media_id, provider_ids):
    """Sync Jellyfin provider IDs to Kodi.

    Keep IMDb as the default for movies and TVDb for shows and episodes.
    Remove IDs no longer provided by Jellyfin, but leave existing IDs
    unchanged if the provider data is unavailable.
    Return the default ID row, if available.
    """
    providers = _PROVIDER_KEYS[media_type]
    if not isinstance(provider_ids, dict):
        id_column, default_column = _DEFAULT_ID_COLUMNS[media_type]
        cursor.execute(
            f"SELECT {default_column} FROM {media_type} WHERE {id_column} = ?",
            (media_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None

    source = {
        key.lower(): value
        for key, value in provider_ids.items()
        if isinstance(key, str)
    }
    wanted = {
        provider: _clean_provider_id(provider, source.get(source_key.lower()))
        for provider, source_key in providers.items()
    }

    cursor.execute(
        "SELECT uniqueid_id, type, value FROM uniqueid "
        "WHERE media_type = ? AND media_id = ? ORDER BY uniqueid_id",
        (media_type, media_id),
    )
    existing = {}
    duplicates = []
    for unique_id, provider, value in cursor.fetchall():
        if provider not in providers:
            continue
        if provider in existing:
            duplicates.append(unique_id)
        else:
            existing[provider] = (unique_id, value)

    for provider, value in wanted.items():
        previous = existing.get(provider)
        if value is None:
            if previous is not None:
                cursor.execute(
                    "DELETE FROM uniqueid WHERE uniqueid_id = ?", (previous[0],)
                )
            continue
        if previous is None:
            cursor.execute(
                "INSERT INTO uniqueid(media_id, media_type, value, type) "
                "VALUES (?, ?, ?, ?)",
                (media_id, media_type, value, provider),
            )
            existing[provider] = (cursor.lastrowid, value)
        elif previous[1] != value:
            cursor.execute(
                "UPDATE uniqueid SET value = ? WHERE uniqueid_id = ?",
                (value, previous[0]),
            )

    for unique_id in duplicates:
        cursor.execute("DELETE FROM uniqueid WHERE uniqueid_id = ?", (unique_id,))

    default_provider = _DEFAULT_PROVIDER[media_type]
    return existing[default_provider][0] if wanted[default_provider] else None
