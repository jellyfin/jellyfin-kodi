#################################################################################################
# UserClient thread
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import threading
import hashlib
import json as json

import KodiMonitor
import Utils as utils
from ClientInformation import ClientInformation
from DownloadUtils import DownloadUtils


class UserClient(threading.Thread):

    # Borg - multiple instances, shared state
    _shared_state = {}

    clientInfo = ClientInformation()
    doUtils = DownloadUtils()
    KodiMonitor = KodiMonitor.Kodi_Monitor()
    
    addonName = clientInfo.getAddonName()
    addonId = clientInfo.getAddonId()
    addon = xbmcaddon.Addon(id=addonId)
    WINDOW = xbmcgui.Window(10000)

    stopClient = False
    logLevel = int(addon.getSetting('logLevel'))
    auth = True
    retry = 0

    currUser = None
    currUserId = None
    currServer = None
    currToken = None
    HasAccess = True
    AdditionalUser = []

    def __init__(self, *args):

        self.__dict__ = self._shared_state
        threading.Thread.__init__(self, *args)

    def logMsg(self, msg, lvl=1):
        
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), str(msg), int(lvl))

    def getUsername(self):

        addon = xbmcaddon.Addon(id=self.addonId)
        username = addon.getSetting('username')

        if (username == ""):
            self.logMsg("No username saved.", 2)
            return ""

        return username

    def getLogLevel(self):

        logLevel = int(self.addon.getSetting('logLevel'))
        return logLevel

    def getUserId(self):

        username = self.getUsername()
        w_userId = self.WINDOW.getProperty('userId%s' % username)
        s_userId = self.addon.getSetting('userId%s' % username)

        # Verify the window property
        if (w_userId != ""):
            self.logMsg("Returning userId from WINDOW for username: %s UserId: %s" % (username, w_userId), 2)
            return w_userId
        # Verify the settings
        elif (s_userId != ""):
            self.logMsg("Returning userId from SETTINGS for username: %s userId: %s" % (username, s_userId), 2)
            return s_userId
        # No userId found
        else:
            self.logMsg("No userId saved for username: %s." % username)
            return

    def getServer(self, prefix=True):

        # For https support
        addon = xbmcaddon.Addon(id=self.addonId)
        HTTPS = addon.getSetting('https')
        host = addon.getSetting('ipaddress')
        port = addon.getSetting('port')
        server = host + ":" + port
        
        if host == "":
            self.logMsg("No server information saved.", 2)
            return ""

        # If https is true
        if prefix and (HTTPS == "true"):
            server = "https://%s" % server
            return server
        # If https is false
        elif prefix and (HTTPS == "false"):
            server = "http://%s" % server
            return server
        # If only the host:port is required
        elif (prefix == False):
            return server

    def getToken(self):

        username = self.getUsername()
        w_token = self.WINDOW.getProperty('accessToken%s' % username)
        s_token = self.addon.getSetting('accessToken')
        
        # Verify the window property
        if (w_token != ""):
            self.logMsg("Returning accessToken from WINDOW for username: %s accessToken: %s" % (username, w_token), 2)
            return w_token
        # Verify the settings
        elif (s_token != ""):
            self.logMsg("Returning accessToken from SETTINGS for username: %s accessToken: %s" % (username, s_token), 2)
            self.WINDOW.setProperty('accessToken%s' % username, s_token)
            return s_token
        else:
            self.logMsg("No token found.")
            return ""

    def getSSLverify(self):
        # Verify host certificate
        s_sslverify = self.addon.getSetting('sslverify')

        if s_sslverify == "true":
            return True
        else:
            return False

    def getSSL(self):
        # Client side certificate
        s_cert = self.addon.getSetting('sslcert')

        if s_cert == "None":
            return None
        else:
            return s_cert

    def setUserPref(self):

        server = self.getServer()
        userId = self.getUserId()
        addon = self.addon

        url = "{server}/mediabrowser/Users/{UserId}?format=json"
        result = self.doUtils.downloadUrl(url)

        audio = result[u'Configuration'].get(u'AudioLanguagePreference', "default")
        subs = result[u'Configuration'].get(u'SubtitleLanguagePreference', "default")
        addon.setSetting('Audiopref', audio)
        addon.setSetting('Subspref', subs)

        self.logMsg("Audio preference: %s" % audio, 2)
        self.logMsg("Subtitles preference: %s" % subs, 2)

        return True

    def getPublicUsers(self):

        server = self.getServer()

        # Get public Users
        url = "%s/mediabrowser/Users/Public?format=json" % server
        result = self.doUtils.downloadUrl(url, authenticate=False)
        
        users = []
        
        if (result != ""):
            users = result
        else:
            # Server connection failed
            return False

        return users

    def hasAccess(self):

        url = "{server}/mediabrowser/Users"
        result = self.doUtils.downloadUrl(url)
        
        if result is False:
            # Access is restricted
            self.logMsg("Access is restricted.")
            self.HasAccess = False
            return
        elif self.WINDOW.getProperty('Server_online') != "true":
            # Server connection failed
            return

        if self.WINDOW.getProperty("Server_status") == "restricted":
            self.logMsg("Access is granted.")
            self.HasAccess = True
            self.WINDOW.setProperty("Server_status", "")
            xbmcgui.Dialog().notification("Emby server", "Access is enabled.")
        return

    def loadCurrUser(self, authenticated=False):

        WINDOW = self.WINDOW
        doUtils = self.doUtils
        username = self.getUsername()

        # Only to be used if token exists
        self.currUserId = self.getUserId()
        self.currServer = self.getServer()
        self.currToken = self.getToken()
        self.ssl = self.getSSLverify()
        self.sslcert = self.getSSL()

        # Test the validity of current token
        if authenticated == False:
            url = "%s/mediabrowser/Users/%s" % (self.currServer, self.currUserId)
            WINDOW.setProperty("currUser", username)
            WINDOW.setProperty("accessToken%s" % username, self.currToken)
            result = doUtils.downloadUrl(url, type="POST")
            if result == 401:
                # Token is no longer valid
                self.resetClient()
                return False

        # Set to windows property
        WINDOW.setProperty("currUser", username)
        WINDOW.setProperty("accessToken%s" % username, self.currToken)
        WINDOW.setProperty("server%s" % username, self.currServer)
        WINDOW.setProperty("server_%s" % username, self.getServer(prefix=False))
        WINDOW.setProperty("userId%s" % username, self.currUserId)

        # Set DownloadUtils values
        doUtils.setUsername(username)
        doUtils.setUserId(self.currUserId)
        doUtils.setServer(self.currServer)
        doUtils.setToken(self.currToken)
        doUtils.setSSL(self.ssl, self.sslcert)
        # parental control - let's verify if access is restricted
        self.hasAccess()
        # Start DownloadUtils session
        doUtils.startSession()

        # Set user preferences in settings
        self.setUserPref()

        self.currUser = username

    def authenticate(self):

        WINDOW = self.WINDOW
        addon = self.addon

        username = self.getUsername()
        server = self.getServer()
        addondir = xbmc.translatePath(self.addon.getAddonInfo('profile'))
        hasSettings   = xbmcvfs.exists("%ssettings.xml" % addondir)

        # If there's no settings.xml
        if (hasSettings == 0):
            self.logMsg("No settings.xml found.")
            self.auth = False
            return
        # If no user information
        if (server == "") or (username == ""):
            self.logMsg("Missing server information.")
            self.auth = False
            return
        # If there's a token
        if (self.getToken() != ""):
            result = self.loadCurrUser()

            if result == False:
                pass
            else:
                self.logMsg("Current user: %s" % self.currUser, 0)
                self.logMsg("Current userId: %s" % self.currUserId, 0)
                self.logMsg("Current accessToken: %s" % self.currToken, 0)
                return
        
        users = self.getPublicUsers()
        password = ""
        
        # Find user in list
        for user in users:
            name = user[u'Name']
            userHasPassword = False

            if (unicode(username, 'utf-8') in name):
                # Verify if user has a password
                if (user.get("HasPassword") == True):
                    userHasPassword = True
                # If user has password
                if (userHasPassword):
                    password = xbmcgui.Dialog().input("Enter password for user: %s" % username, option=xbmcgui.ALPHANUM_HIDE_INPUT)
                    # If password dialog is cancelled
                    if (password == ""):
                        self.logMsg("No password entered.", 0)
                        self.WINDOW.setProperty("Server_status", "Stop")
                        self.auth = False
                        return
                break
        else:
            # Manual login, user is hidden
            password = xbmcgui.Dialog().input("Enter password for user: %s" % username, option=xbmcgui.ALPHANUM_HIDE_INPUT)
            
        sha1 = hashlib.sha1(password)
        sha1 = sha1.hexdigest()    

        # Authenticate username and password
        url = "%s/mediabrowser/Users/AuthenticateByName?format=json" % server
        data = {'username': username, 'password': sha1}
        self.logMsg(data, 2)

        result = self.doUtils.downloadUrl(url, postBody=data, type="POST", authenticate=False)

        accessToken = None
        try:
            self.logMsg("Auth_Reponse: %s" % result, 1)
            accessToken = result[u'AccessToken']
        except:
            pass

        if (result != None and accessToken != None):
            self.currUser = username
            xbmcgui.Dialog().notification("Emby server", "Welcome %s!" % self.currUser)
            userId = result[u'User'][u'Id']
            addon.setSetting("accessToken", accessToken)
            addon.setSetting("userId%s" % username, userId)
            self.logMsg("User Authenticated: %s" % accessToken)
            self.loadCurrUser(authenticated=True)
            self.WINDOW.setProperty("Server_status", "")
            self.retry = 0
            return
        else:
            self.logMsg("User authentication failed.")
            addon.setSetting("accessToken", "")
            addon.setSetting("userId%s" % username, "")
            xbmcgui.Dialog().ok("Error connecting", "Invalid username or password.")
            
            # Give two attempts at entering password
            self.retry += 1
            if self.retry == 2:
                self.logMsg("Too many retries. You can retry by selecting the option in the addon settings.")
                self.WINDOW.setProperty("Server_status", "Stop")
                xbmcgui.Dialog().ok("Error connecting", "Failed to authenticate too many times. You can retry by selecting the option in the addon settings.")
            
            self.auth = False
            return

    def resetClient(self):

        username = self.getUsername()
        self.logMsg("Reset UserClient authentication.", 1)
        if (self.currToken != None):
            # In case of 401, removed saved token
            self.addon.setSetting("accessToken", "")
            self.WINDOW.setProperty("accessToken%s" % username, "")
            self.currToken = None
            self.logMsg("User token has been removed.", 1)
        
        self.auth = True
        self.currUser = None
        return
        

    def run(self):

        self.logMsg("|---- Starting UserClient ----|", 0)

        while not self.KodiMonitor.abortRequested():

            # Get the latest addon settings
            self.addon = xbmcaddon.Addon(id=self.addonId)
            # Verify the log level
            currLogLevel = self.getLogLevel()
            if self.logLevel != currLogLevel:
                # Set new log level
                self.logLevel = currLogLevel
                self.logMsg("New Log Level: %s" % currLogLevel, 0)
                self.WINDOW.setProperty('getLogLevel', str(currLogLevel)) 

            if (self.WINDOW.getProperty("Server_status") != ""):
                status = self.WINDOW.getProperty("Server_status")
                
                if status == "restricted":
                    # Parental control is restricting access
                    self.HasAccess = False

                elif status == "401":
                    self.WINDOW.setProperty("Server_status", "Auth")
                    # Revoked token
                    self.resetClient()

            if self.auth and (self.currUser == None):
                status = self.WINDOW.getProperty("Server_status")
                
                if (status == "") or (status == "Auth"):
                    self.auth = False
                    self.authenticate()
                
            if (self.auth == False) and (self.currUser == None):
                # Only if there's information found to login
                server = self.getServer()
                username = self.getUsername()
                status = self.WINDOW.getProperty("Server_status")

                # If user didn't enter a password when prompted
                if status == "Stop":
                    pass
                
                elif (server != "") and (username != ""):
                    self.logMsg("Server found: %s" % server)
                    self.logMsg("Username found: %s" % username)
                    self.auth = True

            # If stopping the client didn't work
            if self.stopClient == True:
                break
                
            if self.KodiMonitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break
                
        self.logMsg("|---- UserClient Stopped ----|", 0)

    def stopClient(self):
        # As last resort
        self.stopClient = True