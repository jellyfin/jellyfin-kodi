# -*- coding: utf-8 -*-

##################################################################################################

import logging
import os

import xbmcgui
import xbmcaddon

import read_embyserver as embyserver
from utils import language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
SIGN_IN = 200
CANCEL = 201
ERROR_TOGGLE = 202
ERROR_MSG = 203
USER = 204
PASSWORD = 205
ERROR = {
    'Invalid': 1,
    'Empty': 2
}

##################################################################################################


class LoginManual(xbmcgui.WindowXMLDialog):

    _user = None
    error = None
    username = None


    def __init__(self, *args, **kwargs):

        self.emby = embyserver.Read_EmbyServer()
        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def is_logged_in(self):
        return True if self._user else False

    def set_server(self, server):
        self.server = server

    def set_user(self, user):
        self.username = user or None

    def get_user(self):
        return self._user

    def onInit(self):

        self.signin_button = self.getControl(SIGN_IN)
        self.cancel_button = self.getControl(CANCEL)
        self.error_toggle = self.getControl(ERROR_TOGGLE)
        self.error_msg = self.getControl(ERROR_MSG)
        self.user_field = self.getControl(USER)
        self.password_field = self.getControl(PASSWORD)

        if self.username:
            self.user_field.setText(self.username)
            self.setFocus(self.password_field)
        else:
            self.setFocus(self.user_field)

    def onClick(self, control):

        if control == SIGN_IN:
            # Sign in to emby connect
            self._disable_error()

            user = self.user_field.getText()
            password = self.password_field.getText()

            if not user:
                # Display error
                self._error(ERROR['Empty'], lang(30613))
                log.error("Username cannot be null")

            elif self._login(user, password):
                self.close()

        elif control == CANCEL:
            # Remind me later
            self.close()

    def onAction(self, action):

        if self.error == ERROR['Empty'] and self.user_field.getText():
            self._disable_error()

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def _login(self, username, password):

        try:
            result = self.emby.loginUser(self.server, username, password)
        except Exception as error:
            log.info("Error doing login: " + str(error))
            result = None

        if result is None:
            self._error(ERROR['Invalid'], lang(33009))
            return False
        else:
            self._user = result
            return True

    def _error(self, state, message):

        self.error = state
        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('True')

    def _disable_error(self):

        self.error = None
        self.error_toggle.setVisibleCondition('False')
