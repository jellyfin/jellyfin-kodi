# -*- coding: utf-8 -*-

##################################################################################################

import json
import requests
import logging

import xbmc
import xbmcgui

import clientinfo
from utils import Logging, window, settings
import utils

##################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)
#logging.getLogger('requests').setLevel(logging.WARNING)

##################################################################################################


class DownloadUtils():

    # Borg - multiple instances, shared state
    _shared_state = {}
    clientInfo = clientinfo.ClientInfo()
    addonName = clientInfo.getAddonName()

    # Requests session
    s = None
    timeout = 30


    def __init__(self):

        global log
        log = Logging(self.__class__.__name__).log

        self.__dict__ = self._shared_state


    def setUsername(self, username):
        # Reserved for userclient only
        self.username = username
        log("Set username: %s" % username, 2)

    def setUserId(self, userId):
        # Reserved for userclient only
        self.userId = userId
        log("Set userId: %s" % userId, 2)

    def setServer(self, server):
        # Reserved for userclient only
        self.server = server
        log("Set server: %s" % server, 2)

    def setToken(self, token):
        # Reserved for userclient only
        self.token = token
        log("Set token: %s" % token, 2)

    def setSSL(self, ssl, sslclient):
        # Reserved for userclient only
        self.sslverify = ssl
        self.sslclient = sslclient
        log("Verify SSL host certificate: %s" % ssl, 2)
        log("SSL client side certificate: %s" % sslclient, 2)


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

        log("Capabilities URL: %s" % url, 2)
        log("Postdata: %s" % data, 2)

        self.downloadUrl(url, postBody=data, action_type="POST")
        log("Posted capabilities to %s" % self.server, 2)

        # Attempt at getting sessionId
        url = "{server}/emby/Sessions?DeviceId=%s&format=json" % deviceId
        result = self.downloadUrl(url)
        try:
            sessionId = result[0]['Id']

        except (KeyError, TypeError):
            log("Failed to retrieve sessionId.", 1)

        else:
            log("Session: %s" % result, 2)
            log("SessionId: %s" % sessionId, 1)
            window('emby_sessionId', value=sessionId)

            # Post any permanent additional users
            additionalUsers = settings('additionalUsers')
            if additionalUsers:

                additionalUsers = additionalUsers.split(',')
                log("List of permanent users added to the session: %s"
                    % additionalUsers, 1)

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
            log("Could not load SSL settings.", 1)

        # Start session
        self.s = requests.Session()
        self.s.headers = header
        self.s.verify = verify
        # Retry connections to the server
        self.s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        log("Requests session started on: %s" % self.server, 1)

    def stopSession(self):
        try:
            self.s.close()
        except:
            log("Requests session could not be terminated.", 1)

    def getHeader(self, authenticate=True):

        deviceName = self.clientInfo.getDeviceName()
        deviceName = deviceName.encode('utf-8')
        deviceId = self.clientInfo.getDeviceId()
        version = self.clientInfo.getVersion()

        if not authenticate:
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
        else:
            userId = self.userId
            token = self.token
            # Attached to the requests session
            auth = (
                'MediaBrowser UserId="%s", Client="Kodi", Device="%s", DeviceId="%s", Version="%s"'
                % (userId, deviceName, deviceId, version))
            header = {

                'Content-type': 'application/json',
                'Accept-encoding': 'gzip',
                'Accept-Charset': 'UTF-8,*',
                'Authorization': auth,
                'X-MediaBrowser-Token': token
            }

        return header

    def downloadUrl(self, url, postBody=None, action_type="GET", parameters=None,
                    authenticate=True):

        log("===== ENTER downloadUrl =====", 2)
        
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
                'timeout': self.timeout,
                'json': postBody,
                'params': parameters
            })

            ##### THE RESPONSE #####
            log(kwargs, 2)
            r = self.__requests(action_type, session, **kwargs)

            if r.status_code == 204:
                # No body in the response
                log("====== 204 Success ======", 2)
                # Read response to release connection
                r.content

            elif r.status_code == requests.codes.ok:
                try:
                    # UNICODE - JSON object
                    r = r.json()
                    log("====== 200 Success ======", 2)
                    log("Response: %s" % r, 2)
                    return r

                except:
                    if r.headers.get('content-type') != "text/html":
                        log("Unable to convert the response for: %s" % url, 1)

            else: # Bad status code
                r.raise_for_status()

        ##### EXCEPTIONS #####

        except requests.exceptions.ConnectionError as e:
            # Make the addon aware of status
            if window('emby_online') != "false":
                log("Server unreachable at: %s" % url, 0)
                log(e, 2)
                window('emby_online', value="false")

        except requests.exceptions.ConnectTimeout as e:
            log("Server timeout at: %s" % url, 0)
            log(e, 1)

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
                    log("HTTP Error: %s" % e, 0)
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
            log("Invalid SSL certificate for: %s" % url, 0)
            log(e, 1)

        except requests.exceptions.RequestException as e:
            log("Unknown error connecting to: %s" % url, 0)
            log(e, 1)

        return default_link

    @utils.timeIt
    def __requests(self, action, session=requests, **kwargs):

        if action == "GET":
            r = session.get(**kwargs)
        elif action == "POST":
            r = session.post(**kwargs)
        elif action == "DELETE":
            r = session.delete(**kwargs)

        return r