# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import socket

import xbmc
import xbmcgui
import xbmcaddon

import clientinfo
import downloadutils
import userclient
from utils import settings, language as lang, passwordsXML

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class InitialSetup():


    def __init__(self):

        self.addonId = clientinfo.ClientInfo().getAddonId()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.userClient = userclient.UserClient()


    def setup(self):
        # Check server, user, direct paths, music, direct stream if not direct path.
        addonId = self.addonId
        dialog = xbmcgui.Dialog()

        ##### SERVER INFO #####
        
        log.debug("Initial setup called.")
        server = self.userClient.getServer()

        if server:
            log.debug("Server is already set.")
            return
        
        log.debug("Looking for server...")
        server = self.getServerDetails()
        log.debug("Found: %s" % server)
        try:
            prefix, ip, port = server.replace("/", "").split(":")
        except Exception: # Failed to retrieve server information
            log.error("getServerDetails failed.")
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
            return
        else:
            server_confirm = dialog.yesno(
                                heading=lang(29999),
                                line1=lang(33034),
                                line2="%s %s" % (lang(30169), server))
            if server_confirm:
                # Correct server found
                log.info("Server is selected. Saving the information.")
                settings('ipaddress', value=ip)
                settings('port', value=port)

                if prefix == "https":
                    settings('https', value="true")
            else:
                # User selected no or cancelled the dialog
                log.info("No server selected.")
                xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
                return

        ##### USER INFO #####
        
        log.info("Getting user list.")

        result = self.doUtils("%s/emby/Users/Public?format=json" % server, authenticate=False)
        if result == "":
            log.info("Unable to connect to %s" % server)
            return

        log.debug("Response: %s" % result)
        # Process the list of users
        usernames = []
        users_hasPassword = []

        for user in result:
            # Username
            name = user['Name']
            usernames.append(name)
            # Password
            if user['HasPassword']:
                name = "%s (secure)" % name
            users_hasPassword.append(name)

        log.info("Presenting user list: %s" % users_hasPassword)
        user_select = dialog.select(lang(30200), users_hasPassword)
        if user_select > -1:
            selected_user = usernames[user_select]
            log.info("Selected user: %s" % selected_user)
            settings('username', value=selected_user)
        else:
            log.info("No user selected.")
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
            return

        ##### ADDITIONAL PROMPTS #####

        directPaths = dialog.yesno(
                            heading=lang(30511),
                            line1=lang(33035),
                            nolabel=lang(33036),
                            yeslabel=lang(33037))
        if directPaths:
            log.info("User opted to use direct paths.")
            settings('useDirectPaths', value="1")

            # ask for credentials
            credentials = dialog.yesno(
                                heading=lang(30517),
                                line1= lang(33038))
            if credentials:
                log.info("Presenting network credentials dialog.")
                passwordsXML()
        
        musicDisabled = dialog.yesno(
                            heading=lang(29999),
                            line1=lang(33039))
        if musicDisabled:
            log.info("User opted to disable Emby music library.")
            settings('enableMusic', value="false")
        else:
            # Only prompt if the user didn't select direct paths for videos
            if not directPaths:
                musicAccess = dialog.yesno(
                                    heading=lang(29999),
                                    line1=lang(33040))
                if musicAccess:
                    log.info("User opted to direct stream music.")
                    settings('streamMusic', value="true")
                
    def getServerDetails(self):

        log.info("Getting Server Details from Network")
        
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = "who is EmbyServer?"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        
        log.debug("MultiGroup      : %s" % str(MULTI_GROUP))
        log.debug("Sending UDP Data: %s" % MESSAGE)
        sock.sendto(MESSAGE, MULTI_GROUP)
    
        try:
            data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
            log.info("Received Response: %s" % data)
        except Exception:
            log.error("No UDP Response")
            return None
        else:
            # Get the address
            data = json.loads(data)
            return data['Address']