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

class HTTPException(Exception):
    # Emby HTTP exception
    def __init__(self, status):
        self.status = status


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

    def get_token(self):
        return self._get_session_info()['Token']

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

    def post_capabilities(self, device_id=clientinfo.ClientInfo.get_device_id()):
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
                "SetRepeatMode,"
                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
            'IconUrl': "https://raw.githubusercontent.com/MediaBrowser/Emby.Resources/master/images/devices/kodi.png",
        }

        try:
            self.downloadUrl(url, postBody=data, action_type="POST")
            log.debug("Posted capabilities to %s", self.session['Server'])

            # Attempt at getting sessionId
            url = "{server}/emby/Sessions?DeviceId=%s&format=json" % device_id
            result = self.downloadUrl(url)
            session_id = result[0]['Id']

        except Exception as error:
            log.error("Failed to retrieve the session id: " + str(error))
            return False

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

        return True

    def start_session(self):
        # User is identified from this point
        # Attach authenticated header to the session
        session = requests.Session()
        session.headers = self.get_header()
        session.verify = self.session['SSL']
        # Retry connections to the server
        session.mount("http://", requests.adapters.HTTPAdapter(max_retries=3))
        session.mount("https://", requests.adapters.HTTPAdapter(max_retries=3))
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
        device_id = self.client_info.get_device_id().encode('utf-8')
        version = self.client_info.get_version().encode('utf-8')

        if authenticate:

            user = self._get_session_info(server_id)
            user_id = user['UserId'].encode('utf-8')
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
            'User-Agent': 'Emby-Kodi (%s)' % version
        })
        return header


    def downloadUrl(self, url, postBody=None, action_type="GET", parameters=None,
                    authenticate=True, server_id=None):

        log.debug("===== ENTER downloadUrl =====")

        kwargs = {}

        try:
            # Ensure server info is loaded
            self._ensure_server(server_id)
            server = self.session if server_id is None else self.servers[server_id]

            requires_server = False
            if url.find("{server}") > -1 or url.find("{UserId}") > -1:
                requires_server = True

            if requires_server and (not server or not server.get("Server") or not server.get("UserId")):
                #xbmcgui.Dialog().ok('Emby for Kodi', "You are not connected to your emby server.")
                raise Exception("Aborting download, Server Details Error: %s url=%s" % (server, url))

            if server_id is None and self.session_requests is not None: # Main server
                session = self.session_requests
            else:
                session = requests
                kwargs.update({
                    'verify': server.get('SSL', False),
                    'headers': self.get_header(server_id, authenticate)
                })

            # Replace for the real values
            if requires_server:
                url = url.replace("{server}", server['Server'])
                url = url.replace("{UserId}", server['UserId'])

            # does the URL look ok
            if url.startswith('/'):
                raise Exception("URL Error: " + url)

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
                if action_type == "GET":
                    raise Exception("Response Code 204 for GET request")
                else:
                    # this is probably valid for DELETE and PUT
                    return None

            elif response.status_code == requests.codes.ok:
                # UNICODE - JSON object
                json_data = response.json()
                log.debug("====== 200 Success ======")
                log.debug("Response: %s", json_data)
                return json_data

            else: # Bad status code
                log.error("=== Bad status response: %s ===", response.status_code)
                response.raise_for_status()

        ##### EXCEPTIONS #####

        except requests.exceptions.ConnectionError as error:
            # Make the addon aware of status
            if window('emby_online') != "false":
                log.error("Server unreachable at: %s", url)
                window('emby_online', value="false")

            raise HTTPException(None)

        except requests.exceptions.ReadTimeout as error:
            log.error("ReadTimeout at: %s", url)

            raise HTTPException(None)

        except requests.exceptions.HTTPError as error:

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

                elif status not in ("401", "Auth"):
                    # Tell userclient token has been revoked.
                    window('emby_serverStatus', value="401")
                    log.error("HTTP Error: %s", error)
                    xbmcgui.Dialog().notification(heading="Error connecting",
                                                  message="Unauthorized.",
                                                  icon=xbmcgui.NOTIFICATION_ERROR)

            raise HTTPException(response.status_code)

        # if we got to here and did not process the download for some reason then that is bad
        raise Exception("Unhandled Download : %s", url)

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
            'Token': ""
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
