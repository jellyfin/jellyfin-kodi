# -*- coding: utf-8 -*-

from jellyfin_kodi.helper.api import API

TICKS_PER_SECOND = 10_000_000


def test_get_runtime_aggregates_multipart_movie_runtime():
    item = {
        "RunTimeTicks": 90 * TICKS_PER_SECOND,
    }
    additional_parts = [
        {"RunTimeTicks": 45 * TICKS_PER_SECOND},
        {"RunTimeTicks": 30 * TICKS_PER_SECOND},
    ]

    assert API(item).get_runtime(additional_parts) == 165.0
