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

        self.clientInfo = clientinfo.ClientInfo()
        self.addonId = self.clientInfo.getAddonId()
        self.doUtils = downloadutils.DownloadUtils()
        self.userClient = userclient.UserClient()


    def setup(self):
        # Check server, user, direct paths, music, direct stream if not direct path.
        addonId = self.addonId

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
            server_confirm = xbmcgui.Dialog().yesno(
                                            heading="Emby for Kodi",
                                            line1="Proceed with the following server?",
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
        
        url = "%s/emby/Users/Public?format=json" % server
        result = self.doUtils.downloadUrl(url, authenticate=False)
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
        user_select = xbmcgui.Dialog().select(lang(30200), users_hasPassword)
        if user_select > -1:
            selected_user = usernames[user_select]
            log("Selected user: %s" % selected_user, 1)
            settings('username', value=selected_user)
        else:
            log("No user selected.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % addonId)

        ##### ADDITIONAL PROMPTS #####
        dialog = xbmcgui.Dialog()

        directPaths = dialog.yesno(
                            heading="Playback Mode",
                            line1=(
                                "Caution! If you choose Native mode, you "
                                "will lose access to certain Emby features such as: "
                                "Emby cinema mode, direct stream/transcode options, "
                                "parental access schedule."),
                            nolabel="Addon (Default)",
                            yeslabel="Native (Direct Paths)")
        if directPaths:
            log("User opted to use direct paths.", 1)
            settings('useDirectPaths', value="1")

            # ask for credentials
            credentials = dialog.yesno(
                                heading="Network credentials",
                                line1= (
                                    "Add network credentials to allow Kodi access to your "
                                    "content? Note: Skipping this step may generate a message "
                                    "during the initial scan of your content if Kodi can't "
                                    "locate your content."))
            if credentials:
                log("Presenting network credentials dialog.", 1)
                passwordsXML()
        
        musicDisabled = dialog.yesno(
                            heading="Music Library",
                            line1="Disable Emby music library?")
        if musicDisabled:
            log("User opted to disable Emby music library.", 1)
            settings('enableMusic', value="false")
        else:
            # Only prompt if the user didn't select direct paths for videos
            if not directPaths:
                musicAccess = dialog.yesno(
                                    heading="Music Library",
                                    line1=(
                                        "Direct stream the music library? Select "
                                        "this option only if you plan on listening "
                                        "to music outside of your network."))
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