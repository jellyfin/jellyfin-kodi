# -*- coding: utf-8 -*-

#################################################################################################

import json
import socket

import xbmc
import xbmcgui
import xbmcaddon

import clientinfo
import downloadutils
import userclient
from utils import Logging, settings, language as lang, passwordsXML

#################################################################################################


class InitialSetup():


    def __init__(self):

        global log
        log = Logging(self.__class__.__name__).log

        self.addonId = clientinfo.ClientInfo().getAddonId()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.userClient = userclient.UserClient()


    def setup(self):
        # Check server, user, direct paths, music, direct stream if not direct path.
        addonId = self.addonId
        dialog = xbmcgui.Dialog()

        ##### SERVER INFO #####
        
        log("Initial setup called.", 2)
        server = self.userClient.getServer()

        if server:
            log("Server is already set.", 2)
            return
        
        log("Looking for server...", 2)
        server = self.getServerDetails()
        log("Found: %s" % server, 2)
        try:
            prefix, ip, port = server.replace("/", "").split(":")
        except: # Failed to retrieve server information
            log("getServerDetails failed.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
            return
        else:
            server_confirm = dialog.yesno(
                                heading=lang(29999),
                                line1=lang(33034),
                                line2="%s %s" % (lang(30169), server))
            if server_confirm:
                # Correct server found
                log("Server is selected. Saving the information.", 1)
                settings('ipaddress', value=ip)
                settings('port', value=port)

                if prefix == "https":
                    settings('https', value="true")
            else:
                # User selected no or cancelled the dialog
                log("No server selected.", 1)
                xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
                return

        ##### USER INFO #####
        
        log("Getting user list.", 1)

        result = self.doUtils("%s/emby/Users/Public?format=json" % server, authenticate=False)
        if result == "":
            log("Unable to connect to %s" % server, 1)
            return

        log("Response: %s" % result, 2)
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

        log("Presenting user list: %s" % users_hasPassword, 1)
        user_select = dialog.select(lang(30200), users_hasPassword)
        if user_select > -1:
            selected_user = usernames[user_select]
            log("Selected user: %s" % selected_user, 1)
            settings('username', value=selected_user)
        else:
            log("No user selected.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)
            return

        ##### ADDITIONAL PROMPTS #####

        directPaths = dialog.yesno(
                            heading=lang(30511),
                            line1=lang(33035),
                            nolabel=lang(33036),
                            yeslabel=lang(33037))
        if directPaths:
            log("User opted to use direct paths.", 1)
            settings('useDirectPaths', value="1")

            # ask for credentials
            credentials = dialog.yesno(
                                heading=lang(30517),
                                line1= lang(33038))
            if credentials:
                log("Presenting network credentials dialog.", 1)
                passwordsXML()
        
        musicDisabled = dialog.yesno(
                            heading=lang(29999),
                            line1=lang(33039))
        if musicDisabled:
            log("User opted to disable Emby music library.", 1)
            settings('enableMusic', value="false")
        else:
            # Only prompt if the user didn't select direct paths for videos
            if not directPaths:
                musicAccess = dialog.yesno(
                                    heading=lang(29999),
                                    line1=lang(33040))
                if musicAccess:
                    log("User opted to direct stream music.", 1)
                    settings('streamMusic', value="true")
                
    def getServerDetails(self):

        log("Getting Server Details from Network", 1)
        
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = "who is EmbyServer?"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        
        log("MultiGroup      : %s" % str(MULTI_GROUP), 2)
        log("Sending UDP Data: %s" % MESSAGE, 2)
        sock.sendto(MESSAGE, MULTI_GROUP)
    
        try:
            data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
            log("Received Response: %s" % data)
        except:
            log("No UDP Response")
            return None
        else:
            # Get the address
            data = json.loads(data)
            return data['Address']