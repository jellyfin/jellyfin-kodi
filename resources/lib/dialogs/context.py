# -*- coding: utf-8 -*-

##################################################################################################

import logging
import os

import xbmcgui
import xbmcaddon

from utils import window

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
LIST = 155
USER_IMAGE = 150

##################################################################################################


class ContextMenu(xbmcgui.WindowXMLDialog):

    _options = []
    selected_option = None


    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_options(self, options=[]):
        self._options = options

    def is_selected(self):
        return True if self.selected_option else False

    def get_selected(self):
        return self.selected_option

    def onInit(self):

        if window('EmbyUserImage'):
            self.getControl(USER_IMAGE).setImage(window('EmbyUserImage'))

        height = 479 + (len(self._options) * 55)
        log.info("options: %s", self._options)
        self.list_ = self.getControl(LIST)

        for option in self._options:
            self.list_.addItem(self._add_listitem(option))

        self.background = self._add_editcontrol(730, height, 30, 450)
        self.setFocus(self.list_)

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):

            if self.getFocusId() == LIST:
                option = self.list_.getSelectedItem()
                self.selected_option = option.getLabel()
                log.info('option selected: %s', self.selected_option)

                self.close()

    def _add_editcontrol(self, x, y, height, width, password=0):

        media = os.path.join(addon.getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlImage(0, 0, 0, 0,
                                       filename=os.path.join(media, "white.png"),
                                       aspectRatio=0,
                                       colorDiffuse="ff111111")
        control.setPosition(x, y)
        control.setHeight(height)
        control.setWidth(width)

        self.addControl(control)
        return control

    @classmethod
    def _add_listitem(cls, label):
        return xbmcgui.ListItem(label)
