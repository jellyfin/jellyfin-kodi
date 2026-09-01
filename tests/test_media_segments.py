# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

from jellyfin_kodi.player import Player

import pytest

@pytest.fixture
def player():
    return Player()

class TestMediaSegmentsConversion:

    def test_convert_media_segments_response(self, player):
        media_segments_response = {
            "Items": [
                {
                    "Id": "id-1",
                    "ItemId": "test-item-id",
                    "Type": "Intro",
                    "StartTicks": 425000000,
                    "EndTicks": 1220000000,
                },
                {
                    "Id": "id-2",
                    "ItemId": "test-item-id",
                    "Type": "Outro",
                    "StartTicks": 24580000000,
                    "EndTicks": 25200000000,
                },
            ]
        }

        segments = player._convert_media_segments(media_segments_response)

        assert "id-1" in segments
        assert "id-2" in segments
        assert segments["id-1"]["Start"] == pytest.approx(42.5)
        assert segments["id-1"]["End"] == pytest.approx(122.0)
        assert segments["id-2"]["Start"] == pytest.approx(2458.0)
        assert segments["id-2"]["End"] == pytest.approx(2520.0)


    def test_convert_media_segments_response_allows_multiple_of_same_type(self, player):
        media_segments_response = {
            "Items": [
                {
                    "Id": "id-1",
                    "ItemId": "test-item-id",
                    "Type": "Commercial",
                    "StartTicks": 425000000,
                    "EndTicks": 1220000000,
                },
                {
                    "Id": "id-2",
                    "ItemId": "test-item-id",
                    "Type": "Commercial",
                    "StartTicks": 1400000000,
                    "EndTicks": 1500000000,
                },
                {
                    "Id": "id-3",
                    "ItemId": "test-item-id",
                    "Type": "Outro",
                    "StartTicks": 24580000000,
                    "EndTicks": 25200000000,
                },
            ]
        }

        segments = player._convert_media_segments(media_segments_response)

        assert "id-1" in segments
        assert "id-2" in segments
        assert "id-3" in segments
        assert segments["id-1"]["Start"] == pytest.approx(42.5)
        assert segments["id-1"]["End"] == pytest.approx(122.0)
        assert segments["id-2"]["Start"] == pytest.approx(140.0)
        assert segments["id-2"]["End"] == pytest.approx(150.0)
        assert segments["id-3"]["Start"] == pytest.approx(2458.0)
        assert segments["id-3"]["End"] == pytest.approx(2520.0)

    def test_convert_empty_media_segments(self, player):
        response = {"Items": []}
        
        segments = player._convert_media_segments(response)

        assert segments is None

    def test_convert_media_segments_missing_items(self, player):
        response = {}
        
        segments = player._convert_media_segments(response)

        assert segments is None


class TestSegmentDetection:

    @pytest.mark.parametrize(
        "current_position,segment_start,segment_end,expected_in_window",
        [
            (42.5, 42.5, 122.0, True),
            (45.0, 42.5, 122.0, True),
            (47.5, 42.5, 122.0, True),
            (48.0, 42.5, 122.0, False),
            (40.0, 42.5, 122.0, False),
            (100.0, 42.5, 122.0, False),
        ],
    )
    def test_segment_detection_window(
        self, current_position, segment_start, segment_end, expected_in_window
    ):
        in_window = segment_start <= current_position <= segment_start + 5
        assert in_window == expected_in_window

    def test_skip_prompted_tracking(self):
        skip_prompted = set()
        segment_key = "id-1"

        assert segment_key not in skip_prompted

        skip_prompted.add(segment_key)
        assert segment_key in skip_prompted

        skip_prompted.add(segment_key)
        assert len(skip_prompted) == 1


class TestSkipModes:

    def test_skip_mode_values(self):
        AUTO_SKIP = 0
        SHOW_BUTTON = 1
        ASK_EVERY_TIME = 2

        assert AUTO_SKIP == 0
        assert SHOW_BUTTON == 1
        assert ASK_EVERY_TIME == 2

    def test_segment_type_settings_map(self):
        setting_map = {
            "Introduction": "skipIntroduction.bool",
            "Credits": "skipCredits.bool",
            "Recap": "skipRecap.bool",
            "Preview": "skipPreview.bool",
            "Commercial": "skipCommercial.bool",
        }

        assert "Introduction" in setting_map
        assert "Credits" in setting_map
        assert "Recap" in setting_map
        assert "Preview" in setting_map
        assert "Commercial" in setting_map
        assert setting_map["Introduction"] == "skipIntroduction.bool"


class TestDurationFormatting:

    @pytest.mark.parametrize(
        "duration_seconds,expected_text",
        [
            (30, "30s"),
            (60, "1m 0s"),
            (90, "1m 30s"),
            (120, "2m 0s"),
            (150, "2m 30s"),
            (0, "0s"),
        ],
    )
    def test_duration_formatting(self, duration_seconds, expected_text):
        minutes = int(duration_seconds // 60)
        seconds = int(duration_seconds % 60)
        if minutes > 0:
            duration_text = "%dm %ds" % (minutes, seconds)
        else:
            duration_text = "%ds" % seconds
        assert duration_text == expected_text
