# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals
import xbmcgui
from ..helper import LazyLogger

LOG = LazyLogger(__name__)

# Action IDs
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_NAV_BACK = 92

# Control IDs
SKIP_BUTTON = 3012
CLOSE_BUTTON = 3013

# String IDs for segment types - using shorter labels
SEGMENT_LABELS = {
    "Introduction": "Intro",
    "Credits": "Outro",
    "Recap": "Recap",
    "Preview": "Preview",
    "Commercial": "Ad",
}


class SkipDialog(xbmcgui.WindowXMLDialog):
    """
    OSD overlay dialog for skipping intro/outro segments.

    Based on service.upnext popup pattern for reliable non-modal display.
    """

    def __init__(self, *args, **kwargs):
        self._segment_type = kwargs.pop("segment_type", None)
        self._duration = kwargs.pop("duration", 0)

        # State flags
        self.skip_requested = False
        self.cancel_requested = False

        # Set properties before super().__init__ to avoid flicker
        # (like service.upnext does in set_info)

        xbmcgui.WindowXMLDialog.__init__(self, *args)

    def set_skip_info(self, segment_type, duration):
        """Set the skip segment information."""
        self._segment_type = segment_type
        self._duration = duration

        # Format duration text
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        if minutes > 0:
            duration_text = "{0}m {1}s".format(minutes, seconds)
        else:
            duration_text = "{0}s".format(seconds)

        # Get short segment type label
        segment_label = SEGMENT_LABELS.get(segment_type, segment_type or "Segment")

        # Set button label: "Skip Intro (1m 40s)"
        button_label = "Skip {0} ({1})".format(segment_label, duration_text)

        # Use setProperty so it's available to the skin
        self.setProperty('skip_label', button_label)
        self.setProperty('segment_type', segment_type or '')
        self.setProperty('duration', duration_text)

        LOG.debug("SkipDialog: set_skip_info segment=%s, label=%s", segment_type, button_label)

    def onInit(self):
        """Initialize the dialog controls."""
        LOG.debug("SkipDialog.onInit called")

        # Try to set button label directly as well
        try:
            button = self.getControl(SKIP_BUTTON)
            label = self.getProperty('skip_label')
            if label:
                button.setLabel(label)
                LOG.debug("SkipDialog.onInit: set button label to '%s'", label)
        except Exception as e:
            LOG.debug("Could not set skip button label: %s", e)

    def onAction(self, action):
        """Handle user actions."""
        action_id = action.getId()
        LOG.debug("SkipDialog.onAction: action_id=%s", action_id)

        if action_id in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU, ACTION_NAV_BACK):
            self.cancel_requested = True
            self.close()

    def onClick(self, control_id):
        """Handle control clicks."""
        LOG.debug("SkipDialog.onClick: control_id=%s", control_id)

        if control_id == SKIP_BUTTON:
            LOG.debug("Skip button clicked for %s", self._segment_type)
            self.skip_requested = True
            self.close()
        elif control_id == CLOSE_BUTTON:
            LOG.debug("Close button clicked")
            self.cancel_requested = True
            self.close()

    def is_skip(self):
        """Return whether the user requested to skip."""
        return self.skip_requested

    def is_cancel(self):
        """Return whether the user cancelled."""
        return self.cancel_requested
