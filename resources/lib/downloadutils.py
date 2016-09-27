# -*- coding: utf-8 -*-

##################################################################################################

import json
import requests
import logging

import xbmc
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


    def _set_session(self, **kwargs):
        # Reserved for userclient only
        info = {}
        for key in kwargs:
            info[key] = kwargs[key]

        self.session.update(info)
        log.info("Set info for server %s: %s", self.session['ServerId'], self.session)

    def add_server(self, server, ssl):
        # Reserved for userclient only
        server_id = server['Id']
        info = {
            'UserId': server['UserId'],
            'Server': connectionmanager.getServerAddress(server, server['LastConnectionMode']),
            'Token': server['AccessToken'],
            'SSL': ssl
        }
        for s in self.servers:
            if s == server_id:
                s.update(info)
                # Set window prop
                self._set_server_properties(server_id, server['Name'], json.dumps(info))
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
                self.servers.remove(s)
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

        log.debug("capabilities URL: %s" % url)
        log.debug("Postdata: %s" % data)

        self.downloadUrl(url, postBody=data, action_type="POST")
        log.debug("Posted capabilities to %s" % self.session['Server'])

        # Attempt at getting sessionId
        url = "{server}/emby/Sessions?DeviceId=%s&format=json" % device_id
        result = self.downloadUrl(url)
        try:
            sessionId = result[0]['Id']

        except (KeyError, TypeError):
            log.info("Failed to retrieve sessionId.")

        else:
            log.debug("Session: %s" % result)
            log.info("SessionId: %s" % sessionId)
            window('emby_sessionId', value=sessionId)

            # Post any permanent additional users
            additionalUsers = settings('additionalUsers')
            if additionalUsers:

                additionalUsers = additionalUsers.split(',')
                log.info("List of permanent users added to the session: %s" % additionalUsers)

                # Get the user list from server to get the userId
                url = "{server}/emby/Users?format=json"
                result = self.downloadUrl(url)

                for additional in additionalUsers:
                    addUser = additional.decode('utf-8').lower()

                    # Compare to server users to list of permanent additional users
                    for user in result:
                        username = user['Name'].lower()

                        if username in addUser:
                            userId = user['Id']
                            url = (
                                    "{server}/emby/Sessions/%s/Users/%s?format=json"
                                    % (sessionId, userId)
                            )
                            self.downloadUrl(url, postBody={}, action_type="POST")


    def start_session(self):
        # User is identified from this point
        # Attach authenticated header to the session
        # Start session
        s = requests.Session()
        s.headers = self.get_header()
        s.verify = self.session['SSL']
        # Retry connections to the server
        s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))
        self.session_requests = s

        log.info("Requests session started on: %s" % self.session['Server'])

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

            user = self.get_user(server_id)
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

    def get_user(self, server_id=None):

        if server_id is None:
            return {
                'UserId': self.session['UserId'],
                'Token': self.session['Token']
            }
        else:
            server = self.servers[server_id]
            return {
                'UserId': server['UserId'],
                'Token': server['Token']
            }

    def downloadUrl(self, url, postBody=None, action_type="GET", parameters=None,
                    authenticate=True, server_id=None):

        log.debug("===== ENTER downloadUrl =====")
        
        session = requests
        kwargs = {}
        default_link = ""

        try: # Ensure server info is loaded
            if not self._ensure_server(server_id):
                raise AttributeError("unable to load server information: %s" % server_id)

            if server_id is None:
                if self.session_requests is not None:
                    session = self.session_requests
                else:
                    kwargs.update({
                        'verify': self.session['SSL'],
                        'headers': self.get_header(authenticate=authenticate)
                    })
                # Replace for the real values
                url = url.replace("{server}", self.session['Server'])
                url = url.replace("{UserId}", self.session['UserId'])
            else:
                server = self.servers[server_id]
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
            r = self._requests(action_type, session, **kwargs)

            if r.status_code == 204:
                # No body in the response
                log.debug("====== 204 Success ======")
                # Read response to release connection
                r.content

            elif r.status_code == requests.codes.ok:
                try:
                    # UNICODE - JSON object
                    r = r.json()
                    log.debug("====== 200 Success ======")
                    log.debug("Response: %s" % r)
                    return r

                except:
                    if r.headers.get('content-type') != "text/html":
                        log.info("Unable to convert the response for: %s" % url)

            else: # Bad status code
                log.error("=== Bad status response: %s ===" % r.status_code)
                r.raise_for_status()

        ##### EXCEPTIONS #####

        except requests.exceptions.ConnectionError as e:
            # Make the addon aware of status
            if window('emby_online') != "false":
                log.error("Server unreachable at: %s" % url)
                window('emby_online', value="false")

        except requests.exceptions.ConnectTimeout as e:
            log.error("Server timeout at: %s" % url)

        except requests.exceptions.HTTPError as e:

            if r.status_code == 401:
                # Unauthorized
                status = window('emby_serverStatus')

                if 'X-Application-Error-Code' in r.headers:
                    # Emby server errors
                    if r.headers['X-Application-Error-Code'] == "ParentalControl":
                        # Parental control - access restricted
                        if status != "restricted":
                            xbmcgui.Dialog().notification(
                                                    heading=lang(29999),
                                                    message="Access restricted.",
                                                    icon=xbmcgui.NOTIFICATION_ERROR,
                                                    time=5000)
                        
                        window('emby_serverStatus', value="restricted")
                        raise Warning('restricted')

                    elif r.headers['X-Application-Error-Code'] == "UnauthorizedAccessException":
                        # User tried to do something his emby account doesn't allow
                        pass

                elif status not in ("401", "Auth"):
                    # Tell userclient token has been revoked.
                    window('emby_serverStatus', value="401")
                    log.error("HTTP Error: %s" % e)
                    xbmcgui.Dialog().notification(
                                            heading="Error connecting",
                                            message="Unauthorized.",
                                            icon=xbmcgui.NOTIFICATION_ERROR)
                    raise Warning('401')

            elif r.status_code in (301, 302):
                # Redirects
                pass
            elif r.status_code == 400:
                # Bad requests
                pass

        except requests.exceptions.SSLError as e:
            log.error("Invalid SSL certificate for: %s" % url)

        except requests.exceptions.RequestException as e:
            log.error("Unknown error connecting to: %s" % url)

        except AttributeError as error:
            log.error(error)

        return default_link

    
    def _ensure_server(self, server_id=None):

        if server_id is None and self.session_requests is None:
            
            server = self._get_session_info()
            self.session.update(server)

        elif server_id and server_id not in self.servers:
            
            server = self._get_session_info(server_id)
            if server is None:
                return False

            self.servers[server_id] = server

        return True

    @classmethod
    def _get_session_info(cls, server_id=None):
        
        info = {}

        if server_id is None: # Main server

            user_id = window('emby_currUser')
            info.update({
                'UserId': user_id,
                'Server': window('emby_server%s' % user_id),
                'Token': window('emby_accessToken%s' % user_id)
            })
            verifyssl = False
            # If user enables ssl verification
            if settings('sslverify') == "true":
                verifyssl = True
            if settings('sslcert') != "None":
                verifyssl = settings('sslcert')

            info['SSL'] = verifyssl

        else: # Other connect servers
            server = window('emby_server%s.json' % server_id)
            if server:
                info.update(json.loads(server))

        return info

    @classmethod
    def _requests(cls, action, session=requests, **kwargs):

        if action == "GET":
            response = session.get(**kwargs)
        elif action == "POST":
            response = session.post(**kwargs)
        elif action == "DELETE":
            response = session.delete(**kwargs)

        return response