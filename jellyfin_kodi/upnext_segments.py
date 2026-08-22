"""Up Next integration for Jellyfin media segments."""

from __future__ import absolute_import, division, unicode_literals

from urllib.parse import quote

from .helper import event


def build_segment_payload(item, segment_type, start, end):
    """Build a standard Up Next payload for a media segment."""
    item_id = item["Id"]
    current = dict(item.get("CurrentEpisode") or {})
    segment_item = dict(current)
    segment_item.update(
        {
            "episodeid": item_id,
            "title": segment_type,
            "header_text": "Segment ends in",
        }
    )

    return {
        "current_episode": current,
        "next_episode": segment_item,
        "play_url": (
            "plugin://plugin.video.jellyfin/?mode=play&id=%s&timestamp=%s"
            % (quote(str(item_id)), end)
        ),
        "notification_offset": start,
        "segment_end": end,
    }


def broadcast_segment(item, segment_type, start, end):
    """Broadcast a segment using Up Next's normal integration protocol."""
    event(
        "upnext_data",
        build_segment_payload(item, segment_type, start, end),
        hexlify=True,
    )
