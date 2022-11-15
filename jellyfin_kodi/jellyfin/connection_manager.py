# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import socket
from datetime import datetime
from operator import itemgetter
import traceback

import urllib3

from ..helper import LazyLogger

from .credentials import Credentials
from .api import API

#################################################################################################

LOG = LazyLogger(__name__)
CONNECTION_STATE = {
    'Unavailable': 0,
    'ServerSelection': 1,
    'ServerSignIn': 2,
    'SignedIn': 3
}

#################################################################################################


class ConnectionManager(object):

    user = {}
    server_id = None

    def __init__(self, client):

        LOG.debug("ConnectionManager initializing...")

        self.client = client
        self.config = client.config
        self.credentials = Credentials()

        self.API = API(client)

    def revoke_token(self):

        LOG.info("revoking token")

        self['server']['AccessToken'] = None
        self.credentials.set_credentials(self.credentials.get())

        self.config.data['auth.token'] = None

    def get_available_servers(self):

        LOG.info("Begin getAvailableServers")

        # Clone the credentials
        credentials = self.credentials.get()
        found_servers = self.process_found_servers(self._server_discovery())

        if not found_servers and not credentials['Servers']:  # back out right away, no point in continuing
            LOG.info("Found no servers")
            return list()

        servers = list(credentials['Servers'])

        # Merges servers we already knew with newly found ones
        for found_server in found_servers:
            try:
                self.credentials.add_update_server(servers, found_server)
            except KeyError:
                continue

        servers.sort(key=itemgetter('DateLastAccessed'), reverse=True)
        credentials['Servers'] = servers
        self.credentials.set(credentials)

        return servers

    def login(self, server_url, username, password=None):

        if not username:
            raise AttributeError("username cannot be empty")

        if not server_url:
            raise AttributeError("server url cannot be empty")

        data = self.API.login(server_url, username, password)  # returns empty dict on failure

        if not data:
            LOG.info("Failed to login as `"+username+"`")
            return {}

        LOG.info("Successfully logged in as %s" % (username))
        # TODO Change when moving to database storage of server details
        credentials = self.credentials.get()

        self.config.data['auth.user_id'] = data['User']['Id']
        self.config.data['auth.token'] = data['AccessToken']

        for server in credentials['Servers']:
            if server['Id'] == data['ServerId']:
                found_server = server
                break
        else:
            return {}  # No server found

        found_server['DateLastAccessed'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        found_server['UserId'] = data['User']['Id']
        found_server['AccessToken'] = data['AccessToken']

        self.credentials.add_update_server(credentials['Servers'], found_server)

        info = {
            'Id': data['User']['Id'],
            'IsSignedInOffline': True
        }
        self.credentials.add_update_user(server, info)

        self.credentials.set_credentials(credentials)

        return data

    def connect_to_address(self, address, options={}):

        if not address:
            return False

        address = self._normalize_address(address)

        try:
            response_url = self.API.check_redirect(address)
            if address != response_url:
                address = response_url
            LOG.info("connectToAddress %s succeeded", address)
            server = {
                'address': address,
            }
            server = self.connect_to_server(server, options)
            if server is False:
                LOG.error("connectToAddress %s failed", address)
                return {'State': CONNECTION_STATE['Unavailable']}

            return server
        except Exception as error:
            LOG.exception(error)
            LOG.error("connectToAddress %s failed", address)
            return {'State': CONNECTION_STATE['Unavailable']}

    def connect_to_server(self, server, options={}):

        LOG.info("begin connectToServer")

        try:
            result = self.API.get_public_info(server.get('address'))

            if not result:
                LOG.error("Failed to connect to server: %s" % server.get('address'))
                return {'State': CONNECTION_STATE['Unavailable']}

            LOG.info("calling onSuccessfulConnection with server %s", server.get('Name'))

            self._update_server_info(server, result)
            credentials = self.credentials.get()
            return self._after_connect_validated(server, credentials, result, True, options)

        except Exception as e:
            LOG.error(traceback.format_exc())
            LOG.error("Failing server connection. ERROR msg: {}".format(e))
            return {'State': CONNECTION_STATE['Unavailable']}

    def connect(self, options={}):

        LOG.info("Begin connect")

        servers = self.get_available_servers()
        LOG.info("connect has %s servers", len(servers))

        if not (len(servers)):  # No servers provided
            return {
                'State': ['ServerSelection']
            }

        result = self.connect_to_server(servers[0], options)
        LOG.debug("resolving connect with result: %s", result)

        return result

    def jellyfin_token(self):  # Called once monitor.py#163
        return self.get_server_info(self.server_id)['AccessToken']

    def get_server_info(self, server_id):

        if server_id is None:
            LOG.info("server_id is empty")
            return {}

        servers = self.credentials.get()['Servers']

        for server in servers:
            if server['Id'] == server_id:
                return server

    def get_server_address(self, server_id):
        return self.get_server_info(server_id or self.server_id).get('address')

    def get_public_users(self):
        return self.client.jellyfin.get_public_users()

    def _server_discovery(self):
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = b"who is JellyfinServer?"

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0)  # This controls the socket.timeout exception
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        LOG.debug("MultiGroup      : %s", str(MULTI_GROUP))
        LOG.debug("Sending UDP Data: %s", MESSAGE)

        servers = []

        try:
            sock.sendto(MESSAGE, MULTI_GROUP)
        except Exception as error:
            LOG.exception(traceback.format_exc())
            LOG.exception(error)
            return servers

        while True:
            data = None
            addr = None
            try:
                data, addr = sock.recvfrom(1024)  # buffer size
                servers.append(json.loads(data))

            except socket.timeout:
                LOG.info("Found Servers: %s", servers)
                return servers

            except json.JSONDecodeError:
                LOG.warning("Unable to decode %r from %r.", data, addr)

            except Exception as e:
                LOG.error(traceback.format_exc())
                LOG.exception("Error trying to find servers: %s", e)
                return servers

    def process_found_servers(self, found_servers):

        servers = []

        for found_server in found_servers:

            server = self._convert_endpoint_address_to_manual_address(found_server)

            info = {
                'Id': found_server['Id'],
                'address': server or found_server['Address'],
                'Name': found_server['Name']
            }

            servers.append(info)

        return servers

    # TODO: Make IPv6 compatible
    def _convert_endpoint_address_to_manual_address(self, info):

        if info.get('Address') and info.get('EndpointAddress'):
            address = info['EndpointAddress'].split(':')[0]

            # Determine the port, if any
            parts = info['Address'].split(':')
            if len(parts) > 1:
                port_string = parts[len(parts) - 1]

                try:
                    address += ":%s" % int(port_string)
                    return self._normalize_address(address)
                except ValueError:
                    pass

        return None

    def _normalize_address(self, address):
        # TODO: Try HTTPS first, then HTTP if that fails.
        if '://' not in address:
            address = 'http://' + address

        # Attempt to correct bad input
        url = urllib3.util.parse_url(address.strip())

        if url.scheme is None:
            url = url._replace(scheme='http')

        if url.scheme == 'http' and url.port == 80:
            url = url._replace(port=None)

        if url.scheme == 'https' and url.port == 443:
            url = url._replace(port=None)

        return url.url

    def _after_connect_validated(self, server, credentials, system_info, verify_authentication, options):
        if options.get('enableAutoLogin') is False:

            self.config.data['auth.user_id'] = server.pop('UserId', None)
            self.config.data['auth.token'] = server.pop('AccessToken', None)

        elif verify_authentication and server.get('AccessToken'):
            system_info = self.API.validate_authentication_token(server)
            if 'Status_Code' not in system_info:

                self._update_server_info(server, system_info)
                self.config.data['auth.user_id'] = server['UserId']
                self.config.data['auth.token'] = server['AccessToken']
                system_info['Status_Code'] = 200

                return self._after_connect_validated(server, credentials, system_info, False, options)

            server['UserId'] = None
            server['AccessToken'] = None
            system_info['State'] = CONNECTION_STATE['Unavailable']
            return system_info

        self._update_server_info(server, system_info)

        server['DateLastAccessed'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        self.credentials.add_update_server(credentials['Servers'], server)
        self.credentials.set(credentials)
        self.server_id = server['Id']

        # Update configs
        self.config.data['auth.server'] = server['address']
        self.config.data['auth.server-name'] = server['Name']
        self.config.data['auth.server=id'] = server['Id']
        self.config.data['auth.ssl'] = options.get('ssl', self.config.data['auth.ssl'])

        # Connected
        return {
            'Servers': [server],
            'State': CONNECTION_STATE['SignedIn']
            if server.get('AccessToken')
            else CONNECTION_STATE['ServerSignIn'],
        }

    def _update_server_info(self, server, system_info):

        if server is None or system_info is None:
            return

        server['Name'] = system_info['ServerName']
        server['Id'] = system_info['Id']

        if system_info.get('address'):
            server['address'] = system_info['address']
