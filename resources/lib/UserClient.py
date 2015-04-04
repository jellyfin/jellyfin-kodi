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
from ClientInformation import ClientInformation
from DownloadUtils import DownloadUtils


class UserClient(threading.Thread):


    clientInfo = ClientInformation()
    doUtils = DownloadUtils()

    stopClient = False
    logLevel = 0
    addon = None
    auth = True
    retry = 0
    WINDOW = xbmcgui.Window(10000)

    currUser = None
    currUserId = None
    currServer = None
    currToken = None
    AdditionalUser = []

    def __init__(self, *args):

        clientInfo = self.clientInfo
        self.KodiMonitor = KodiMonitor.Kodi_Monitor()

        self.addonId = clientInfo.getAddonId()
        self.addonName = clientInfo.getAddonName()
        self.addon = xbmcaddon.Addon(id=self.addonId)

        threading.Thread.__init__(self, *args)

    def logMsg(self, msg, level=1):

        addonName = self.addonName
        className = self.__class__.__name__

        if (self.logLevel != self.getLogLevel()):
            xbmc.log("Adjusting logLevel to %i" % self.getLogLevel())
            self.logLevel = self.getLogLevel()

        if (self.logLevel >= level):
            try:
                xbmc.log("%s %s -> %s" % (addonName, className, str(msg)))
            except UnicodeEncodeError:
                try:
                    xbmc.log("%s %s -> %s" % (addonName, className, str(msg.encode('utf-8'))))
                except:
                    pass

    def getUsername(self):

        username = self.addon.getSetting('username')
        
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
        addon = self.addon
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
        s_token = self.addon.getSetting('accessToken%s' % username)
        
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

    def getPublicUsers(self):

        server = self.getServer()

        # Get public Users
        url = "%s/mediabrowser/Users/Public?format=json" % server
        jsonData = self.doUtils.downloadUrl(url, authenticate=False)
        
        users = []
        
        if (jsonData != ""):
            users = json.loads(jsonData)

        return users

    def loadCurrUser(self):

        WINDOW = self.WINDOW
        username = self.getUsername()

        # Only to be used if token exists
        self.currUserId = self.getUserId()
        self.currServer = self.getServer()
        self.currToken = self.getToken()

        # Set to windows property
        WINDOW.setProperty("currUser", username)
        WINDOW.setProperty("accessToken%s" % username, self.currToken)
        WINDOW.setProperty("server%s" % username, self.currServer)
        WINDOW.setProperty("server_%s" % username, self.getServer(prefix=False))
        WINDOW.setProperty("userId%s" % username, self.currUserId)

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
            self.loadCurrUser()
            self.logMsg("Current user: %s" % self.currUser, 0)
            self.logMsg("Current userId: %s" % self.currUserId, 0)
            self.logMsg("Current accessToken: %s" % self.currToken, 0)
            return
        
        users = self.getPublicUsers()
        password = ""
        
        # Find user in list
        for user in users:
            name = user.get("Name")
            userHasPassword = False
            if (username == name):
                # Verify if user has a password
                if (user.get("HasPassword") == True):
                    userHasPassword = True
                # If user has password
                if (userHasPassword):
                    password = xbmcgui.Dialog().input("Enter password for user: %s" % username, option=xbmcgui.ALPHANUM_HIDE_INPUT)
                    # If password dialog is cancelled
                    if password == "":
                        self.logMsg("No password entered.", 0)
                        #addon.setSetting("username", "")
                        self.WINDOW.setProperty("Server_status", "Stop")
                        self.auth = False
                        #self.WINDOW.setProperty("Server_status", "")
                        return
                break
        else:
            # Manual login, user is hidden
            password = xbmcgui.Dialog().input("Enter password for user: %s" % username, option=xbmcgui.ALPHANUM_HIDE_INPUT)
            
        sha1 = hashlib.sha1(password)
        sha1 = sha1.hexdigest()    

        # Authenticate username and password
        url = "%s/mediabrowser/Users/AuthenticateByName?format=json" % server
        messageData = "username=%s&password=%s" % (username, sha1)

        resp = self.doUtils.downloadUrl(url, postBody=messageData, type="POST", authenticate=False)

        result = None
        accessToken = None
        try:
            self.logMsg("Auth_Reponse: %s" % resp, 1)
            result = json.loads(resp)
            accessToken = result.get("AccessToken")
        except:
            pass

        if (result != None and accessToken != None):
            self.currUser = username
            userId = result.get("User").get("Id")
            addon.setSetting("accessToken%s" % username, accessToken)
            addon.setSetting("userId%s" % username, userId)
            self.logMsg("User Authenticated: %s" % accessToken)
            self.loadCurrUser()
            self.WINDOW.setProperty("Server_status", "")
            self.retry = 0
            return
        else:
            self.logMsg("User authentication failed.")
            addon.setSetting("accessToken%s" % username, "")
            addon.setSetting("userId%s" % username, "")
            xbmcgui.Dialog().ok("Error Connecting", "Wrong password.")
            
            # Give two attempts at entering password
            self.retry += 1
            if self.retry == 2:
                self.logMsg("Too many retries. Please restart Kodi.")
                self.WINDOW.setProperty("Server_status", "Stop")
            
            self.auth = False
            return

    def resetClient(self):

        if self.currToken != None:
            # In case of 401, removed saved token
            self.addon.setSetting("accessToken%s" % self.currUser, "")
            self.WINDOW.setProperty("accessToken%s" % self.currUser, "")
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

            if (self.WINDOW.getProperty("Server_status") != ""):
                status = self.WINDOW.getProperty("Server_status")
                if status == "401":
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
                
            # Prevent sleep while the initial sync is going    
            if (self.WINDOW.getProperty("Server_sync") == ""):
                if self.KodiMonitor.waitForAbort(1):
                    # Abort was requested while waiting. We should exit
                    break
                
        self.logMsg("|---- UserClient Stopped ----|", 0)

    def stopClient(self):
        # As last resort
        self.stopClient = True