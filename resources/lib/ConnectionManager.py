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

from DownloadUtils import DownloadUtils
from UserClient import UserClient
from ClientInformation import ClientInformation


class ConnectionManager():

    clientInfo = ClientInformation()
    userClient = UserClient()
    doUtils = DownloadUtils()

    logLevel = 0
    addon = None
    WINDOW = xbmcgui.Window(10000)

    def __init__(self):

        clientInfo = self.clientInfo

        self.addonId = clientInfo.getAddonId()
        self.addonName = clientInfo.getAddonName()
        self.addon = xbmcaddon.Addon(id=self.addonId)
        self.__language__     = self.addon.getLocalizedString
    
    def logMsg(self, msg, level=1):
        
        addonName = self.addonName
        className = self.__class__.__name__
        s_logLevel = self.userClient.getLogLevel()

        # Attempt to change logLevel live
        if (self.logLevel != s_logLevel):
            self.logLevel = s_logLevel

        if (self.logLevel >= level):
            try:
                xbmc.log("%s %s -> %s" % (addonName, className, str(msg)))
            except UnicodeEncodeError:
                try:
                    xbmc.log("%s %s -> %s" % (addonName, className, str(msg.encode('utf-8'))))
                except:
                    pass

    def checkServer(self):
        
        self.WINDOW.setProperty("Server_Checked", "True")
        self.logMsg("Connection Manager Called")
        
        addon = self.addon
        server = self.userClient.getServer()

        if (server != ""):
            self.logMsg("Server already set", 2)
            return
        
        serverInfo = self.getServerDetails()
        prefix,ip,port = serverInfo.split(":")
        
        if (serverInfo == None):
            self.logMsg("getServerDetails failed", 1)
            return
        
        setServer = xbmcgui.Dialog().yesno(self.__language__(30167), "Proceed with the following server?", self.__language__(30169) + serverInfo)
        
        if setServer == 1:
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

        try:
            jsonData = self.doUtils.downloadUrl(serverInfo + "/mediabrowser/Users/Public?format=json", authenticate=False)
        except Exception, msg:
            error = "Get User unable to connect to " + server + " : " + str(msg)
            xbmc.log (error)
            return ""
        
        if (jsonData == False):
            return
    
        self.logMsg("jsonData : " + str(jsonData), level=2)
        result = json.loads(jsonData)
        
        names = []
        userList = []
        for user in result:
            name = user.get("Name")
            userList.append(name)
            if(user.get("HasPassword") == True):
                name = name + " (Secure)"
            names.append(name)
    
        self.logMsg("User List: " + str(names))
        self.logMsg("User List: " + str(userList))
        return_value = xbmcgui.Dialog().select(self.__language__(30200), names)
        
        if(return_value > -1):
            selected_user = userList[return_value]
            self.logMsg("Setting Selected User: %s" % selected_user)      
            self.addon.setSetting("username", selected_user)
            return
        else:
            xbmc.log("No user selected.")
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
        
        self.logMsg("MutliGroup      : %s" % str(MULTI_GROUP));
        self.logMsg("Sending UDP Data: %s" % MESSAGE);
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