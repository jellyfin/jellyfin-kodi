# -*- coding: utf-8 -*-

##################################################################################################

import hashlib
import logging
import threading

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

import artwork
import clientinfo
import downloadutils
from utils import window, settings, language as lang

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class UserClient(threading.Thread):

    # Borg - multiple instances, shared state
    _shared_state = {}

    stop_thread = False
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

        self.doUtils = downloadutils.DownloadUtils()

        threading.Thread.__init__(self)


    def getAdditionalUsers(self):

        additionalUsers = settings('additionalUsers')

        if additionalUsers:
            self.AdditionalUser = additionalUsers.split(',')

    def getUsername(self):

        username = settings('username')

        if not username:
            log.debug("No username saved.")
            return ""

        return username

    def getLogLevel(self):

        try:
            logLevel = int(settings('logLevel'))
        except ValueError:
            logLevel = 0

        return logLevel

    def getUserId(self):

        username = self.getUsername()
        w_userId = window('emby_currUser')
        s_userId = settings('userId%s' % username)

        # Verify the window property
        if w_userId:
            if not s_userId:
                # Save access token if it's missing from settings
                settings('userId%s' % username, value=w_userId)
            log.debug("Returning userId from WINDOW for username: %s UserId: %s"
                % (username, w_userId))
            return w_userId
        # Verify the settings
        elif s_userId:
            log.debug("Returning userId from SETTINGS for username: %s userId: %s"
                % (username, s_userId))
            return s_userId
        # No userId found
        else:
            log.info("No userId saved for username: %s." % username)

    def getServer(self, prefix=True):

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
            log.debug("No server information saved.")
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

        username = self.getUsername()
        userId = self.getUserId()
        w_token = window('emby_accessToken%s' % userId)
        s_token = settings('accessToken')

        # Verify the window property
        if w_token:
            if not s_token:
                # Save access token if it's missing from settings
                settings('accessToken', value=w_token)
                log.debug("Returning accessToken from WINDOW for username: %s accessToken: %s"
                % (username, w_token))
            return w_token
        # Verify the settings
        elif s_token:
            log.debug("Returning accessToken from SETTINGS for username: %s accessToken: %s"
                % (username, s_token))
            window('emby_accessToken%s' % username, value=s_token)
            return s_token
        else:
            log.info("No token found.")
            return ""

    def getSSLverify(self):
        # Verify host certificate
        s_sslverify = settings('sslverify')
        if settings('altip') == "true":
            s_sslverify = settings('secondsslverify')

        if s_sslverify == "true":
            return True
        else:
            return False

    def getSSL(self):
        # Client side certificate
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
            window('EmbyUserImage', value=artwork.Artwork().getUserArtwork(result['Id'], 'Primary'))

        # Set resume point max
        result = doUtils("{server}/emby/System/Configuration?format=json")
        settings('markPlayed', value=str(result['MaxResumePct']))

    def getPublicUsers(self):
        # Get public Users
        url = "%s/emby/Users/Public?format=json" % self.getServer()
        result = self.doUtils.downloadUrl(url, authenticate=False)
        if result != "":
            return result
        else:
            # Server connection failed
            return False


    def hasAccess(self):
        # hasAccess is verified in service.py
        result = self.doUtils.downloadUrl("{server}/emby/Users?format=json")

        if result == False:
            # Access is restricted, set in downloadutils.py via exception
            log.info("Access is restricted.")
            self.HasAccess = False

        elif window('emby_online') != "true":
            # Server connection failed
            pass

        elif window('emby_serverStatus') == "restricted":
            log.info("Access is granted.")
            self.HasAccess = True
            window('emby_serverStatus', clear=True)
            xbmcgui.Dialog().notification(lang(29999), lang(33007))

    def loadCurrUser(self, authenticated=False):

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

        dialog = xbmcgui.Dialog()

        # Get /profile/addon_data
        addondir = xbmc.translatePath(self.addon.getAddonInfo('profile')).decode('utf-8')
        hasSettings = xbmcvfs.exists("%ssettings.xml" % addondir)

        username = self.getUsername()
        server = self.getServer()

        # If there's no settings.xml
        if not hasSettings:
            log.info("No settings.xml found.")
            self.auth = False
            return
        # If no user information
        elif not server or not username:
            log.info("Missing server information.")
            self.auth = False
            return
        # If there's a token, load the user
        elif self.getToken():
            result = self.loadCurrUser()

            if result == False:
                pass
            else:
                log.info("Current user: %s" % self.currUser)
                log.info("Current userId: %s" % self.currUserId)
                log.debug("Current accessToken: %s" % self.currToken)
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
                        log.warn("No password entered.")
                        window('emby_serverStatus', value="Stop")
                        self.auth = False
                        return
                break
        else:
            # Manual login, user is hidden
            password = dialog.input(
                            heading="%s %s" % (lang(33008), username.decode('utf-8')),
                            option=xbmcgui.ALPHANUM_HIDE_INPUT)
        sha1 = hashlib.sha1(password)
        sha1 = sha1.hexdigest()

        # Authenticate username and password
        data = {'username': username, 'password': sha1}
        log.debug(data)

        url = "%s/emby/Users/AuthenticateByName?format=json" % server
        result = self.doUtils.downloadUrl(url, postBody=data, action_type="POST", authenticate=False)

        try:
            log.info("Auth response: %s" % result)
            accessToken = result['AccessToken']

        except (KeyError, TypeError):
            log.info("Failed to retrieve the api key.")
            accessToken = None

        if accessToken is not None:
            self.currUser = username
            dialog.notification(lang(29999),
                                "%s %s!" % (lang(33000), self.currUser.decode('utf-8')))
            settings('accessToken', value=accessToken)
            settings('userId%s' % username, value=result['User']['Id'])
            log.info("User Authenticated: %s" % accessToken)
            self.loadCurrUser(authenticated=True)
            window('emby_serverStatus', clear=True)
            self.retry = 0
        else:
            log.error("User authentication failed.")
            settings('accessToken', value="")
            settings('userId%s' % username, value="")
            dialog.ok(lang(33001), lang(33009))

            # Give two attempts at entering password
            if self.retry == 2:
                log.info("Too many retries. "
                    "You can retry by resetting attempts in the addon settings.")
                window('emby_serverStatus', value="Stop")
                dialog.ok(lang(33001), lang(33010))

            self.retry += 1
            self.auth = False

    def resetClient(self):

        log.info("Reset UserClient authentication.")
        if self.currToken is not None:
            # In case of 401, removed saved token
            settings('accessToken', value="")
            window('emby_accessToken%s' % self.getUserId(), clear=True)
            self.currToken = None
            log.info("User token has been removed.")

        self.auth = True
        self.currUser = None

    def run(self):

        monitor = xbmc.Monitor()
        log.warn("----===## Starting UserClient ##===----")

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
                    log.debug("Server found: %s" % server)
                    log.debug("Username found: %s" % username)
                    self.auth = True


            if self.stop_thread == True:
                # If stopping the client didn't work
                break

            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break

        self.doUtils.stopSession()
        log.warn("##===---- UserClient Stopped ----===##")

    def stopClient(self):
        # When emby for kodi terminates
        self.stop_thread = True