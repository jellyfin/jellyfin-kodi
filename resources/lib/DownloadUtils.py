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
    timeout = 60

    def __init__(self):

        self.__dict__ = self._shared_state

    def logMsg(self, msg, lvl=1):

        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))

    def setUsername(self, username):
        # Reserved for UserClient only
        self.username = username
        self.logMsg("Set username: %s" % username, 2)

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

    def setSSL(self, ssl, sslclient):
        # Reserved for UserClient only
        self.sslverify = ssl
        self.sslclient = sslclient
        self.logMsg("Verify SSL host certificate: %s" % ssl, 2)
        self.logMsg("SSL client side certificate: %s" % sslclient, 2)

    def postCapabilities(self, deviceId):

        # Post settings to session
        url = "{server}/mediabrowser/Sessions/Capabilities/Full"
        data = {
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (
                
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"

                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext"
            )
        }

        self.logMsg("Capabilities URL: %s" % url, 2)
        self.logMsg("PostData: %s" % data, 2)

        try:
            self.downloadUrl(url, postBody=data, type="POST")
            self.logMsg("Posted capabilities to %s" % self.server, 1)
        except:
            self.logMsg("Posted capabilities failed.")

        # Attempt at getting sessionId
        url = "{server}/mediabrowser/Sessions?DeviceId=%s&format=json" % deviceId

        try:
            result = self.downloadUrl(url)
            self.logMsg("Session: %s" % result, 2)
            
            sessionId = result[0][u'Id']
            self.logMsg("SessionId: %s" % sessionId)
            self.WINDOW.setProperty("sessionId%s" % self.username, sessionId)
        except:
            self.logMsg("Failed to retrieve sessionId.", 1)

    def startSession(self):

        self.deviceId = self.clientInfo.getMachineId()

        # User is identified from this point
        # Attach authenticated header to the session
        verify = None
        cert = None
        header = self.getHeader()

        # If user enabled host certificate verification
        try:
            verify = self.sslverify
            cert = self.sslclient
        except:
            self.logMsg("Could not load SSL settings.", 1)
        
        # Start session
        self.s = requests.Session()
        self.s.headers = header
        self.s.verify = verify
        self.s.cert = cert
        # Retry connections to the server
        self.s.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.s.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        self.logMsg("Requests session started on: %s" % self.server)

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
            header = {'Content-type': 'application/json', 'Accept-encoding': 'gzip', 'Accept-Charset': 'UTF-8,*', 'Authorization': auth}      
            
            self.logMsg("Header: %s" % header, 2)
            return header
        
        else:
            userId = self.userId
            token = self.token
            # Attached to the requests session
            auth = 'MediaBrowser UserId="%s", Client="Kodi", Device="%s", DeviceId="%s", Version="%s"' % (userId, deviceName, deviceId, version)
            header = {'Content-type': 'application/json', 'Accept-encoding': 'gzip', 'Accept-Charset': 'UTF-8,*', 'Authorization': auth, 'X-MediaBrowser-Token': token}        
                    
            self.logMsg("Header: %s" % header, 2)
            return header

    def downloadUrl(self, url, postBody=None, type="GET", authenticate=True):
        
        self.logMsg("=== ENTER downloadUrl ===", 2)

        WINDOW = self.WINDOW
        timeout = self.timeout
        default_link = ""

        try:

            # If user is authenticated
            if (authenticate):
                # Get requests session
                try: 
                    s = self.s
                    # Replace for the real values and append api_key
                    url = url.replace("{server}", self.server, 1)
                    url = url.replace("{UserId}", self.userId, 1)
                    #url = "%s&api_key=%s" % (url, self.token)

                    self.logMsg("URL: %s" % url, 2)
                    # Prepare request
                    if type == "GET":
                        r = s.get(url, json=postBody, timeout=timeout)
                    elif type == "POST":
                        r = s.post(url, json=postBody, timeout=timeout)
                    elif type == "DELETE":
                        r = s.delete(url, json=postBody, timeout=timeout)
                
                except AttributeError:
                    
                    # Get user information
                    self.username = WINDOW.getProperty('currUser')
                    self.userId = WINDOW.getProperty('userId%s' % self.username)
                    self.server = WINDOW.getProperty('server%s' % self.username)
                    self.token = WINDOW.getProperty('accessToken%s' % self.username)
                    header = self.getHeader()
                    verifyssl = False
                    cert = None

                    # IF user enables ssl verification
                    try:
                        if self.addon.getSetting('sslverify') == "true":
                            verifyssl = True
                        if self.addon.getSetting('sslcert') != "None":
                            cert = self.addon.getSetting('sslcert')
                    except:
                        self.logMsg("Could not load SSL settings.", 1)
                        pass

                    # Replace for the real values and append api_key
                    url = url.replace("{server}", self.server, 1)
                    url = url.replace("{UserId}", self.userId, 1)

                    self.logMsg("URL: %s" % url, 2)
                    # Prepare request
                    if type == "GET":
                        r = requests.get(url, json=postBody, headers=header, timeout=timeout, cert=cert, verify=verifyssl)
                    elif type == "POST":
                        r = requests.post(url, json=postBody, headers=header, timeout=timeout, cert=cert, verify=verifyssl)
                    elif type == "DELETE":
                        r = requests.delete(url, json=postBody, headers=header, timeout=timeout, cert=cert, verify=verifyssl)

            # If user is not authenticated
            elif not authenticate:
                
                self.logMsg("URL: %s" % url, 2)
                header = self.getHeader(authenticate=False)
                verifyssl = False

                # If user enables ssl verification
                try:
                    verifyssl = self.sslverify
                except AttributeError:
                    pass
                
                # Prepare request
                if type == "GET":
                    r = requests.get(url, json=postBody, headers=header, timeout=timeout, verify=verifyssl)
                elif type == "POST":
                    r = requests.post(url, json=postBody, headers=header, timeout=timeout, verify=verifyssl)
        
            # Process the response
            if r.status_code == 204:
                # No body in the response
                self.logMsg("====== 204 Success ======", 2)
                return default_link

            elif r.status_code == requests.codes.ok:
                try: 
                    # UTF-8 - JSON object
                    r = r.json()
                    self.logMsg("====== 200 Success ======", 2)
                    self.logMsg("Response: %s" % r, 2)
                    return r
                except:
                    if r.headers['content-type'] == "text/html":
                        pass
                    else:
                        self.logMsg("Unable to convert the response for: %s" % url, 1)
            else:
                r.raise_for_status()

            return default_link
        
        # TO REVIEW EXCEPTIONS
        except requests.exceptions.ConnectionError as e:
            # Make the addon aware of status
            if WINDOW.getProperty("Server_online") != "false":
                self.logMsg("Server unreachable at: %s" % url, 0)
                self.logMsg(e, 2)
                WINDOW.setProperty("Server_online", "false")
            pass

        except requests.exceptions.ConnectTimeout as e:
            self.logMsg("Server timeout at: %s" % url, 0)
            self.logMsg(e, 1)

        except requests.exceptions.HTTPError as e:

            if r.status_code == 401:
                # Unauthorized
                status = WINDOW.getProperty("Server_status")

                if 'x-application-error-code' in r.headers:
                    if r.headers['X-Application-Error-Code'] == "ParentalControl":
                        # Parental control - access restricted
                        WINDOW.setProperty("Server_status", "restricted")
                        xbmcgui.Dialog().notification("Emby server", "Access restricted.", xbmcgui.NOTIFICATION_ERROR, time=5000)
                        return False

                if (status == "401") or (status == "Auth"):
                    pass

                else:
                    # Tell UserClient token has been revoked.
                    WINDOW.setProperty("Server_status", "401")
                    self.logMsg("HTTP Error: %s" % e, 0)
                    xbmcgui.Dialog().notification("Error connecting", "Unauthorized.", xbmcgui.NOTIFICATION_ERROR)
                    return 401

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
