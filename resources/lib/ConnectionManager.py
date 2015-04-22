#################################################################################################
# connection manager class
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon

import json
import urllib
import sys
import socket
import threading
from datetime import datetime

import Utils as utils
from DownloadUtils import DownloadUtils
from UserClient import UserClient
from ClientInformation import ClientInformation


class ConnectionManager():

    clientInfo = ClientInformation()
    uc = UserClient()
    doUtils = DownloadUtils()

    addonName = clientInfo.getAddonName()
    addonId = clientInfo.getAddonId()
    addon = xbmcaddon.Addon(id=addonId)
    WINDOW = xbmcgui.Window(10000)

    logLevel = 0

    def __init__(self):

        self.className = self.__class__.__name__
        self.__language__ = self.addon.getLocalizedString
    
    def logMsg(self, msg, lvl=1):

        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))

    def checkServer(self):
        
        self.WINDOW.setProperty("Server_Checked", "True")
        self.logMsg("Connection Manager Called", 2)
        
        addon = self.addon
        server = self.uc.getServer()

        if (server != ""):
            self.logMsg("Server already set", 2)
            return
        
        serverInfo = self.getServerDetails()
        
        if (serverInfo == None):
            self.logMsg("getServerDetails failed", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return

        prefix,ip,port = serverInfo.split(":")
        setServer = xbmcgui.Dialog().yesno(self.__language__(30167), "Proceed with the following server?", self.__language__(30169) + serverInfo)
        
        if (setServer == 1):
            self.logMsg("Server selected. Saving information.", 1)
            addon.setSetting("ipaddress", ip.replace("/", ""))
            addon.setSetting("port", port)
            # If https is enabled
            if (prefix == 'https'):
                addon.setSetting('https', "true")
        else:
            self.logMsg("No server selected.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return

        # Get List of public users
        self.logMsg("Getting user list", 1)
        server = ip.replace("/", "") + ":" + port
        url = "%s/mediabrowser/Users/Public?format=json" % serverInfo

        try:
            result = self.doUtils.downloadUrl(url, authenticate=False)
        except Exception, msg:
            error = "Unable to connect to %s: %s" % (server, msg)
            self.logMsg(error, 1)
            return ""
        
        if (result == ""):
            return
    
        self.logMsg("jsonData: %s" % result, 2)

        names = []
        userList = []
        for user in result:
            name = user[u'Name']
            userList.append(name)

            if(user[u'HasPassword'] == True):
                name = name + " (Secure)"
            names.append(name)
    
        self.logMsg("User List: %s" % names, 1)
        self.logMsg("User List: %s" % userList, 2)
        return_value = xbmcgui.Dialog().select(self.__language__(30200), names)
        
        if (return_value > -1):
            selected_user = userList[return_value]
            self.logMsg("Selected User: %s" % selected_user, 1)      
            self.addon.setSetting("username", selected_user)
        else:
            self.logMsg("No user selected.", 1)
            xbmc.executebuiltin('Addon.OpenSettings(%s)' % self.addonId)
            return
            
        # Option to play from http
        setPlayback = xbmcgui.Dialog().yesno("Playback option", "Play your files using HTTP?")
        if setPlayback == 1:
            self.logMsg("Playback will be set using HTTP.", 1)
            addon.setSetting("playFromStream", "true")
        else:
            self.logMsg("Playback will be set using SMB.", 1)
                
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