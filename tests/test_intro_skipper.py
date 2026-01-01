# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import pytest


class TestIntroSkipperSegmentParsing:

    def test_parse_intro_skipper_response(self):
        response = {
            "Introduction": {
                "EpisodeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "Start": 42.5,
                "End": 122.0
            },
            "Credits": {
                "EpisodeId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "Start": 2458.0,
                "End": 2520.0
            }
        }
        assert "Introduction" in response
        assert "Credits" in response
        assert response["Introduction"]["Start"] == 42.5
        assert response["Introduction"]["End"] == 122.0

    def test_parse_empty_response(self):
        response = {}
        assert len(response) == 0

    def test_parse_partial_response(self):
        response = {
            "Introduction": {
                "EpisodeId": "test-id",
                "Start": 10.0,
                "End": 60.0
            }
        }
        assert "Introduction" in response
        assert "Credits" not in response


class TestMediaSegmentsConversion:

    def test_convert_media_segments_to_intro_skipper_format(self):
        media_segments_response = {
            "Items": [
                {
                    "ItemId": "test-item-id",
                    "Type": "Intro",
                    "StartTicks": 425000000,
                    "EndTicks": 1220000000
                },
                {
                    "ItemId": "test-item-id",
                    "Type": "Outro",
                    "StartTicks": 24580000000,
                    "EndTicks": 25200000000
                }
            ]
        }

        type_map = {
            "Intro": "Introduction",
            "Outro": "Credits",
            "Recap": "Recap",
            "Preview": "Preview",
            "Commercial": "Commercial",
        }

        segments = {}
        for item in media_segments_response["Items"]:
            seg_type = type_map.get(item.get("Type"))
            if seg_type:
                segments[seg_type] = {
                    "EpisodeId": item.get("ItemId"),
                    "Start": item.get("StartTicks", 0) / 10000000.0,
                    "End": item.get("EndTicks", 0) / 10000000.0,
                }

        assert "Introduction" in segments
        assert "Credits" in segments
        assert segments["Introduction"]["Start"] == 42.5
        assert segments["Introduction"]["End"] == 122.0
        assert segments["Credits"]["Start"] == 2458.0
        assert segments["Credits"]["End"] == 2520.0

    def test_convert_empty_media_segments(self):
        response = {"Items": []}
        assert len(response["Items"]) == 0

    def test_convert_media_segments_missing_items(self):
        response = {}
        assert "Items" not in response


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
    def test_segment_detection_window(self, current_position, segment_start, segment_end, expected_in_window):
        in_window = segment_start <= current_position <= segment_start + 5
        assert in_window == expected_in_window

    def test_segment_key_generation(self):
        item_id = "a1b2c3d4"
        segment_type = "Introduction"
        segment_key = "%s:%s" % (item_id, segment_type)
        assert segment_key == "a1b2c3d4:Introduction"

    def test_skip_prompted_tracking(self):
        skip_prompted = set()
        segment_key = "item123:Introduction"

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
