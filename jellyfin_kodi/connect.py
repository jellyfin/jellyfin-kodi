# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from kodi_six import xbmc, xbmcaddon

from . import client
from .database import get_credentials, save_credentials
from .dialogs import ServerConnect, UsersConnect, LoginManual, ServerManual
from .helper import settings, addon_id, event, api, window, LazyLogger
from .jellyfin import Jellyfin
from .jellyfin.connection_manager import CONNECTION_STATE
from .helper.exceptions import HTTPException

##################################################################################################

LOG = LazyLogger(__name__)
XML_PATH = (xbmcaddon.Addon(addon_id()).getAddonInfo('path'), "default", "1080i")

##################################################################################################


class Connect(object):

    def __init__(self):
        self.info = client.get_info()

    def register(self, server_id=None, options={}):

        ''' Login into server. If server is None, then it will show the proper prompts to login, etc.
            If a server id is specified then only a login dialog will be shown for that server.
        '''
        LOG.info("--[ server/%s ]", server_id or 'default')
        credentials = dict(get_credentials())
        servers = credentials['Servers']

        if server_id is None and credentials['Servers']:
            credentials['Servers'] = [credentials['Servers'][0]]

        elif credentials['Servers']:

            for server in credentials['Servers']:

                if server['Id'] == server_id:
                    credentials['Servers'] = [server]

        server_select = server_id is None and not settings('SyncInstallRunDone.bool')
        new_credentials = self.register_client(credentials, options, server_id, server_select)

        for server in servers:
            if server['Id'] == new_credentials['Servers'][0]['Id']:
                server = new_credentials['Servers'][0]

                break
        else:
            servers = new_credentials['Servers']

        credentials['Servers'] = servers
        save_credentials(credentials)

        try:
            Jellyfin(server_id).start(True)
        except ValueError as error:
            LOG.error(error)

    def get_ssl(self):

        ''' Returns boolean value.
            True: verify connection.
        '''
        return settings('sslverify.bool')

    def get_client(self, server_id=None):

        ''' Get Jellyfin client.
        '''
        client = Jellyfin(server_id)
        client.config.app("Kodi", self.info['Version'], self.info['DeviceName'], self.info['DeviceId'])
        client.config.data['http.user_agent'] = "Jellyfin-Kodi/%s" % self.info['Version']
        client.config.data['auth.ssl'] = self.get_ssl()

        return client

    def register_client(self, credentials=None, options=None, server_id=None, server_selection=False):

        client = self.get_client(server_id)
        self.client = client
        self.connect_manager = client.auth

        if server_id is None:
            client.config.data['app.default'] = True

        try:
            state = client.authenticate(credentials or {}, options or {})

            if state['State'] == CONNECTION_STATE['SignedIn']:
                client.callback_ws = event

                if server_id is None:  # Only assign for default server

                    client.callback = event
                    self.get_user(client)

                    settings('serverName', client.config.data['auth.server-name'])
                    settings('server', client.config.data['auth.server'])

                event('ServerOnline', {'ServerId': server_id})
                event('LoadServer', {'ServerId': server_id})

                return state['Credentials']

            elif (server_selection or state['State'] == CONNECTION_STATE['ServerSelection'] or state['State'] == CONNECTION_STATE['Unavailable'] and not settings('SyncInstallRunDone.bool')):
                state['Credentials']['Servers'] = [self.select_servers(state)]

            elif state['State'] == CONNECTION_STATE['ServerSignIn']:
                if 'ExchangeToken' not in state['Servers'][0]:
                    self.login()

            elif state['State'] == CONNECTION_STATE['Unavailable'] and state.get('Status_Code', 0) == 401:
                # If the saved credentials don't work, restart the addon to force the password dialog to open
                window('jellyfin.restart', clear=True)

            elif state['State'] == CONNECTION_STATE['Unavailable']:
                raise HTTPException('ServerUnreachable', {})

            return self.register_client(state['Credentials'], options, server_id, False)

        except RuntimeError as error:

            LOG.exception(error)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addon_id())

            raise Exception('User sign in interrupted')

        except HTTPException as error:

            if error.status == 'ServerUnreachable':
                event('ServerUnreachable', {'ServerId': server_id})

            return client.get_credentials()

    def get_user(self, client):

        ''' Save user info.
        '''
        self.user = client.jellyfin.get_user()
        settings('username', self.user['Name'])

        if 'PrimaryImageTag' in self.user:
            server_address = client.auth.get_server_info(client.auth.server_id)['address']
            window('JellyfinUserImage', api.API(self.user, server_address).get_user_artwork(self.user['Id']))

    def select_servers(self, state=None):

        state = state or self.connect_manager.connect({'enableAutoLogin': False})
        user = {}

        dialog = ServerConnect("script-jellyfin-connect-server.xml", *XML_PATH)
        dialog.set_args(
            connect_manager=self.connect_manager,
            username=user.get('DisplayName', ""),
            user_image=user.get('ImageUrl'),
            servers=self.connect_manager.get_available_servers()
        )

        dialog.doModal()

        if dialog.is_server_selected():
            LOG.debug("Server selected: %s", dialog.get_server())
            return dialog.get_server()

        elif dialog.is_manual_server():
            LOG.debug("Adding manual server")
            try:
                return self.manual_server()
            except RuntimeError:
                pass
        else:
            raise RuntimeError("No server selected")

        return self.select_servers()

    def setup_manual_server(self):

        ''' Setup manual servers
        '''
        client = self.get_client()
        client.set_credentials(get_credentials())
        manager = client.auth

        try:
            self.manual_server(manager)
        except RuntimeError:
            return

        credentials = client.get_credentials()
        save_credentials(credentials)

    def manual_server(self, manager=None):

        ''' Return server or raise error.
        '''
        dialog = ServerManual("script-jellyfin-connect-server-manual.xml", *XML_PATH)
        dialog.set_args(**{'connect_manager': manager or self.connect_manager})
        dialog.doModal()

        if dialog.is_connected():
            return dialog.get_server()
        else:
            raise RuntimeError("Server is not connected")

    def login(self):

        users = self.connect_manager.get_public_users()
        server = self.connect_manager.get_server_info(self.connect_manager.server_id)['address']

        if not users:
            try:
                return self.login_manual()
            except RuntimeError:
                raise RuntimeError("No user selected")

        dialog = UsersConnect("script-jellyfin-connect-users.xml", *XML_PATH)
        dialog.set_args(**{'server': server, 'users': users})
        dialog.doModal()

        if dialog.is_user_selected():
            user = dialog.get_user()
            username = user['Name']

            if user['HasPassword']:
                LOG.debug("User has password, present manual login")
                try:
                    return self.login_manual(username)
                except RuntimeError:
                    pass
            else:
                return self.connect_manager.login(server, username)

        elif dialog.is_manual_login():
            try:
                return self.login_manual()
            except RuntimeError:
                pass
        else:
            raise RuntimeError("No user selected")

        return self.login()

    def setup_login_manual(self):

        ''' Setup manual login by itself for default server.
        '''
        client = self.get_client()
        client.set_credentials(get_credentials())
        manager = client.auth

        username = settings('username')
        try:
            self.login_manual(user=username, manager=manager)
        except RuntimeError:
            return

        credentials = client.get_credentials()
        save_credentials(credentials)

    def login_manual(self, user=None, manager=None):

        ''' Return manual login user authenticated or raise error.
        '''
        dialog = LoginManual("script-jellyfin-connect-login-manual.xml", *XML_PATH)
        dialog.set_args(**{'connect_manager': manager or self.connect_manager, 'username': user or {}})
        dialog.doModal()

        if dialog.is_logged_in():
            return dialog.get_user()
        else:
            raise RuntimeError("User is not authenticated")

    def remove_server(self, server_id):

        ''' Stop client and remove server.
        '''
        Jellyfin(server_id).close()
        credentials = get_credentials()

        for server in credentials['Servers']:
            if server['Id'] == server_id:
                credentials['Servers'].remove(server)

                break

        save_credentials(credentials)
        LOG.info("[ remove server ] %s", server_id)
