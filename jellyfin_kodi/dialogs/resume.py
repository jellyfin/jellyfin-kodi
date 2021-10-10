# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from kodi_six import xbmc, xbmcgui

from ..helper import LazyLogger

##################################################################################################

LOG = LazyLogger(__name__)
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
RESUME = 3010
START_BEGINNING = 3011

##################################################################################################


class ResumeDialog(xbmcgui.WindowXMLDialog):

    _resume_point = None
    selected_option = None

    def __init__(self, *args, **kwargs):
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_resume_point(self, time):
        self._resume_point = time

    def is_selected(self):
        return self.selected_option is not None

    def get_selected(self):
        return self.selected_option

    def onInit(self):

        self.getControl(RESUME).setLabel(self._resume_point)
        self.getControl(START_BEGINNING).setLabel(xbmc.getLocalizedString(12021))

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def onClick(self, control_id):

        if control_id == RESUME:
            self.selected_option = 1
            self.close()

        if control_id == START_BEGINNING:
            self.selected_option = 0
            self.close()
