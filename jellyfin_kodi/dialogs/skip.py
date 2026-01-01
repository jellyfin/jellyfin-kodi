# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

import xbmc
import xbmcgui

from ..helper import LazyLogger
from ..helper.translate import translate

##################################################################################################

LOG = LazyLogger(__name__)

# Action IDs
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT = 7

# Control IDs
SKIP_BUTTON = 3020
COUNTDOWN_LABEL = 3021

# String IDs for segment types
SEGMENT_STRING_IDS = {
    "Introduction": 33252,
    "Credits": 33253,
    "Recap": 33254,
    "Preview": 33255,
    "Commercial": 33259,
}

##################################################################################################


class SkipDialog(xbmcgui.WindowXMLDialog):
    """
    OSD overlay dialog for skipping intro/outro segments.
    
    Displays a "Skip" button in the bottom-right corner during playback
    when a skippable segment is detected.
    """

    _segment_type = None
    _duration = 0
    _timeout = 5  # seconds before auto-dismiss
    skip_requested = False

    def __init__(self, *args, **kwargs):
        self._segment_type = kwargs.pop("segment_type", None)
        self._duration = kwargs.pop("duration", 0)
        self._timeout = kwargs.pop("timeout", 5)
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_skip_info(self, segment_type, duration, timeout=5):
        """
        Set the skip segment information.
        
        Args:
            segment_type: Type of segment (Introduction, Credits, Recap, Preview, Commercial)
            duration: Duration of the segment in seconds
            timeout: Seconds before dialog auto-dismisses (default 5)
        """
        self._segment_type = segment_type
        self._duration = duration
        self._timeout = timeout

    def onInit(self):
        """Initialize the dialog controls."""
        # Format duration text
        minutes = int(self._duration // 60)
        seconds = int(self._duration % 60)
        if minutes > 0:
            duration_text = f"{minutes}m {seconds}s"
        else:
            duration_text = f"{seconds}s"
        
        # Get translated segment type label
        string_id = SEGMENT_STRING_IDS.get(self._segment_type)
        if string_id:
            segment_label = translate(string_id)
        else:
            segment_label = self._segment_type or "Segment"
        
        # Set button label: "Skip Introduction (1m 30s)"
        skip_text = translate(33256)  # "Skip"
        button_label = f"{skip_text} {segment_label} ({duration_text})"
        
        try:
            self.getControl(SKIP_BUTTON).setLabel(button_label)
        except Exception as e:
            LOG.warning(f"Could not set skip button label: {e}")
        
        # Start auto-dismiss countdown
        self._start_countdown()

    def _start_countdown(self):
        """Start the auto-dismiss countdown timer."""
        monitor = xbmc.Monitor()
        remaining = self._timeout
        
        while remaining > 0 and not monitor.abortRequested():
            try:
                countdown_label = self.getControl(COUNTDOWN_LABEL)
                countdown_label.setLabel(f"{remaining}s")
            except Exception:
                pass
            
            if monitor.waitForAbort(1):
                break
            remaining -= 1
            
            # Check if dialog was closed by user
            if not self.isActive():
                return
        
        # Auto-dismiss if not interacted with
        if self.isActive() and not self.skip_requested:
            self.close()

    def isActive(self):
        """Check if the dialog is still visible."""
        try:
            return xbmcgui.getCurrentWindowDialogId() == 3302
        except Exception:
            return False

    def onAction(self, action):
        """Handle user actions."""
        action_id = action.getId()
        
        if action_id in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.skip_requested = False
            self.close()
        elif action_id == ACTION_SELECT:
            # SELECT on the button triggers skip
            self.skip_requested = True
            self.close()

    def onClick(self, control_id):
        """Handle control clicks."""
        if control_id == SKIP_BUTTON:
            LOG.info(f"Skip button clicked for {self._segment_type}")
            self.skip_requested = True
            self.close()

    def was_skipped(self):
        """Return whether the user requested to skip."""
        return self.skip_requested


def show_skip_dialog(segment_type, duration, timeout=5):
    """
    Convenience function to show the skip dialog.
    
    Args:
        segment_type: Type of segment (Introduction, Credits, etc.)
        duration: Duration of the segment in seconds
        timeout: Auto-dismiss timeout in seconds
        
    Returns:
        True if user clicked skip, False otherwise
    """
    from ..helper.utils import translate_path
    
    addon_path = translate_path("special://home/addons/plugin.video.jellyfin/resources/skins/")
    
    dialog = SkipDialog(
        "script-jellyfin-skip.xml",
        addon_path,
        "default",
        "1080i",
        segment_type=segment_type,
        duration=duration,
        timeout=timeout
    )
    dialog.doModal()
    
    return dialog.was_skipped()
