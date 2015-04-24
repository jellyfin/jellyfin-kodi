import xbmc
import xbmcgui
import xbmcaddon

import requests
import json
import logging

import Utils as utils
from ClientInformation import ClientInformation
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Disable requests logging
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
logging.getLogger("requests").setLevel(logging.WARNING)

class DownloadUtils():
    
    # Borg - multiple instances, shared state
    _shared_state = {}
    clientInfo = ClientInformation()

    addonName = clientInfo.getAddonName()
    addonId = clientInfo.getAddonId()
    addon = xbmcaddon.Addon(id=addonId)
    WINDOW = xbmcgui.Window(10000)

    # Requests session
    s = None
    timeout = 30

    def __init__(self):

        self.__dict__ = self._shared_state
        self.className = self.__class__.__name__

    def logMsg(self, msg, lvl=1):

        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))

    def setUsername(self, username):
        # Reserved for UserClient only
        self.username = username
        self.logMsg("Set username: %s" % username, 1)

    def setUserId(self, userId):
        # Reserved for UserClient only
        self.userId = userId
        self.logMsg("Set userId: %s" % userId, 2)

    def setServer(self, server):
        # Reserved for UserClient only
        self.server = server
        self.logMsg("Set server: %s" % server, 2)

    def setToken(self, token):
        # Reserved for UserClient only
        self.token = token
        self.logMsg("Set token: %s" % token, 2)

    def setSSL(self, ssl):
        # Reserved for UserClient only
        self.ssl = ssl
        self.logMsg("Set ssl path: %s" % ssl, 2)

    def postCapabilities(self, deviceId):

        # Get sessionId
        url = "{server}/mediabrowser/Sessions?DeviceId=%s&format=json" % deviceId
        result = self.downloadUrl(url)
        # sessionId result
        self.logMsg("Session result: %s" % result, 1)
        self.sessionId = result[0][u'Id']

        # Settings for capabilities
        playableMediaTypes = "Audio,Video"
        supportedCommands = "Play,Playstate,SendString,DisplayMessage,PlayNext"

        # Post settings to sessionId
        url = "{server}/mediabrowser/Sessions/Capabilities?Id=%s&PlayableMediaTypes=%s&SupportedCommands=%s&SupportsMediaControl=True" % (self.sessionId, playableMediaTypes, supportedCommands)
        data = {}
        self.logMsg("Capabilities URL: %s" % url, 2)
        self.logMsg("PostData: %s" % data, 2)

        self.downloadUrl(url, postBody=data, type="POST")
        self.logMsg("Posted capabilities to sessionId: %s" % self.sessionId, 1)

    def startSession(self):

        self.deviceId = self.clientInfo.getMachineId()

        # User is identified from this point
        # Attach authenticated header to the session
        header = self.getHeader()
        cert = None
        verify = None

        # If user has a custom certificate, verify the host certificate too
        if (self.ssl != None):
            cert = self.ssl
            verify = True

        # Start session
        self.s = requests.Session()
        self.s.headers = header
        self.s.cert = cert
        self.s.verify = verify
        # Retry connections to the server
        self.s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        self.logMsg("Requests session started on: %s" % self.server)
        self.postCapabilities(self.deviceId)

    def imageUrl(self, id, type, index, width, height):
        # To move to API.py
        return "%s/mediabrowser/Items/%s/Images/%s?MaxWidth=%s&MaxHeight=%s&Index=%s" % (self.server, id, type, width, height, index)

    def getHeader(self, authenticate=True):

        clientInfo = self.clientInfo

        deviceName = clientInfo.getDeviceName()
        deviceId = clientInfo.getMachineId()
        version = clientInfo.getVersion()

        if not authenticate:
            # If user is not authenticated
            auth = 'MediaBrowser Client="Kodi", Device="%s", DeviceId="%s", Version="%s"' % (deviceName, deviceId, version)
            header = {"Accept-encoding": "gzip", "Accept-Charset": "UTF-8,*", "Authorization": auth}      
            
            self.logMsg("Header: %s" % header, 2)
            return header
        
        else:
            userId = self.userId
            token = self.token
            # Attached to the requests session
            auth = 'MediaBrowser UserId="%s", Client="Kodi", Device="%s", DeviceId="%s", Version="%s"' % (userId, deviceName, deviceId, version)
            header = {"Accept-encoding": "gzip", "Accept-Charset": "UTF-8,*", "Authorization": auth, "X-MediaBrowser-Token": token}        
                    
            self.logMsg("Header: %s" % header, 2)
            return header

    def downloadUrl(self, url, postBody=None, type="GET", authenticate=True):
        
        self.logMsg("=== ENTER downloadUrl ===", 2)

        WINDOW = self.WINDOW
        timeout = self.timeout
        default_link = ""

        # If user is authenticated
        if (authenticate):
            # Get requests session
            s = self.s
            # Replace for the real values and append api_key
            url = url.replace("{server}", self.server, 1)
            url = url.replace("{UserId}", self.userId, 1)
            url = "%s&api_key=%s" % (url, self.token)
            
            self.logMsg("URL: %s" % url, 2)
            # Prepare request
            if type == "GET":
                r = s.get(url, params=postBody, timeout=timeout)
            elif type == "POST":
                r = s.post(url, params=postBody, timeout=timeout)
            elif type == "DELETE":
                r = s.delete(url, params=postBody, timeout=timeout)

        # If user is not authenticated
        elif not authenticate:
            
            self.logMsg("URL: %s" % url, 1)
            header = self.getHeader(authenticate=False)
            
            # Prepare request
            if type == "GET":
                r = requests.get(url, params=postBody, headers=header, timeout=timeout, verify=False)
            elif type == "POST":
                r = requests.post(url, params=postBody, headers=header, timeout=timeout, verify=False)
        
        # Process the response
        try:
            r.raise_for_status()

            if r.status_code == 204:
                # No response in body
                self.logMsg("====== 204 Success ======", 2)
                return default_link
            # Response code 200
            elif r.status_code == requests.codes.ok:
                try: 
                    # UTF-8 - JSON object
                    r = r.json()
                    self.logMsg("====== 200 Success ======", 2)
                    return r
                except:
                    self.logMsg("Unable to convert the response for: %s" % url, 1)

            return default_link
        
        # TO REVIEW EXCEPTIONS
        except requests.exceptions.ConnectionError as e:
            self.logMsg("Server unreachable at: %s" % url, 0)
            self.logMsg(e, 1)

        except requests.exceptions.ConnectTimeout as e:
            self.logMsg("Server timeout at: %s" % url, 0)
            self.logMsg(e, 1)

        except requests.exceptions.HTTPError as e:

            if r.status_code == 401:
                # Unauthorized
                status = WINDOW.getProperty("Server_status")
                if (status == "401") or (status == "Auth"):
                    pass
                else:
                    # Tell UserClient token has been revoked.
                    WINDOW.setProperty("Server_status", "401")
                    self.logMsg("HTTP Error: %s" % e, 0)

            elif (r.status_code == 301) or (r.status_code == 302):
                # Redirects
                pass
            elif r.status_code == 400:
                # Bad requests
                pass

        except requests.exceptions.SSLError as e:
            self.logMsg("Invalid SSL certificate for: %s" % url, 0)
            self.logMsg(e, 1)

        except requests.exceptions.RequestException as e:
            self.logMsg("Unknown error connecting to: %s" % url, 0)
            self.logMsg(e, 1)

        return default_link
