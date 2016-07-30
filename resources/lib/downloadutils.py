# -*- coding: utf-8 -*-

##################################################################################################

import json
import requests
import logging

import xbmc
import xbmcgui

import clientinfo
from utils import window, settings

##################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class DownloadUtils():

    # Borg - multiple instances, shared state
    _shared_state = {}
    clientInfo = clientinfo.ClientInfo()

    # Requests session
    s = None
    default_timeout = 30


    def __init__(self):

        self.__dict__ = self._shared_state


    def setUsername(self, username):
        # Reserved for userclient only
        self.username = username
        log.debug("Set username: %s" % username)

    def setUserId(self, userId):
        # Reserved for userclient only
        self.userId = userId
        log.debug("Set userId: %s" % userId)

    def setServer(self, server):
        # Reserved for userclient only
        self.server = server
        log.debug("Set server: %s" % server)

    def setToken(self, token):
        # Reserved for userclient only
        self.token = token
        log.debug("Set token: %s" % token)

    def setSSL(self, ssl, sslclient):
        # Reserved for userclient only
        self.sslverify = ssl
        self.sslclient = sslclient
        log.debug("Verify SSL host certificate: %s" % ssl)
        log.debug("SSL client side certificate: %s" % sslclient)


    def postCapabilities(self, deviceId):

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

        log.debug("Capabilities URL: %s" % url)
        log.debug("Postdata: %s" % data)

        self.downloadUrl(url, postBody=data, action_type="POST")
        log.debug("Posted capabilities to %s" % self.server)

        # Attempt at getting sessionId
        url = "{server}/emby/Sessions?DeviceId=%s&format=json" % deviceId
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


    def startSession(self):

        self.deviceId = self.clientInfo.getDeviceId()

        # User is identified from this point
        # Attach authenticated header to the session
        verify = False
        header = self.getHeader()

        # If user enabled host certificate verification
        try:
            verify = self.sslverify
            if self.sslclient is not None:
                verify = self.sslclient
        except:
            log.info("Could not load SSL settings.")

        # Start session
        self.s = requests.Session()
        self.s.headers = header
        self.s.verify = verify
        # Retry connections to the server
        self.s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        log.info("Requests session started on: %s" % self.server)

    def stopSession(self):
        try:
            self.s.close()
        except Exception:
            log.warn("Requests session could not be terminated.")

    def getHeader(self, authenticate=True):

        deviceName = self.clientInfo.getDeviceName()
        deviceName = deviceName.encode('utf-8')
        deviceId = self.clientInfo.getDeviceId()
        version = self.clientInfo.getVersion()

        if authenticate:
            auth = (
                'MediaBrowser UserId="%s", Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (self.userId, deviceName, deviceId, version))
            header = {

                'Content-type': 'application/json',
                'Accept-encoding': 'gzip',
                'Accept-Charset': 'UTF-8,*',
                'Authorization': auth,
                'X-MediaBrowser-Token': self.token
            }
        else:
            # If user is not authenticated
            auth = (
                'MediaBrowser Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (deviceName, deviceId, version))
            header = {

                'Content-type': 'application/json',
                'Accept-encoding': 'gzip',
                'Accept-Charset': 'UTF-8,*',
                'Authorization': auth
            }

        return header

    def downloadUrl(self, url, postBody=None, action_type="GET", parameters=None,
                    authenticate=True):

        log.debug("===== ENTER downloadUrl =====")
        
        session = requests
        kwargs = {}
        default_link = ""

        try:
            if authenticate:

                if self.s is not None:
                    session = self.s
                else:
                    # request session does not exists
                    # Get user information
                    self.userId = window('emby_currUser')
                    self.server = window('emby_server%s' % self.userId)
                    self.token = window('emby_accessToken%s' % self.userId)
                    verifyssl = False

                    # IF user enables ssl verification
                    if settings('sslverify') == "true":
                        verifyssl = True
                    if settings('sslcert') != "None":
                        verifyssl = settings('sslcert')

                    kwargs.update({
                        'verify': verifyssl,
                        'headers': self.getHeader()
                    })

                # Replace for the real values
                url = url.replace("{server}", self.server)
                url = url.replace("{UserId}", self.userId)

            else: # User is not authenticated
                # If user enables ssl verification
                try:
                    verifyssl = self.sslverify
                    if self.sslclient is not None:
                        verifyssl = self.sslclient
                except AttributeError:
                    verifyssl = False

                kwargs.update({
                    'verify': verifyssl,
                    'headers': self.getHeader(authenticate=False)
                })

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
                        window('emby_serverStatus', value="restricted")
                        xbmcgui.Dialog().notification(
                                                heading="Emby server",
                                                message="Access restricted.",
                                                icon=xbmcgui.NOTIFICATION_ERROR,
                                                time=5000)
                        return False

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
                    return 401

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

        return default_link

    def _requests(self, action, session=requests, **kwargs):

        if action == "GET":
            r = session.get(**kwargs)
        elif action == "POST":
            r = session.post(**kwargs)
        elif action == "DELETE":
            r = session.delete(**kwargs)

        return r