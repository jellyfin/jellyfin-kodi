# -*- coding: utf-8 -*-
"""Tests for FullSync's already-running collision guard.

A sync collision doesn't require two deliberate user clicks -- it can happen
from a double-press on a laggy remote, a companion app or the HTTP API firing
the same action, or a skin widget auto-refreshing a library node, all while
the user is doing something else (e.g. watching a video). This guard
previously surfaced a blocking "ok" dialog in that case. Because Kodi is
single-window, an unattended modal can also stall the GUI-dependent steps of
the sync that's already running, until someone notices and dismisses it. It
should use a non-blocking notification instead.

This test exercises the real FullSync.__init__, not a hand-copied
reimplementation of the guard -- only jellyfin_kodi.full_sync.dialog is
monkeypatched, since the real one opens an actual Kodi UI dialog.
"""

from unittest.mock import patch

import pytest

from jellyfin_kodi.full_sync import FullSync


@pytest.fixture(autouse=True)
def reset_borg_state():
    """FullSync uses the Borg pattern (shared class-level state across
    instances) -- reset it before and after each test so tests don't leak
    "running" state into each other or into other test modules."""
    FullSync._shared_state.clear()
    yield
    FullSync._shared_state.clear()


def test_no_collision_does_not_show_any_dialog():
    with patch("jellyfin_kodi.full_sync.dialog") as mock_dialog:
        FullSync("jellyfin", "server")
    mock_dialog.assert_not_called()


def test_collision_uses_notification_not_blocking_ok_dialog():
    FullSync.running = True
    try:
        with patch("jellyfin_kodi.full_sync.dialog") as mock_dialog:
            with pytest.raises(Exception, match="Sync is already running"):
                FullSync("jellyfin", "server")

        mock_dialog.assert_called_once()
        dialog_type = mock_dialog.call_args[0][0]
        assert dialog_type == "notification", (
            "Sync-collision guard must use a non-blocking notification, not "
            "an 'ok' dialog -- this can trigger without a deliberate click "
            "(double-press, companion app, widget refresh), and a modal here "
            "can stall the already-running sync's own GUI-dependent steps "
            "since Kodi is single-window."
        )
    finally:
        FullSync._shared_state.clear()
