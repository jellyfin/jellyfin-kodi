# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import xml.etree.ElementTree as etree

from jellyfin_kodi.views import Views


def write_playlist(directory, tag):
    view = {"Media": "movies", "Id": "abc123", "Name": tag, "Tag": tag}
    # add_playlist() never touches `self`, so it can be called unbound.
    Views.add_playlist(None, str(directory), view)

    return os.path.join(str(directory), "jellyfinmoviesabc123.xsp")


def test_add_playlist_writes_non_ascii_tag_as_utf8(tmp_path):
    """A non-ASCII library name must be written as literal UTF-8.

    ElementTree.write() defaults to us-ascii, which escapes non-ASCII
    characters as numeric character references. Kodi does not decode those
    inside a smart playlist rule value, so it compares the literal string
    (e.g. "Pel&#237;culas") against the tag name and matches nothing.
    """
    playlist = write_playlist(tmp_path, "Películas")

    with open(playlist, "rb") as f:
        raw = f.read()

    assert "Películas".encode("utf-8") in raw
    assert b"&#" not in raw


def test_add_playlist_does_not_duplicate_existing_rule(tmp_path):
    """The playlist is rewritten on every view refresh, so re-running must
    reuse the existing rule rather than appending a second one."""
    playlist = write_playlist(tmp_path, "Películas")
    write_playlist(tmp_path, "Películas")

    root = etree.parse(playlist).getroot()

    assert [element.text for element in root.findall(".//value")] == ["Películas"]
