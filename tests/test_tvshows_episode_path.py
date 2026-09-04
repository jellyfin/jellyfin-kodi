# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import pytest

from jellyfin_kodi.objects import tvshows
from jellyfin_kodi.objects.tvshows import TVShows

LIBRARY_ID = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
SERIES_ID = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
EPISODE_ITEM_ID = "cccccccccccccccccccccccccccccccc"


class FakeTVShows(object):
    """Stand-in for TVShows; get_episode_path_filename only reads these attributes."""

    def __init__(self, direct_path=False, library=None):
        self.direct_path = direct_path
        self.library = library
        self.server = object()


def episode_obj():
    return {
        "Path": "/media/tvshows/Some Show (2024)/Some Show S01E01.mkv",
        "Id": EPISODE_ITEM_ID,
        "SeriesId": SERIES_ID,
        "EpisodeId": 42,
    }


def call(fake, obj):
    return TVShows.get_episode_path_filename(fake, obj)


def test_skips_item_outside_whitelisted_library(monkeypatch):
    """find_library returns {} for items outside the whitelist; skip instead of raising."""
    monkeypatch.setattr(tvshows, "find_library", lambda server, obj: {})
    obj = episode_obj()

    assert call(FakeTVShows(), obj) is False
    assert "LibraryId" not in obj


def test_builds_plugin_path_for_whitelisted_library(monkeypatch):
    monkeypatch.setattr(
        tvshows, "find_library", lambda server, obj: {"Id": LIBRARY_ID, "Name": "TV"}
    )
    obj = episode_obj()

    assert call(FakeTVShows(), obj) is True
    assert obj["LibraryId"] == LIBRARY_ID
    assert obj["Path"] == "plugin://plugin.video.jellyfin/%s/%s/" % (
        LIBRARY_ID,
        SERIES_ID,
    )
    assert obj["Filename"].startswith(obj["Path"] + "?")
    assert "id=%s" % EPISODE_ITEM_ID in obj["Filename"]
    assert obj["FullFilePath"] == obj["Filename"]


def test_known_library_skips_the_lookup(monkeypatch):
    """During a full library sync self.library is set and find_library is never called."""

    def boom(server, obj):
        raise AssertionError("find_library must not be called when self.library is set")

    monkeypatch.setattr(tvshows, "find_library", boom)
    obj = episode_obj()

    assert call(FakeTVShows(library={"Id": LIBRARY_ID}), obj) is True
    assert obj["LibraryId"] == LIBRARY_ID


@pytest.mark.parametrize(
    "path", ["/media/tv/Show/Show S01E01.mkv", "C:\\tv\\Show\\Show S01E01.mkv"]
)
def test_direct_path_mode_is_unaffected(monkeypatch, path):
    monkeypatch.setattr(tvshows, "validate", lambda p: True)
    monkeypatch.setattr(tvshows, "validate_dvd_dir", lambda p: False)
    monkeypatch.setattr(tvshows, "validate_bluray_dir", lambda p: False)

    def boom(server, obj):
        raise AssertionError("find_library must not be called in direct path mode")

    monkeypatch.setattr(tvshows, "find_library", boom)
    obj = episode_obj()
    obj["Path"] = path

    assert call(FakeTVShows(direct_path=True), obj) is True
    assert obj["Filename"] == "Show S01E01.mkv"
    assert obj["FullFilePath"] == obj["Path"] + obj["Filename"]
