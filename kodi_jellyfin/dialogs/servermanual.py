# -*- coding: utf-8 -*-

##################################################################################################

import logging
import os
import re

import xbmcgui
import xbmcaddon

from helper import _, addon_id
from jellyfin.core.connection_manager import CONNECTION_STATE

##################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)
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

# https://stackoverflow.com/a/17871737/1035647
_IPV6_PATTERN = "^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$"
_IPV6_RE = re.compile(_IPV6_PATTERN)
##################################################################################################


class ServerManual(xbmcgui.WindowXMLDialog):

    _server = None
    error = None

    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_args(self, **kwargs):
        # connect_manager, user_image, servers, jellyfin_connect
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def is_connected(self):
        return True if self._server else False

    def get_server(self):
        return self._server

    def onInit(self):

        self.connect_button = self.getControl(CONNECT)
        self.cancel_button = self.getControl(CANCEL)
        self.error_toggle = self.getControl(ERROR_TOGGLE)
        self.error_msg = self.getControl(ERROR_MSG)
        self.host_field = self._add_editcontrol(755, 433, 40, 415)
        self.port_field = self._add_editcontrol(755, 543, 40, 415)

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
            self._disable_error()

            server = self.host_field.getText()
            port = self.port_field.getText()

            if not server:
                # Display error
                self._error(ERROR['Empty'], _('empty_server'))
                LOG.error("Server cannot be null")

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

        media = os.path.join(xbmcaddon.Addon(addon_id()).getAddonInfo('path'), 'resources', 'skins', 'default', 'media')
        control = xbmcgui.ControlEdit(0, 0, 0, 0,
                                      label="User",
                                      font="font13",
                                      textColor="FF00A4DC",
                                      disabledColor="FF888888",
                                      focusTexture="-",
                                      noFocusTexture="-")
        control.setPosition(x, y)
        control.setHeight(height)
        control.setWidth(width)

        self.addControl(control)
        return control

    def _connect_to_server(self, server, port):
        if _IPV6_RE.match(server):
            server = "[%s]" % (server)

        server_address = "%s:%s" % (server, port) if port else server
        self._message("%s %s..." % (_(30610), server_address))
        result = self.connect_manager.connect_to_address(server_address)

        if result['State'] == CONNECTION_STATE['Unavailable']:
            self._message(_(30609))
            return False
        else:
            self._server = result['Servers'][0]
            return True

    def _message(self, message):

        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('true')

    def _error(self, state, message):

        self.error = state
        self.error_msg.setLabel(message)
        self.error_toggle.setVisibleCondition('true')

    def _disable_error(self):

        self.error = None
        self.error_toggle.setVisibleCondition('false')
