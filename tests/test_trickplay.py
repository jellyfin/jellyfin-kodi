from jellyfin_kodi.trickplay import (
    next_thumbnail_index,
    select_profile,
    thumbnail_location,
)


def test_select_profile_prefers_smallest_profile_at_or_above_target():
    item = {"Trickplay": [{"Width": 160}, {"Width": 640}, {"Width": 320}]}
    assert select_profile(item)["Width"] == 320


def test_select_profile_uses_largest_available_when_all_profiles_are_smaller():
    item = {"Trickplay": [{"Width": 160}, {"Width": 240}]}
    assert select_profile(item)["Width"] == 240


def test_select_profile_accepts_width_keyed_response():
    item = {"Trickplay": {"320": [{"Width": 320, "Interval": 10000}]}}
    assert select_profile(item)["Width"] == 320


def test_select_profile_accepts_item_id_and_width_keyed_response():
    item = {
        "Trickplay": {
            "episode-id": {
                "320": {
                    "Width": 320,
                    "Height": 180,
                    "TileWidth": 10,
                    "TileHeight": 10,
                    "ThumbnailCount": 197,
                    "Interval": 10000,
                }
            }
        }
    }
    profile = select_profile(item)
    assert profile["Width"] == 320
    assert profile["ThumbnailCount"] == 197


def test_next_thumbnail_uses_the_first_frame_after_the_segment():
    assert next_thumbnail_index(122.0, 10000, 1000) == 13


def test_next_thumbnail_returns_none_when_no_following_frame_exists():
    assert next_thumbnail_index(990.0, 10000, 100) is None


def test_next_thumbnail_rejects_invalid_interval():
    assert next_thumbnail_index(122.0, 0, 1000) is None


def test_thumbnail_location_uses_sheet_and_tile_coordinates():
    profile = {
        "Width": 320,
        "Height": 180,
        "TileWidth": 10,
        "TileHeight": 10,
        "ThumbnailCount": 197,
        "Interval": 10000,
    }
    location = thumbnail_location(profile, 300.0)
    assert location == {
        "index": 31,
        "sheet": 0,
        "tile": 31,
        "row": 3,
        "column": 1,
    }


def test_thumbnail_location_crosses_sheet_boundary():
    profile = {
        "Width": 320,
        "Height": 180,
        "TileWidth": 10,
        "TileHeight": 10,
        "ThumbnailCount": 197,
        "Interval": 10000,
    }
    location = thumbnail_location(profile, 990.0)
    assert location["sheet"] == 1
    assert location["tile"] == 0
    assert location["row"] == 0
    assert location["column"] == 0
