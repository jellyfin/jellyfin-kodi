# -*- coding: utf-8 -*-

##################################################################################################

import logging
import os

import xbmcgui
import xbmcaddon

import connect.connectionmanager as connectionmanager
from utils import language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)
addon = xbmcaddon.Addon('plugin.video.emby')

CONN_STATE = connectionmanager.ConnectionState
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
CONNECT = 200
CANCEL = 201
ERROR_TOGGLE = 202
ERROR_MSG = 203
ERROR = {
    'Invalid': 1,
    'Empty': 2
}

##################################################################################################


class ServerManual(xbmcgui.WindowXMLDialog):

    _server = None
    error = None


    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_connect_manager(self, connect_manager):
        self.connect_manager = connect_manager

    def is_connected(self):
        return True if self._server else False

    def get_server(self):
        return self._server

    def onInit(self):

        self.connect_button = self.getControl(CONNECT)
        self.cancel_button = self.getControl(CANCEL)
        self.error_toggle = self.getControl(ERROR_TOGGLE)
        self.error_msg = self.getControl(ERROR_MSG)
        self.host_field = self._add_editcontrol(755, 458, 40, 415)
        self.port_field = self._add_editcontrol(755, 558, 40, 415)

        self.port_field.setText('8096')
        self.setFocus(self.host_field)

        self.host_field.controlUp(self.cancel_button)
        self.host_field.controlDown(self.port_field)
        self.port_field.controlUp(self.host_field)
        self.port_field.controlDown(self.connect_button)
        self.connect_button.controlUp(self.port_field)
        self.cancel_button.controlDown(self.host_field)

    def onClick(self, control):

        if control == CONNECT:
            # Sign in to emby connect
            self._disable_error()

            server = self.host_field.getText()
            port = self.port_field.getText()

            if not server:
                # Display error
                self._error(ERROR['Empty'], lang(30617))
                log.error("Server cannot be null")

            elif self._connect_to_server(server, port):
                self.close()

        elif control == CANCEL:
            # Remind me later
            self.close()

    def onAction(self, action):

        if self.error == ERROR['Empty'] and self.host_field.getText() and self.port_field.getText():
            self._disable_error()

        if action in (ACTION_BACK, ACTION_PARENT_DIR, ACTION_PREVIOUS_MENU):
            self.close()

    def _add_editcontrol(self, x, y, height, width):

        media = os.path.join(addon.getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlEdit(0, 0, 0, 0,
                                      label="User",
                                      font="font10",
                                      textColor="FF52b54b",
                                      disabledColor="FF888888",
                                      focusTexture="-",
                                      noFocusTexture="-")
        control.setPosition(x, y)
        control.setHeight(height)
        control.setWidth(width)

        self.addControl(control)
        return control

    def _connect_to_server(self, server, port):

        server_address = "%s:%s" % (server, port) if port else server
        self._message("%s %s..." % (lang(30610), server_address))
        result = self.connect_manager.connectToAddress(server_address)

        if result['State'] == CONN_STATE['Unavailable']:
            self._message(lang(30609))
            return False
        else:
            self._server = result['Servers'][0]
            return True

    def _message(self, message):

        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('True')

    def _error(self, state, message):

        self.error = state
        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('True')

    def _disable_error(self):

        self.error = None
        self.error_toggle.setVisibleCondition('False')
