# -*- coding: utf-8 -*-

##################################################################################################

import hashlib
import threading

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import artwork
import utils
import clientinfo
import downloadutils

##################################################################################################


class UserClient(threading.Thread):

    # Borg - multiple instances, shared state
    _shared_state = {}

    stopClient = False
    auth = True
    retry = 0

    currUser = None
    currUserId = None
    currServer = None
    currToken = None
    HasAccess = True
    AdditionalUser = []

    userSettings = None


    def __init__(self):

        self.__dict__ = self._shared_state
        self.addon = xbmcaddon.Addon()

        self.addonName = clientinfo.ClientInfo().getAddonName()
        self.doUtils = downloadutils.DownloadUtils()

        threading.Thread.__init__(self)

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def getAdditionalUsers(self):

        additionalUsers = utils.settings('additionalUsers')

        if additionalUsers:
            self.AdditionalUser = additionalUsers.split(',')

    def getUsername(self):

        username = utils.settings('username')

        if not username:
            self.logMsg("No username saved.", 2)
            return ""

        return username

    def getLogLevel(self):

        try:
            logLevel = int(utils.settings('logLevel'))
        except ValueError:
            logLevel = 0

        return logLevel

    def getUserId(self):

        window = utils.window
        settings = utils.settings

        username = self.getUsername()
        w_userId = window('emby_currUser')
        s_userId = settings('userId%s' % username)

        # Verify the window property
        if w_userId:
            if not s_userId:
                # Save access token if it's missing from settings
                settings('userId%s' % username, value=w_userId)
            self.logMsg("Returning userId from WINDOW for username: %s UserId: %s"
                % (username, w_userId), 2)
            return w_userId
        # Verify the settings
        elif s_userId:
            self.logMsg("Returning userId from SETTINGS for username: %s userId: %s"
                % (username, s_userId), 2)
            return s_userId
        # No userId found
        else:
            self.logMsg("No userId saved for username: %s." % username, 1)

    def getServer(self, prefix=True):

        settings = utils.settings

        alternate = settings('altip') == "true"
        if alternate:
            # Alternate host
            HTTPS = settings('secondhttps') == "true"
            host = settings('secondipaddress')
            port = settings('secondport')
        else:
            # Original host
            HTTPS = settings('https') == "true"
            host = settings('ipaddress')
            port = settings('port')

        server = host + ":" + port

        if not host:
            self.logMsg("No server information saved.", 2)
            return False

        # If https is true
        if prefix and HTTPS:
            server = "https://%s" % server
            return server
        # If https is false
        elif prefix and not HTTPS:
            server = "http://%s" % server
            return server
        # If only the host:port is required
        elif not prefix:
            return server

    def getToken(self):

        window = utils.window
        settings = utils.settings

        username = self.getUsername()
        userId = self.getUserId()
        w_token = window('emby_accessToken%s' % userId)
        s_token = settings('accessToken')

        # Verify the window property
        if w_token:
            if not s_token:
                # Save access token if it's missing from settings
                settings('accessToken', value=w_token)
            self.logMsg("Returning accessToken from WINDOW for username: %s accessToken: %s"
                % (username, w_token), 2)
            return w_token
        # Verify the settings
        elif s_token:
            self.logMsg("Returning accessToken from SETTINGS for username: %s accessToken: %s"
                % (username, s_token), 2)
            window('emby_accessToken%s' % username, value=s_token)
            return s_token
        else:
            self.logMsg("No token found.", 1)
            return ""

    def getSSLverify(self):
        # Verify host certificate
        settings = utils.settings

        s_sslverify = settings('sslverify')
        if settings('altip') == "true":
            s_sslverify = settings('secondsslverify')

        if s_sslverify == "true":
            return True
        else:
            return False

    def getSSL(self):
        # Client side certificate
        settings = utils.settings

        s_cert = settings('sslcert')
        if settings('altip') == "true":
            s_cert = settings('secondsslcert')

        if s_cert == "None":
            return None
        else:
            return s_cert

    def setUserPref(self):

        doUtils = self.doUtils.downloadUrl

        result = doUtils("{server}/emby/Users/{UserId}?format=json")
        self.userSettings = result
        # Set user image for skin display
        if result.get('PrimaryImageTag'):
            utils.window('EmbyUserImage', value=artwork.Artwork().getUserArtwork(result['Id'], 'Primary'))

        # Set resume point max
        result = doUtils("{server}/emby/System/Configuration?format=json")

        utils.settings('markPlayed', value=str(result['MaxResumePct']))

    def getPublicUsers(self):
        # Get public Users
        result = self.doUtils.downloadUrl("%s/emby/Users/Public?format=json" % self.getServer(), authenticate=False)
        if result != "":
            return result
        else:
            # Server connection failed
            return False


    def hasAccess(self):
        # hasAccess is verified in service.py
        window = utils.window

        result = self.doUtils.downloadUrl("{server}/emby/Users?format=json")

        if result == False:
            # Access is restricted, set in downloadutils.py via exception
            self.logMsg("Access is restricted.", 1)
            self.HasAccess = False

        elif window('emby_online') != "true":
            # Server connection failed
            pass

        elif window('emby_serverStatus') == "restricted":
            self.logMsg("Access is granted.", 1)
            self.HasAccess = True
            window('emby_serverStatus', clear=True)
            xbmcgui.Dialog().notification("Emby for Kodi", utils.language(33007))

    def loadCurrUser(self, authenticated=False):

        window = utils.window

        doUtils = self.doUtils
        username = self.getUsername()
        userId = self.getUserId()

        # Only to be used if token exists
        self.currUserId = userId
        self.currServer = self.getServer()
        self.currToken = self.getToken()
        self.ssl = self.getSSLverify()
        self.sslcert = self.getSSL()

        # Test the validity of current token
        if authenticated == False:
            url = "%s/emby/Users/%s?format=json" % (self.currServer, userId)
            window('emby_currUser', value=userId)
            window('emby_accessToken%s' % userId, value=self.currToken)
            result = doUtils.downloadUrl(url)

            if result == 401:
                # Token is no longer valid
                self.resetClient()
                return False

        # Set to windows property
        window('emby_currUser', value=userId)
        window('emby_accessToken%s' % userId, value=self.currToken)
        window('emby_server%s' % userId, value=self.currServer)
        window('emby_server_%s' % userId, value=self.getServer(prefix=False))

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
        self.getAdditionalUsers()
        # Set user preferences in settings
        self.currUser = username
        self.setUserPref()


    def authenticate(self):

        lang = utils.language
        window = utils.window
        settings = utils.settings
        dialog = xbmcgui.Dialog()

        # Get /profile/addon_data
        addondir = xbmc.translatePath(self.addon.getAddonInfo('profile')).decode('utf-8')
        hasSettings = xbmcvfs.exists("%ssettings.xml" % addondir)

        username = self.getUsername()
        server = self.getServer()

        # If there's no settings.xml
        if not hasSettings:
            self.logMsg("No settings.xml found.", 1)
            self.auth = False
            return
        # If no user information
        elif not server or not username:
            self.logMsg("Missing server information.", 1)
            self.auth = False
            return
        # If there's a token, load the user
        elif self.getToken():
            result = self.loadCurrUser()

            if result is False:
                pass
            else:
                self.logMsg("Current user: %s" % self.currUser, 1)
                self.logMsg("Current userId: %s" % self.currUserId, 1)
                self.logMsg("Current accessToken: %s" % self.currToken, 2)
                return

        ##### AUTHENTICATE USER #####

        users = self.getPublicUsers()
        password = ""

        # Find user in list
        for user in users:
            name = user['Name']

            if username.decode('utf-8') in name:
                # If user has password
                if user['HasPassword'] == True:
                    password = dialog.input(
                        heading="%s %s" % (lang(33008), username.decode('utf-8')),
                        option=xbmcgui.ALPHANUM_HIDE_INPUT)
                    # If password dialog is cancelled
                    if not password:
                        self.logMsg("No password entered.", 0)
                        window('emby_serverStatus', value="Stop")
                        self.auth = False
                        return
                break
        else:
            # Manual login, user is hidden
            password = dialog.input(
                            heading="%s %s" % (lang(33008), username),
                            option=xbmcgui.ALPHANUM_HIDE_INPUT)
        sha1 = hashlib.sha1(password)
        sha1 = sha1.hexdigest()

        # Authenticate username and password
        data = {'username': username, 'password': sha1}
        self.logMsg(data, 2)

        result = self.doUtils.downloadUrl("%s/emby/Users/AuthenticateByName?format=json" % server, postBody=data, action_type="POST", authenticate=False)

        try:
            self.logMsg("Auth response: %s" % result, 1)
            accessToken = result['AccessToken']

        except (KeyError, TypeError):
            self.logMsg("Failed to retrieve the api key.", 1)
            accessToken = None

        if accessToken is not None:
            self.currUser = username
            dialog.notification("Emby for Kodi",
                                "%s %s!" % (lang(33000), self.currUser.decode('utf-8')))
            settings('accessToken', value=accessToken)
            settings('userId%s' % username, value=result['User']['Id'])
            self.logMsg("User Authenticated: %s" % accessToken, 1)
            self.loadCurrUser(authenticated=True)
            window('emby_serverStatus', clear=True)
            self.retry = 0
        else:
            self.logMsg("User authentication failed.", 1)
            settings('accessToken', value="")
            settings('userId%s' % username, value="")
            dialog.ok(lang(33001), lang(33009))

            # Give two attempts at entering password
            if self.retry == 2:
                self.logMsg("Too many retries. "
                    "You can retry by resetting attempts in the addon settings.", 1)
                window('emby_serverStatus', value="Stop")
                dialog.ok(lang(33001), lang(33010))

            self.retry += 1
            self.auth = False

    def resetClient(self):

        self.logMsg("Reset UserClient authentication.", 1)
        if self.currToken is not None:
            # In case of 401, removed saved token
            utils.settings('accessToken', value="")
            utils.window('emby_accessToken%s' % self.getUserId(), clear=True)
            self.currToken = None
            self.logMsg("User token has been removed.", 1)

        self.auth = True
        self.currUser = None

    def run(self):

        window = utils.window

        monitor = xbmc.Monitor()
        self.logMsg("----===## Starting UserClient ##===----", 0)

        while not monitor.abortRequested():

            status = window('emby_serverStatus')
            if status:
                # Verify the connection status to server
                if status == "restricted":
                    # Parental control is restricting access
                    self.HasAccess = False

                elif status == "401":
                    # Unauthorized access, revoke token
                    window('emby_serverStatus', value="Auth")
                    self.resetClient()

            if self.auth and (self.currUser is None):
                # Try to authenticate user
                status = window('emby_serverStatus')
                if not status or status == "Auth":
                    # Set auth flag because we no longer need
                    # to authenticate the user
                    self.auth = False
                    self.authenticate()


            if not self.auth and (self.currUser is None):
                # If authenticate failed.
                server = self.getServer()
                username = self.getUsername()
                status = window('emby_serverStatus')

                # The status Stop is for when user cancelled password dialog.
                if server and username and status != "Stop":
                    # Only if there's information found to login
                    self.logMsg("Server found: %s" % server, 2)
                    self.logMsg("Username found: %s" % username, 2)
                    self.auth = True


            if self.stopClient == True:
                # If stopping the client didn't work
                break

            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        self.doUtils.stopSession()
        self.logMsg("##===---- UserClient Stopped ----===##", 0)

    def stopClient(self):
        # When emby for kodi terminates
        self.stopClient = True