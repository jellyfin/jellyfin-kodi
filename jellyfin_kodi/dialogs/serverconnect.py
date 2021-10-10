# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from six import iteritems
from kodi_six import xbmc, xbmcgui

from ..helper import translate
from ..jellyfin.connection_manager import CONNECTION_STATE
from ..helper import LazyLogger

##################################################################################################

LOG = LazyLogger(__name__)
ACTION_PARENT_DIR = 9
ACTION_PREVIOUS_MENU = 10
ACTION_BACK = 92
ACTION_SELECT_ITEM = 7
ACTION_MOUSE_LEFT_CLICK = 100
USER_IMAGE = 150
LIST = 155
CANCEL = 201
MESSAGE_BOX = 202
MESSAGE = 203
BUSY = 204
MANUAL_SERVER = 206

##################################################################################################


class ServerConnect(xbmcgui.WindowXMLDialog):

    user_image = None
    servers = []

    _selected_server = None
    _connect_login = False
    _manual_server = False

    def __init__(self, *args, **kwargs):

        xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def set_args(self, **kwargs):
        # connect_manager, user_image, servers
        for key, value in iteritems(kwargs):
            setattr(self, key, value)

    def is_server_selected(self):
        return bool(self._selected_server)

    def get_server(self):
        return self._selected_server

    def is_manual_server(self):
        return self._manual_server

    def onInit(self):

        self.message = self.getControl(MESSAGE)
        self.message_box = self.getControl(MESSAGE_BOX)
        self.busy = self.getControl(BUSY)
        self.list_ = self.getControl(LIST)

        for server in self.servers:
            server_type = "wifi" if server.get('ExchangeToken') else "network"
            self.list_.addItem(self._add_listitem(server['Name'], server['Id'], server_type))

        if self.user_image is not None:
            self.getControl(USER_IMAGE).setImage(self.user_image)

        if self.servers:
            self.setFocus(self.list_)

    @classmethod
    def _add_listitem(cls, label, server_id, server_type):

        item = xbmcgui.ListItem(label)
        item.setProperty('id', server_id)
        item.setProperty('server_type', server_type)

        return item

    def onAction(self, action):

        if action in (ACTION_BACK, ACTION_PREVIOUS_MENU, ACTION_PARENT_DIR):
            self.close()

        if action in (ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK) and self.getFocusId() == LIST:

            server = self.list_.getSelectedItem()
            selected_id = server.getProperty('id')
            LOG.info('Server Id selected: %s', selected_id)

            if self._connect_server(selected_id):
                self.message_box.setVisibleCondition('false')
                self.close()

    def onClick(self, control):

        if control == MANUAL_SERVER:
            self._manual_server = True
            self.close()

        elif control == CANCEL:
            self.close()

    def _connect_server(self, server_id):

        server = self.connect_manager.get_server_info(server_id)
        self.message.setLabel("%s %s..." % (translate(30610), server['Name']))

        self.message_box.setVisibleCondition('true')
        self.busy.setVisibleCondition('true')

        result = self.connect_manager.connect_to_server(server)

        if result['State'] == CONNECTION_STATE['Unavailable']:
            self.busy.setVisibleCondition('false')

            self.message.setLabel(translate(30609))
            return False
        else:
            xbmc.sleep(1000)
            self._selected_server = result['Servers'][0]
            return True
