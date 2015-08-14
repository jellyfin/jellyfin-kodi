# -*- coding: utf-8 -*-

#################################################################################################
# connection manager class
#################################################################################################

import json
import socket

import xbmc
import xbmcgui
import xbmcaddon

import Utils as utils
from ClientInformation import ClientInformation
from DownloadUtils import DownloadUtils
from UserClient import UserClient


class ConnectionManager():

    clientInfo = ClientInformation()
    user = UserClient()
    doUtils = DownloadUtils()

    addonName = clientInfo.getAddonName()
    addonId = clientInfo.getAddonId()
    addon = xbmcaddon.Addon()
    WINDOW = xbmcgui.Window(10000)

    def __init__(self):

        self.__language__ = self.addon.getLocalizedString
    
    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))

    def checkServer(self):
        
        self.WINDOW.setProperty("Server_Checked", "True")
        self.logMsg("Connection Manager Called", 2)
        
        server = self.user.getServer()

        if server != "":
            self.logMsg("Server already set", 2)
            return
        
        serverInfo = self.getServerDetails()
        
        try:
            prefix,ip,port = serverInfo.split(":")
            setServer = xbmcgui.Dialog().yesno(self.__language__(30167), "Proceed with the following server?", self.__language__(30169) + serverInfo)
        except: # serverInfo is None
            self.logMsg("getServerDetails failed", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return
        
        if setServer == 1:
            self.logMsg("Server selected. Saving information.", 1)
            utils.settings("ipaddress", ip.replace("/", ""))
            utils.settings("port", port)
            # If https, enable the setting
            if (prefix == 'https'):
                utils.settings('https', "true")
        else:
            self.logMsg("No server selected.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return

        # Get List of public users
        self.logMsg("Getting user list", 1)
        server = "%s:%s" % (ip.replace("/", ""), port)
        url = "%s/mediabrowser/Users/Public?format=json" % serverInfo

        result = self.doUtils.downloadUrl(url, authenticate=False)
        if result == "":
            self.logMsg("Unable to connect to %s." % server, 1)
            return

        self.logMsg("Result: %s" % result, 2)

        # Process the list returned
        names = []
        userList = []
        for user in result:
            name = user['Name']
            userList.append(name)

            if user['HasPassword']:
                name = "%s (Secure)" % name
            names.append(name)

        self.logMsg("User list: %s" % names, 1)
        resp = xbmcgui.Dialog().select(self.__language__(30200), names)
        if resp > -1:
            selected_user = userList[resp]
            self.logMsg("Selected User: %s" % selected_user, 1)      
            utils.settings("username", selected_user)
        else:
            self.logMsg("No user selected.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return
                
    def getServerDetails(self):

        self.logMsg("Getting Server Details from Network")
        
        MULTI_GROUP = ("<broadcast>", 7359)
        MESSAGE = "who is EmbyServer?"
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(6.0)

        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 20)
        
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.SO_REUSEADDR, 1)
        
        self.logMsg("MutliGroup      : %s" % str(MULTI_GROUP), 2);
        self.logMsg("Sending UDP Data: %s" % MESSAGE, 2);
        sock.sendto(MESSAGE, MULTI_GROUP)
    
        try:
            data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
            self.logMsg("Received Response: %s" % data)
            # Get the address
            data = json.loads(data)
            return data['Address']
        except:
            self.logMsg("No UDP Response")
            pass
        
        return None