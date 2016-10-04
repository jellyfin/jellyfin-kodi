# -*- coding: utf-8 -*-

#################################################################################################

import hashlib
import json
import logging
import requests
import socket
import time
from datetime import datetime

import credentials as cred

#################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning, SNIMissingWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)
requests.packages.urllib3.disable_warnings(SNIMissingWarning)

log = logging.getLogger("EMBY."+__name__.split('.')[-1])

#################################################################################################

ConnectionState = {
    'Unavailable': 0,
    'ServerSelection': 1,
    'ServerSignIn': 2,
    'SignedIn': 3,
    'ConnectSignIn': 4,
    'ServerUpdateNeeded': 5
}

ConnectionMode = {
    'Local': 0,
    'Remote': 1,
    'Manual': 2
}

#################################################################################################

def getServerAddress(server, mode):

    modes = {
        ConnectionMode['Local']: server.get('LocalAddress'),
        ConnectionMode['Remote']: server.get('RemoteAddress'),
        ConnectionMode['Manual']: server.get('ManualAddress')
    }
    return (modes.get(mode) or 
            server.get('ManualAddress',server.get('LocalAddress',server.get('RemoteAddress'))))


class ConnectionManager(object):

    default_timeout = 20
    apiClients = []
    minServerVersion = "3.0.5930"
    connectUser = None


    def __init__(self, appName, appVersion, deviceName, deviceId, capabilities=None, devicePixelRatio=None):
        
        log.info("Begin ConnectionManager constructor")

        self.credentialProvider = cred.Credentials()
        self.appName = appName
        self.appVersion = appVersion
        self.deviceName = deviceName
        self.deviceId = deviceId
        self.capabilities = capabilities
        self.devicePixelRatio = devicePixelRatio


    def setFilePath(self, path):
        # Set where to save persistant data
        self.credentialProvider.setPath(path)

    def _getAppVersion(self):
        return self.appVersion

    def _getCapabilities(self):
        return self.capabilities

    def _getDeviceId(self):
        return self.deviceId

    def _connectUserId(self):
        return self.credentialProvider.getCredentials().get('ConnectUserId')

    def _connectToken(self):
        return self.credentialProvider.getCredentials().get('ConnectAccessToken')

    def getServerInfo(self, id_):

        servers = self.credentialProvider.getCredentials()['Servers']
        
        for s in servers:
            if s['Id'] == id_:
                return s

    def _getLastUsedServer(self):

        servers = self.credentialProvider.getCredentials()['Servers']

        if not len(servers):
            return

        try:
            servers.sort(key=lambda x: datetime.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
        except TypeError:
            servers.sort(key=lambda x: datetime(*(time.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ")[0:6])), reverse=True)

        return servers[0]

    def _mergeServers(self, list1, list2):

        for i in range(0, len(list2), 1):
            try:
                self.credentialProvider.addOrUpdateServer(list1, list2[i])
            except KeyError:
                continue

        return list1

    def _connectUser(self):
        
        return self.connectUser

    def _resolveFailure(self):

        return {
            'State': ConnectionState['Unavailable'],
            'ConnectUser': self._connectUser()
        }

    def _getMinServerVersion(self, val=None):

        if val is not None:
            self.minServerVersion = val

        return self.minServerVersion

    def _updateServerInfo(self, server, systemInfo):

        server['Name'] = systemInfo['ServerName']
        server['Id'] = systemInfo['Id']

        if systemInfo.get('LocalAddress'):
            server['LocalAddress'] = systemInfo['LocalAddress']
        if systemInfo.get('WanAddress'):
            server['RemoteAddress'] = systemInfo['WanAddress']
        if systemInfo.get('MacAddress'):
            server['WakeOnLanInfos'] = [{'MacAddress': systemInfo['MacAddress']}]

    def _getHeaders(self, request):
        
        headers = request.setdefault('headers', {})

        if request.get('dataType') == "json":
            headers['Accept'] = "application/json"
            request.pop('dataType')

        headers['X-Application'] = self._addAppInfoToConnectRequest()
        headers['Content-type'] = request.get('contentType',
            'application/x-www-form-urlencoded; charset=UTF-8')

    def requestUrl(self, request):

        if not request:
            raise AttributeError("Request cannot be null")

        self._getHeaders(request)
        request['timeout'] = request.get('timeout') or self.default_timeout
        request['verify'] = False

        action = request['type']
        request.pop('type')

        log.debug("ConnectionManager requesting %s" % request)

        try:
            r = self._requests(action, **request)
            log.info("ConnectionManager response status: %s" % r.status_code)
            r.raise_for_status()
        
        except Exception as e: # Elaborate on exceptions?
            log.error(e)
            raise

        else:
            try:
                return r.json()
            except ValueError:
                r.content # Read response to release connection
                return

    def _requests(self, action, **kwargs):

        if action == "GET":
            r = requests.get(**kwargs)
        elif action == "POST":
            r = requests.post(**kwargs)

        return r

    def getEmbyServerUrl(self, baseUrl, handler):
        return "%s/emby/%s" % (baseUrl, handler)

    def getConnectUrl(self, handler):
        return "https://connect.emby.media/service/%s" % handler

    def _findServers(self, foundServers):

        servers = []

        for foundServer in foundServers:

            server = self._convertEndpointAddressToManualAddress(foundServer)

            info = {
                'Id': foundServer['Id'],
                'LocalAddress': server or foundServer['Address'],
                'Name': foundServer['Name']
            }
            info['LastConnectionMode'] = ConnectionMode['Manual'] if info.get('ManualAddress') else ConnectionMode['Local']
            
            servers.append(info)
        else:
            return servers

    def _convertEndpointAddressToManualAddress(self, info):
        
        if info.get('Address') and info.get('EndpointAddress'):
            address = info['EndpointAddress'].split(':')[0]

            # Determine the port, if any
            parts = info['Address'].split(':')
            if len(parts) > 1:
                portString = parts[len(parts)-1]

                try:
                    address += ":%s" % int(portString)
                    return self._normalizeAddress(address)
                except ValueError:
                    pass

        return None

    def _serverDiscovery(self):
        
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = "who is EmbyServer?"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(1.0) # This controls the socket.timeout exception

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        
        log.debug("MultiGroup      : %s" % str(MULTI_GROUP))
        log.debug("Sending UDP Data: %s" % MESSAGE)
        sock.sendto(MESSAGE, MULTI_GROUP)
        
        servers = []
        while True:
            try:
                data, addr = sock.recvfrom(1024) # buffer size
                servers.append(json.loads(data))
            
            except socket.timeout:
                log.info("Found Servers: %s" % servers)
                return servers
            
            except Exception as e:
                log.error("Error trying to find servers: %s" % e)
                return servers

    def _normalizeAddress(self, address):
        # Attempt to correct bad input
        address = address.strip()
        address = address.lower()

        if 'http' not in address:
            address = "http://%s" % address

        return address

    def connectToAddress(self, address, options={}):

        if not address:
            return False

        address = self._normalizeAddress(address)

        def _onFail():
            log.error("connectToAddress %s failed" % address)
            return self._resolveFailure()

        try:
            publicInfo = self._tryConnect(address)
        except Exception:
            return _onFail()
        else:
            log.info("connectToAddress %s succeeded" % address)
            server = {
                'ManualAddress': address,
                'LastConnectionMode': ConnectionMode['Manual']
            }
            self._updateServerInfo(server, publicInfo)
            server = self.connectToServer(server, options)
            if server is False:
                return _onFail()
            else:
                return server

    def onAuthenticated(self, result, options={}):

        credentials = self.credentialProvider.getCredentials()
        for s in credentials['Servers']:
            if s['Id'] == result['ServerId']:
                server = s
                break
        else: # Server not found?
            return

        if options.get('updateDateLastAccessed') is not False:
            server['DateLastAccessed'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        server['UserId'] = result['User']['Id']
        server['AccessToken'] = result['AccessToken']

        self.credentialProvider.addOrUpdateServer(credentials['Servers'], server)
        self._saveUserInfoIntoCredentials(server, result['User'])
        self.credentialProvider.getCredentials(credentials)

    def _tryConnect(self, url, timeout=None):

        url = self.getEmbyServerUrl(url, "system/info/public")
        log.info("tryConnect url: %s" % url)

        return self.requestUrl({
            
            'type': "GET",
            'url': url,
            'dataType': "json",
            'timeout': timeout
        })

    def _addAppInfoToConnectRequest(self):
        return "%s/%s" % (self.appName, self.appVersion)

    def _getConnectServers(self, credentials):

        log.info("Begin getConnectServers")
        
        servers = []

        if not credentials.get('ConnectAccessToken') or not credentials.get('ConnectUserId'):
            return servers

        url = self.getConnectUrl("servers?userId=%s" % credentials['ConnectUserId'])
        request = {

            'type': "GET",
            'url': url,
            'dataType': "json",
            'headers': {
                'X-Connect-UserToken': credentials['ConnectAccessToken']
            }
        }
        for server in self.requestUrl(request):

            servers.append({

                'ExchangeToken': server['AccessKey'],
                'ConnectServerId': server['Id'],
                'Id': server['SystemId'],
                'Name': server['Name'],
                'RemoteAddress': server['Url'],
                'LocalAddress': server['LocalAddress'],
                'UserLinkType': "Guest" if server['UserType'].lower() == "guest" else "LinkedUser",
            })

        return servers

    def getAvailableServers(self):
        
        log.info("Begin getAvailableServers")

        # Clone the array
        credentials = self.credentialProvider.getCredentials()

        connectServers = self._getConnectServers(credentials)
        foundServers = self._findServers(self._serverDiscovery())

        servers = list(credentials['Servers'])
        self._mergeServers(servers, foundServers)
        self._mergeServers(servers, connectServers)

        servers = self._filterServers(servers, connectServers)

        try:
            servers.sort(key=lambda x: datetime.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ"), reverse=True)
        except TypeError:
            servers.sort(key=lambda x: datetime(*(time.strptime(x['DateLastAccessed'], "%Y-%m-%dT%H:%M:%SZ")[0:6])), reverse=True)

        credentials['Servers'] = servers
        self.credentialProvider.getCredentials(credentials)

        return servers

    def _filterServers(self, servers, connectServers):
        
        filtered = []

        for server in servers:
            # It's not a connect server, so assume it's still valid
            if server.get('ExchangeToken') is None:
                filtered.append(server)
                continue

            for connectServer in connectServers:
                if server['Id'] == connectServer['Id']:
                    filtered.append(server)
                    break
        else:
            return filtered

    def _getConnectPasswordHash(self, password):

        password = self._cleanConnectPassword(password)
        
        return hashlib.md5(password).hexdigest()

    def _saveUserInfoIntoCredentials(self, server, user):

        info = {
            'Id': user['Id'],
            'IsSignedInOffline': True
        }

        self.credentialProvider.addOrUpdateUser(server, info)

    def _compareVersions(self, a, b):
        """
            -1 a is smaller
            1 a is larger
            0 equal
        """
        a = a.split('.')
        b = b.split('.')

        for i in range(0, max(len(a), len(b)), 1):
            try:
                aVal = a[i]
            except IndexError:
                aVal = 0

            try:    
                bVal = b[i]
            except IndexError:
                bVal = 0

            if aVal < bVal:
                return -1

            if aVal > bVal:
                return 1

        return 0

    def connectToServer(self, server, options={}):

        log.info("begin connectToServer")

        tests = []

        if server.get('LastConnectionMode') is not None:
            #tests.append(server['LastConnectionMode'])
            pass
        if ConnectionMode['Manual'] not in tests:
            tests.append(ConnectionMode['Manual'])
        if ConnectionMode['Local'] not in tests:
            tests.append(ConnectionMode['Local'])
        if ConnectionMode['Remote'] not in tests:
            tests.append(ConnectionMode['Remote'])

        # TODO: begin to wake server

        log.info("beginning connection tests")
        return self._testNextConnectionMode(tests, 0, server, options)

    def _stringEqualsIgnoreCase(self, str1, str2):

        return (str1 or "").lower() == (str2 or "").lower()

    def _testNextConnectionMode(self, tests, index, server, options):

        if index >= len(tests):
            log.info("Tested all connection modes. Failing server connection.")
            return self._resolveFailure()

        mode = tests[index]
        address = getServerAddress(server, mode)
        enableRetry = False
        skipTest = False
        timeout = self.default_timeout

        if mode == ConnectionMode['Local']:
            enableRetry = True
            timeout = 8

            if self._stringEqualsIgnoreCase(address, server.get('ManualAddress')):
                log.info("skipping LocalAddress test because it is the same as ManualAddress")
                skipTest = True

        elif mode == ConnectionMode['Manual']:

            if self._stringEqualsIgnoreCase(address, server.get('LocalAddress')):
                enableRetry = True
                timeout = 8

        if skipTest or not address:
            log.info("skipping test at index: %s" % index)
            return self._testNextConnectionMode(tests, index+1, server, options)

        log.info("testing connection mode %s with server %s" % (mode, server['Name']))
        try:
            result = self._tryConnect(address, timeout)
        
        except Exception:
            log.error("test failed for connection mode %s with server %s" % (mode, server['Name']))

            if enableRetry:
                # TODO: wake on lan and retry
                return self._testNextConnectionMode(tests, index+1, server, options)
            else:
                return self._testNextConnectionMode(tests, index+1, server, options)
        else:

            if self._compareVersions(self._getMinServerVersion(), result['Version']) == 1:
                log.warn("minServerVersion requirement not met. Server version: %s" % result['Version'])
                return {
                    'State': ConnectionState['ServerUpdateNeeded'],
                    'Servers': [server]
                }
            else:
                log.info("calling onSuccessfulConnection with connection mode %s with server %s"
                        % (mode, server['Name']))
                return self._onSuccessfulConnection(server, result, mode, options)

    def _onSuccessfulConnection(self, server, systemInfo, connectionMode, options):

        credentials = self.credentialProvider.getCredentials()

        if credentials.get('ConnectAccessToken') and options.get('enableAutoLogin') is not False:
            
            if self._ensureConnectUser(credentials) is not False:

                if server.get('ExchangeToken'):
                    
                    self._addAuthenticationInfoFromConnect(server, connectionMode, credentials)

        return self._afterConnectValidated(server, credentials, systemInfo, connectionMode, True, options)

    def _afterConnectValidated(self, server, credentials, systemInfo, connectionMode, verifyLocalAuthentication, options):

        if options.get('enableAutoLogin') is False:
            server['UserId'] = None
            server['AccessToken'] = None
        
        elif (verifyLocalAuthentication and server.get('AccessToken') and 
            options.get('enableAutoLogin') is not False):

            if self._validateAuthentication(server, connectionMode) is not False:
                return self._afterConnectValidated(server, credentials, systemInfo, connectionMode, False, options)

            return

        self._updateServerInfo(server, systemInfo)
        server['LastConnectionMode'] = connectionMode

        if options.get('updateDateLastAccessed') is not False:
            server['DateLastAccessed'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        self.credentialProvider.addOrUpdateServer(credentials['Servers'], server)
        self.credentialProvider.getCredentials(credentials)

        result = {
            'Servers': [],
            'ConnectUser': self._connectUser()
        }
        result['State'] = ConnectionState['SignedIn'] if (server.get('AccessToken') and options.get('enableAutoLogin') is not False) else ConnectionState['ServerSignIn']
        result['Servers'].append(server)

        # Connected
        return result

    def _validateAuthentication(self, server, connectionMode):

        url = getServerAddress(server, connectionMode)
        request = {

            'type': "GET",
            'url': self.getEmbyServerUrl(url, "System/Info"),
            'dataType': "json",
            'headers': {
                'X-MediaBrowser-Token': server['AccessToken']
            }
        }
        try:
            systemInfo = self.requestUrl(request)
            self._updateServerInfo(server, systemInfo)

            if server.get('UserId'):
                user = self.requestUrl({

                    'type': "GET",
                    'url': self.getEmbyServerUrl(url, "users/%s" % server['UserId']),
                    'dataType': "json",
                    'headers': {
                        'X-MediaBrowser-Token': server['AccessToken']
                    }
                })

        except Exception:
            server['UserId'] = None
            server['AccessToken'] = None
            return False

    def loginToConnect(self, username, password):

        if not username:
            raise AttributeError("username cannot be empty")

        if not password:
            raise AttributeError("password cannot be empty")

        md5 = self._getConnectPasswordHash(password)
        request = {
            'type': "POST",
            'url': self.getConnectUrl("user/authenticate"),
            'data': {
                'nameOrEmail': username,
                'password': md5
            },
            'dataType': "json"
        }
        try:
            result = self.requestUrl(request)
        except Exception as e: # Failed to login
            log.error(e)
            return False
        else:
            credentials = self.credentialProvider.getCredentials()
            credentials['ConnectAccessToken'] = result['AccessToken']
            credentials['ConnectUserId'] = result['User']['Id']
            self.credentialProvider.getCredentials(credentials)
            # Signed in
            self._onConnectUserSignIn(result['User'])
        
        return result

    def _onConnectUserSignIn(self, user):

        self.connectUser = user
        log.info("connectusersignedin %s" % user)

    def _getConnectUser(self, userId, accessToken):

        if not userId:
            raise AttributeError("null userId")

        if not accessToken:
            raise AttributeError("null accessToken")

        url = self.getConnectUrl('user?id=%s' % userId)

        return self.requestUrl({
            
            'type': "GET",
            'url': url,
            'dataType': "json",
            'headers': {
                'X-Connect-UserToken': accessToken
            }
        })

    def _addAuthenticationInfoFromConnect(self, server, connectionMode, credentials):

        if not server.get('ExchangeToken'):
            raise KeyError("server['ExchangeToken'] cannot be null")

        if not credentials.get('ConnectUserId'):
            raise KeyError("credentials['ConnectUserId'] cannot be null")

        url = getServerAddress(server, connectionMode)
        url = self.getEmbyServerUrl(url, "Connect/Exchange?format=json")
        auth = ('MediaBrowser Client="%s", Device="%s", DeviceId="%s", Version="%s"'
                % (self.appName, self.deviceName, self.deviceId, self.appVersion))
        try:
            auth = self.requestUrl({

                'url': url,
                'type': "GET",
                'dataType': "json",
                'params': {
                    'ConnectUserId': credentials['ConnectUserId']
                },
                'headers': {
                    'X-MediaBrowser-Token': server['ExchangeToken'],
                    'X-Emby-Authorization': auth
                }
            })
        except Exception:
            server['UserId'] = None
            server['AccessToken'] = None
            return False
        else:
            server['UserId'] = auth['LocalUserId']
            server['AccessToken'] = auth['AccessToken']
            return auth

    def _ensureConnectUser(self, credentials):

        if self.connectUser and self.connectUser['Id'] == credentials['ConnectUserId']:
            return

        elif credentials.get('ConnectUserId') and credentials.get('ConnectAccessToken'):

            self.connectUser = None

            try:
                result = self._getConnectUser(credentials['ConnectUserId'], credentials['ConnectAccessToken'])
                self._onConnectUserSignIn(result)
            except Exception:
                return False

    def connect(self, options={}):

        log.info("Begin connect")

        servers = self.getAvailableServers()
        return self._connectToServers(servers, options)

    def _connectToServers(self, servers, options):

        log.info("Begin connectToServers, with %s servers" % len(servers))

        if len(servers) == 1:
            result = self.connectToServer(servers[0], options)
            if result.get('State') == ConnectionState['Unavailable']:
                result['State'] = ConnectionState['ConnectSignIn'] if result['ConnectUser'] == None else ConnectionState['ServerSelection']

            log.info("resolving connectToServers with result['State']: %s" % result)
            return result

        firstServer = self._getLastUsedServer()
        # See if we have any saved credentials and can auto sign in
        if firstServer:
            
            result = self.connectToServer(firstServer, options)
            if result and result.get('State') == ConnectionState['SignedIn']:
                return result

        # Return loaded credentials if exists
        credentials = self.credentialProvider.getCredentials()
        self._ensureConnectUser(credentials)

        return {
            'Servers': servers,
            'State': ConnectionState['ConnectSignIn'] if (not len(servers) and not self._connectUser()) else ConnectionState['ServerSelection'],
            'ConnectUser': self._connectUser()
        }

    def _cleanConnectPassword(self, password):

        password = password or ""

        password = password.replace("&", '&amp;')
        password = password.replace("/", '&#092;')
        password = password.replace("!", '&#33;')
        password = password.replace("$", '&#036;')
        password = password.replace("\"", '&quot;')
        password = password.replace("<", '&lt;')
        password = password.replace(">", '&gt;')
        password = password.replace("'", '&#39;')

        return password

    def clearData(self):

        log.info("connection manager clearing data")

        self.connectUser = None
        credentials = self.credentialProvider.getCredentials()
        credentials['ConnectAccessToken'] = None
        credentials['ConnectUserId'] = None
        credentials['Servers'] = []
        self.credentialProvider.getCredentials(credentials)