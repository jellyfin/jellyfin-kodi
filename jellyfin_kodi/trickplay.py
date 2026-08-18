# -*- coding: utf-8 -*-
"""Helpers for selecting Jellyfin trickplay thumbnails."""
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import time

TRICKPLAY_CACHE_MAX_AGE = 7 * 24 * 60 * 60
TRICKPLAY_CACHE_MAX_BYTES = 64 * 1024 * 1024


def trickplay_profiles(item):
    """Return trickplay profiles from the several server response shapes."""
    def flatten(value):
        if isinstance(value, list):
            profiles = []
            for entry in value:
                profiles.extend(flatten(entry))
            return profiles
        if isinstance(value, dict):
            if value.get("Width"):
                return [value]
            profiles = []
            for entry in value.values():
                profiles.extend(flatten(entry))
            return profiles
        return []

    return flatten(item.get("Trickplay") or [])


def select_profile(item, target_width=320):
    """Choose the smallest available profile at or above target_width."""
    profiles = [profile for profile in trickplay_profiles(item) if profile.get("Width")]
    if not profiles:
        return None

    return min(
        profiles,
        key=lambda profile: (
            0 if int(profile["Width"]) >= target_width else 1,
            abs(int(profile["Width"]) - target_width),
        ),
    )


def next_thumbnail_index(segment_end, interval, thumbnail_count=None):
    """Return the first thumbnail after segment_end.

    Jellyfin reports Interval in milliseconds. The +1 deliberately selects
    the thumbnail immediately after the segment rather than the thumbnail at
    the segment boundary.
    """
    if interval <= 0:
        return None

    index = int((float(segment_end) * 1000) // float(interval)) + 1
    if thumbnail_count is not None and index >= int(thumbnail_count):
        return None
    return index


def thumbnail_location(profile, segment_end):
    """Return sprite sheet and tile coordinates for the next thumbnail."""
    index = next_thumbnail_index(
        segment_end,
        profile.get("Interval"),
        profile.get("ThumbnailCount"),
    )
    if index is None:
        return None

    columns = int(profile.get("TileWidth") or 0)
    rows = int(profile.get("TileHeight") or 0)
    if columns <= 0 or rows <= 0:
        return None

    per_sheet = columns * rows
    return {
        "index": index,
        "sheet": index // per_sheet,
        "tile": index % per_sheet,
        "row": (index % per_sheet) // columns,
        "column": (index % per_sheet) % columns,
    }


def download_thumbnail(server, item_id, profile, location):
    """Download and crop one trickplay thumbnail into Kodi's temp directory."""
    import requests
    import xbmcvfs
    from PIL import Image

    cache_dir = xbmcvfs.translatePath("special://temp/jellyfin/trickplay/")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)

    _cleanup_cache(cache_dir)

    prefix = "%s_%s_%s" % (item_id, profile["Width"], location["sheet"])
    sheet_path = os.path.join(cache_dir, "sheet_%s.jpg" % prefix)
    image_path = os.path.join(
        cache_dir, "thumb_%s_%s.jpg" % (prefix, location["tile"])
    )
    if os.path.exists(image_path):
        return image_path

    if not os.path.exists(sheet_path):
        response = requests.get(
            server.jellyfin.trickplay_sheet_url(
                item_id, profile["Width"], location["sheet"]
            ),
            timeout=5,
            verify=server.config.data.get("auth.ssl", False),
        )
        response.raise_for_status()
        with open(sheet_path, "wb") as sheet_file:
            sheet_file.write(response.content)

    with Image.open(sheet_path) as sheet:
        tile_width = int(profile["Width"])
        tile_height = int(profile["Height"])
        left = location["column"] * tile_width
        top = location["row"] * tile_height
        tile = sheet.crop((left, top, left + tile_width, top + tile_height))
        tile.save(image_path, "JPEG", quality=90)

    return image_path


def _cleanup_cache(
    cache_dir,
    max_age=TRICKPLAY_CACHE_MAX_AGE,
    max_bytes=TRICKPLAY_CACHE_MAX_BYTES,
):
    """Remove old trickplay files and cap the cache size."""
    now = time.time()
    entries = []
    for name in os.listdir(cache_dir):
        path = os.path.join(cache_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            stat = os.stat(path)
        except OSError:
            continue
        if now - stat.st_mtime > max_age:
            try:
                os.remove(path)
            except OSError:
                pass
            continue
        entries.append((stat.st_mtime, stat.st_size, path))

    total_bytes = sum(entry[1] for entry in entries)
    for modified, size, path in sorted(entries):
        if total_bytes <= max_bytes:
            break
        try:
            os.remove(path)
            total_bytes -= size
        except OSError:
            pass
