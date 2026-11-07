# -*- coding: utf-8 -*-
from unittest.mock import Mock

from jellyfin_kodi.objects.actions import Actions

import pytest

TICKS = 10000000
RUNTIME_TICKS = 3189 * TICKS
RESUME_TICKS = 1234 * TICKS


def _obj(resume_ticks):
    """A BrowseVideo-shaped mapping, only the keys listitem_video touches."""
    return {
        "Album": None,
        "Artists": None,
        "Artwork": {"Backdrop": [], "Thumb": "", "Primary": "primary.png"},
        "Audio": [],
        "ChildCount": None,
        "Container": "mov",
        "Countries": None,
        "DateAdded": "2026-01-01T00:00:00",
        "DatePlayed": None,
        "DbId": 2,
        "Directors": None,
        "Genres": None,
        "Index": None,
        "MediaType": "Video",
        "Mpaa": None,
        "People": None,
        "Plot": None,
        "Premiere": None,
        "ProgramName": None,
        "Rating": None,
        "RecursiveCount": None,
        "Resume": resume_ticks,
        "Runtime": RUNTIME_TICKS,
        "Season": None,
        "SeriesName": None,
        "ShortPlot": None,
        "SortTitle": None,
        "Status": None,
        "Studios": None,
        "Subtitles": [],
        "Tagline": None,
        "Title": "Lights Out",
        "Type": "Episode",
        "UniqueId": None,
        "Unwatched": None,
        "Played": False,
        "PlayCount": None,
        "Video": [],
        "Votes": None,
        "Writers": None,
        "Year": None,
    }


@pytest.fixture
def actions(monkeypatch):
    # adjust_resume reads the resumeJumpBack setting; Kodistubs returns "".
    monkeypatch.setattr("jellyfin_kodi.helper.api.settings", lambda *a, **kw: "0")
    obj = Actions.__new__(Actions)
    obj.server = "http://localhost:8096"
    obj.stack = []
    return obj


def _play(actions, resume_playback, resume_ticks=RESUME_TICKS):
    listitem = Mock()
    tag = listitem.getVideoInfoTag.return_value
    item = {"Id": "abc", "Type": "Episode", "resumePlayback": resume_playback}
    actions.listitem_video(_obj(resume_ticks), listitem, item)
    return listitem, tag


class TestBrowseListing:

    def test_browse_listing_keeps_its_resume_point(self, actions):
        # Browse listings come through here without a resumePlayback key, and they
        # still need the resume point so Kodi draws the progress bar.
        listitem = Mock()
        tag = listitem.getVideoInfoTag.return_value
        item = {"Id": "abc", "Type": "Episode"}

        actions.listitem_video(_obj(RESUME_TICKS), listitem, item)

        tag.setResumePoint.assert_called_once_with(1234.0, 3189.0)


class TestResumeStartOffset:

    def test_resuming_sets_the_resume_point(self, actions):
        # Our own resume path still has to work.
        listitem, tag = _play(actions, resume_playback=True)

        tag.setResumePoint.assert_called_once_with(1234.0, 3189.0)
        listitem.setProperty.assert_any_call("StartOffset", "1234.0")

    def test_not_resuming_leaves_the_resume_point_unset(self, actions):
        # Kodi resumes whenever the listitem has a resume point, even an empty one,
        # which would override the position the caller asked to start at.
        listitem, tag = _play(actions, resume_playback=False)

        tag.setResumePoint.assert_not_called()

    def test_not_resuming_does_not_zero_the_start_offset(self, actions):
        listitem, tag = _play(actions, resume_playback=False)

        properties = [call.args for call in listitem.setProperty.call_args_list]
        assert ("StartOffset", "0") not in properties
        assert ("StartPercent", "0") not in properties
