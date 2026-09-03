# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals
from unittest.mock import Mock

import jellyfin_kodi.player as player_module
import pytest


@pytest.fixture
def player():
    return player_module.Player()


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

    def test_segment_skip_can_only_be_prompted_once_for_the_same_segment(
        self, monkeypatch, player
    ):

        player.skip_prompted = set()

        skip_mode = 1
        settings = Mock(return_value=skip_mode)
        monkeypatch.setattr(player_module, "settings", settings)

        item = {"Id": "test-item-id"}

        segments = {
            "aa1": {
                "EpisodeId": "test-item-id",
                "Type": "Commercial",
                "Start": 10,
                "End": 20,
            }
        }

        player.skip_segments["test-item-id"] = segments

        player.check_skip_segments(item, 11)
        player.check_skip_segments(item, 12)

        assert "aa1" in player.skip_prompted
        assert len(player.skip_prompted) == 1

    @pytest.mark.parametrize(
        "current_position,segment_start,segment_end,should_skip",
        [
            (42.5, 42.5, 122.0, True),
            (45.0, 42.5, 122.0, True),
            (122.0, 42.5, 122.0, True),
            (41.0, 42.5, 122.0, False),
            (123.0, 42.5, 122.0, False),
        ],
    )
    def test_segment_detection_window(
        self,
        monkeypatch,
        player,
        current_position,
        segment_start,
        segment_end,
        should_skip,
    ):

        player.skip_prompted = set()

        skip_mode = 1
        settings = Mock(return_value=skip_mode)
        monkeypatch.setattr(player_module, "settings", settings)

        item = {"Id": "test-item-id"}

        segments = {
            "aa1": {
                "EpisodeId": "test-item-id",
                "Type": "Commercial",
                "Start": segment_start,
                "End": segment_end,
            }
        }

        player.skip_segments["test-item-id"] = segments

        player.check_skip_segments(item, current_position)

        if should_skip:
            assert "aa1" in player.skip_prompted
            assert len(player.skip_prompted) == 1
        else:
            assert len(player.skip_prompted) == 0

    @pytest.mark.parametrize(
        "segment_type,should_skip",
        [
            ("Introduction", True),
            ("Credits", True),
            ("Recap", True),
            ("Preview", True),
            ("Commercial", True),
            ("Unknown", False),
        ],
    )
    def test_only_mapped_segments_skipped(
        self, monkeypatch, player, segment_type, should_skip
    ):

        player.skip_prompted = set()

        player.played = {
            "": {"Type": "Episode"}
        }  # "Credits" type falls into next_up() which requires this value to be set (and an empty string is the default stub filename)

        skip_mode = 1
        settings = Mock(return_value=skip_mode)
        monkeypatch.setattr(player_module, "settings", settings)

        item = {"Id": "test-item-id"}

        segments = {
            "aa1": {
                "EpisodeId": "test-item-id",
                "Type": segment_type,
                "Start": 10,
                "End": 20,
            }
        }

        player.skip_segments["test-item-id"] = segments

        player.check_skip_segments(item, 11)

        if should_skip:
            assert "aa1" in player.skip_prompted
            assert len(player.skip_prompted) == 1
        else:
            assert len(player.skip_prompted) == 0
