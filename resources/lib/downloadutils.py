# -*- coding: utf-8 -*-

##################################################################################################

import json
import logging
import requests

import xbmcgui

import clientinfo
import connect.connectionmanager as connectionmanager
from utils import window, settings, language as lang

##################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class DownloadUtils(object):

    # Borg - multiple instances, shared state
    _shared_state = {}

    # Requests session
    session = {}
    session_requests = None
    servers = {} # Multi server setup
    default_timeout = 30


    def __init__(self):

        self.__dict__ = self._shared_state
        self.client_info = clientinfo.ClientInfo()


    def set_session(self, **kwargs):
        # Reserved for userclient only
        info = {}
        for key in kwargs:
            info[key] = kwargs[key]

        self.session.update(info)
        window('emby_server.json', value=self.session)

        log.debug("Set info for server %s: %s", self.session['ServerId'], self.session)

    def add_server(self, server, ssl):
        # Reserved for userclient only
        server_id = server['Id']
        info = {
            'UserId': server['UserId'],
            'Server': connectionmanager.getServerAddress(server, server['LastConnectionMode']),
            'Token': server['AccessToken'],
            'SSL': ssl
        }
        for server_info in self.servers:
            if server_info == server_id:
                server_info.update(info)
                # Set window prop
                self._set_server_properties(server_id, server['Name'], info)
                log.info("updating %s to available servers: %s", server_id, self.servers)
                break
        else:
            self.servers[server_id] = info
            self._set_server_properties(server_id, server['Name'], json.dumps(info))
            log.info("adding %s to available servers: %s", server_id, self.servers)

    def reset_server(self, server_id):
        # Reserved for userclient only
        for server in self.servers:
            if server['ServerId'] == server_id:
                self.servers.pop(server)
                window('emby_server%s.json' % server_id, clear=True)
                window('emby_server%s.name' % server_id, clear=True)
                log.info("removing %s from available servers", server_id)

    @staticmethod
    def _set_server_properties(server_id, name, info):
        window('emby_server%s.json' % server_id, value=info)
        window('emby_server%s.name' % server_id, value=name)

    def post_capabilities(self, device_id):
        # Post settings to session
        url = "{server}/emby/Sessions/Capabilities/Full?format=json"
        data = {

            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (

                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"

                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext"
            )
        }

        self.downloadUrl(url, postBody=data, action_type="POST")
        log.debug("Posted capabilities to %s" % self.session['Server'])

        # Attempt at getting sessionId
        url = "{server}/emby/Sessions?DeviceId=%s&format=json" % device_id
        result = self.downloadUrl(url)
        try:
            session_id = result[0]['Id']

        except (KeyError, TypeError):
            log.error("Failed to retrieve the session id.")

        else:
            log.info("SessionId: %s", session_id)
            window('emby_sessionId', value=session_id)

            # Post any permanent additional users
            additional_users = settings('additionalUsers')
            if additional_users:

                additional_users = additional_users.split(',')
                log.info("List of permanent users added to the session: %s", additional_users)

                # Get the user list from server to get the userId
                url = "{server}/emby/Users?format=json"
                result = self.downloadUrl(url)

                for additional in additional_users:
                    add_user = additional.decode('utf-8').lower()

                    # Compare to server users to list of permanent additional users
                    for user in result:
                        username = user['Name'].lower()

                        if username in add_user:
                            user_id = user['Id']
                            url = ("{server}/emby/Sessions/%s/Users/%s?format=json"
                                   % (session_id, user_id))
                            self.downloadUrl(url, postBody={}, action_type="POST")

    def start_session(self):
        # User is identified from this point
        # Attach authenticated header to the session
        session = requests.Session()
        session.headers = self.get_header()
        session.verify = self.session['SSL']
        # Retry connections to the server
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))
        self.session_requests = session

        log.info("requests session started on: %s", self.session['Server'])

    def stop_session(self):
        try:
            self.session_requests.close()
        except Exception as error:
            log.error(error)
            log.warn("requests session could not be terminated")

    def get_header(self, server_id=None, authenticate=True):

        device_name = self.client_info.get_device_name().encode('utf-8')
        device_id = self.client_info.get_device_id()
        version = self.client_info.get_version()

        if authenticate:

            user = self._get_session_info(server_id)
            user_id = user['UserId']
            token = user['Token']

            auth = (
                'MediaBrowser UserId="%s", Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (user_id, device_name, device_id, version)
            )
            header = {
                'Authorization': auth,
                'X-MediaBrowser-Token': token
            }
        else:
            auth = (
                'MediaBrowser Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (device_name, device_id, version)
            )
            header = {'Authorization': auth}

        header.update({
            'Content-type': 'application/json',
            'Accept-encoding': 'gzip',
            'Accept-Charset': 'UTF-8,*',
        })
        return header

    def downloadUrl(self, url, postBody=None, action_type="GET", parameters=None,
                    authenticate=True, server_id=None):

        log.debug("===== ENTER downloadUrl =====")

        kwargs = {}
        default_link = ""

        try:
            # Ensure server info is loaded
            self._ensure_server(server_id)
            server = self.session if server_id is None else self.servers[server_id]

            if server_id is None and self.session_requests is not None: # Main server
                session = self.session_requests
            else:
                session = requests
                kwargs.update({
                    'verify': server['SSL'],
                    'headers': self.get_header(server_id, authenticate)
                })

            # Replace for the real values
            url = url.replace("{server}", server['Server'])
            url = url.replace("{UserId}", server['UserId'])

            ##### PREPARE REQUEST #####
            kwargs.update({
                'url': url,
                'timeout': self.default_timeout,
                'json': postBody,
                'params': parameters
            })

            ##### THE RESPONSE #####
            log.debug(kwargs)
            response = self._requests(action_type, session, **kwargs)
            #response = requests.get('http://httpbin.org/status/400')

            if response.status_code == 204:
                # No body in the response
                log.debug("====== 204 Success ======")
                # Read response to release connection
                response.content

            elif response.status_code == requests.codes.ok:
                try:
                    # UNICODE - JSON object
                    response = response.json()
                    log.debug("====== 200 Success ======")
                    log.debug("Response: %s", response)
                    return response

                except Exception:
                    if response.headers.get('content-type') != "text/html":
                        log.info("Unable to convert the response for: %s", url)

            else: # Bad status code
                log.error("=== Bad status response: %s ===", response.status_code)
                response.raise_for_status()

        ##### EXCEPTIONS #####

        except requests.exceptions.SSLError as error:
            log.error("invalid SSL certificate for: %s", url)

        except requests.exceptions.ConnectTimeout as error:
            log.error("Server timeout at: %s", url)

        except requests.exceptions.ConnectionError as error:
            # Make the addon aware of status
            if window('emby_online') != "false":
                log.error("Server unreachable at: %s", url)
                window('emby_online', value="false")

        except requests.exceptions.HTTPError as error:

            if response.status_code == 400:
                log.error("Malformed request: %s", error)
                raise Warning('400')

            if response.status_code == 401:
                # Unauthorized
                status = window('emby_serverStatus')

                if 'X-Application-Error-Code' in response.headers:
                    # Emby server errors
                    if response.headers['X-Application-Error-Code'] == "ParentalControl":
                        # Parental control - access restricted
                        if status != "restricted":
                            xbmcgui.Dialog().notification(heading=lang(29999),
                                                          message="Access restricted.",
                                                          icon=xbmcgui.NOTIFICATION_ERROR,
                                                          time=5000)
                        window('emby_serverStatus', value="restricted")
                        raise Warning('restricted')

                    elif (response.headers['X-Application-Error-Code'] ==
                            "UnauthorizedAccessException"):
                        # User tried to do something his emby account doesn't allow
                        pass

                elif status not in ("401", "Auth"):
                    # Tell userclient token has been revoked.
                    window('emby_serverStatus', value="401")
                    log.error("HTTP Error: %s", error)
                    xbmcgui.Dialog().notification(heading="Error connecting",
                                                  message="Unauthorized.",
                                                  icon=xbmcgui.NOTIFICATION_ERROR)
                    raise Warning('401')

        except requests.exceptions.RequestException as error:
            log.error("unknown error connecting to: %s", url)

        return default_link

    def _ensure_server(self, server_id=None):

        if server_id is None and self.session_requests is None:
            if not self.session:
                server = self._get_session_info()
                self.session = server

        elif server_id and server_id not in self.servers:
            if server_id not in self.servers:
                server = self._get_session_info(server_id)
                self.servers[server_id] = server

        return True

    @classmethod
    def _get_session_info(cls, server_id=None):

        info = {
            'UserId': "",
            'Server': "",
            'Token': "",
            'SSL': False
        }

        if server_id is None: # Main server
            server = window('emby_server.json')
        else: # Other connect servers
            server = window('emby_server%s.json' % server_id)

        if server:
            info.update(server)

        return info

    @classmethod
    def _requests(cls, action, session, **kwargs):

        if action == "GET":
            response = session.get(**kwargs)
        elif action == "POST":
            response = session.post(**kwargs)
        elif action == "DELETE":
            response = session.delete(**kwargs)

        return response
