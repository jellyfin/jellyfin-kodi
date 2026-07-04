# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

from jellyfin_kodi.monitor import order_from_start_index


def _items(*ids):
    return [{"Id": i, "Name": i} for i in ids]


class TestOrderFromStartIndex:

    def test_honors_start_index(self):
        # Casting the second track must start playback on that track.
        result = order_from_start_index(_items("a", "b", "c"), ["a", "b", "c"], 1)
        assert [i["Id"] for i in result] == ["b", "c"]

    def test_start_index_zero_keeps_all(self):
        result = order_from_start_index(_items("a", "b", "c"), ["a", "b", "c"], 0)
        assert [i["Id"] for i in result] == ["a", "b", "c"]

    def test_reorders_to_requested_ids(self):
        # get_items (/Items?Ids=) may return a different order than requested;
        # StartIndex is an index into the requested ItemIds, so reorder first.
        result = order_from_start_index(_items("c", "a", "b"), ["a", "b", "c"], 1)
        assert [i["Id"] for i in result] == ["b", "c"]

    def test_skips_items_the_server_did_not_return(self):
        # "b" was requested but not returned by get_items.
        result = order_from_start_index(_items("a", "c"), ["a", "b", "c"], 0)
        assert [i["Id"] for i in result] == ["a", "c"]
