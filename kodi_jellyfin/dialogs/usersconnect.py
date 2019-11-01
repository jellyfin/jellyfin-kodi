# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc
import xbmcgui

##################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
LIST = 155
MANUAL = 200
CANCEL = 201

##################################################################################################


class UsersConnect(xbmcgui.WindowXMLDialog):

    _user = None
    _manual_login = False

    def __init__(self, *args, **kwargs):

        self.kodi_version = int(xbmc.getInfoLabel('System.BuildVersion')[:2])
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_args(self, **kwargs):
        # connect_manager, user_image, servers
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def is_user_selected(self):
        return True if self._user else False

    def get_user(self):
        return self._user

    def is_manual_login(self):
        return self._manual_login

    def onInit(self):

        self.list_ = self.getControl(LIST)
        for user in self.users:
            user_image = ("items/logindefault.png" if 'PrimaryImageTag' not in user
                          else self._get_user_artwork(user['Id'], 'Primary'))
            self.list_.addItem(self._add_listitem(user['Name'], user['Id'], user_image))

        self.setFocus(self.list_)

    def _add_listitem(self, label, user_id, user_image):

        item = xbmcgui.ListItem(label)
        item.setProperty('id', user_id)
        if self.kodi_version > 15:
            item.setArt({'Icon': user_image})
        else:
            item.setIconImage(user_image)

        return item

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK):

            if self.getFocusId() == LIST:
                user = self.list_.getSelectedItem()
                selected_id = user.getProperty('id')
                LOG.info('User Id selected: %s', selected_id)

                for user in self.users:
                    if user['Id'] == selected_id:
                        self._user = user
                        break

                self.close()

    def onClick(self, control):

        if control == MANUAL:
            self._manual_login = True
            self.close()

        elif control == CANCEL:
            self.close()

    def _get_user_artwork(self, user_id, item_type):
        # Load user information set by UserClient
        return "%s/emby/Users/%s/Images/%s?Format=original" % (self.server, user_id, item_type)
