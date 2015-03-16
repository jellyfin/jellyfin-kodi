#######################################################################
#       CLIENTINFORMATION: centralized client data
#       -------------------------------
#       addonId, addonName, addon version, clientId, platform       
#######################################################################
#       USER: centralized Userdata
#       -------------------------------
#       username, userId, token, server, http prefix, LogLevel
#######################################################################

import xbmc
import xbmcaddon
import xbmcgui
import os
from uuid import uuid4 as uuid4
from Lock import Lock

class ClientInformation():

    def __init__(self):
        addonId = self.getAddonId()
        self.addon = xbmcaddon.Addon(id=addonId)
        self.WINDOW = xbmcgui.Window( 10000 )

        level = User().getLogLevel()     
        self.logLevel = 0
        
        if (level != None and level != ""):
            self.logLevel = int(level)
        
        if (self.logLevel == 2):
            self.LogCalls = True

    def logMsg(self, msg, level = 1):

        addonName = self.getAddonName()
        className = self.__class__.__name__
        
        if (self.logLevel >= level):
            try:
                xbmc.log("%s %s -> %s" % (addonName, className, str(msg)))
            except UnicodeEncodeError:
                try:
                    xbmc.log("%s %s -> %s" % (addonName, className, str(msg)))
                except: pass
    
    def getAddonId(self):
        # To use when declaring xbmcaddon.Addon(id=addonId)
        addonId = "plugin.video.mb3sync"
        return addonId

    def getAddonName(self):
        # Useful for logging
        addonName = self.addon.getAddonInfo('name').upper()
        return addonName
    
    def getVersion(self):
        
        version = self.addon.getAddonInfo('version')
        return version
    
    def getMachineId(self):
    
        WINDOW = self.WINDOW
        
        clientId = WINDOW.getProperty("client_id")
        if(clientId != None and clientId != ""):
            return clientId
            
        # we need to load and or generate a client machine id    
        __addon__ = self.addon
        __addondir__ = xbmc.translatePath( __addon__.getAddonInfo('path'))
        machine_guid_lock_path = os.path.join(__addondir__, "machine_guid.lock")
        machine_guid_path = os.path.join(__addondir__, "machine_guid")
        clientId = ""
        
        try:
            lock = Lock(machine_guid_lock_path)
            locked = lock.acquire()
            
            if(locked == True):
            
                fd = os.open(machine_guid_path, os.O_CREAT|os.O_RDWR)
                clientId = os.read(fd, 256)
                
                if(len(clientId) == 0):
                    uuid = uuid4()
                    clientId = str("%012X" % uuid)
                    self.logMsg("ClientId saved to FILE : %s" % clientId)                    
                    os.write(fd, clientId)
                    os.fsync(fd)
                    
                os.close(fd)
                
                self.logMsg("ClientId saved to WINDOW : %s" % clientId)
                WINDOW.setProperty("client_id", clientId)
                 
        finally: 
            lock.release()
                
        return clientId
        
    def getPlatform(self):

        if xbmc.getCondVisibility('system.platform.osx'):
            return "OSX"
        elif xbmc.getCondVisibility('system.platform.atv2'):
            return "ATV2"
        elif xbmc.getCondVisibility('system.platform.ios'):
            return "iOS"
        elif xbmc.getCondVisibility('system.platform.windows'):
            return "Windows"
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux/RPi"
        elif xbmc.getCondVisibility('system.platform.android'): 
            return "Linux/Android"

        return "Unknown"


class User(ClientInformation):
    
    def __init__(self):
        addonId = self.getAddonId()
        self.addon = xbmcaddon.Addon(id=addonId)
        self.WINDOW = xbmcgui.Window( 10000 )

        level = self.getLogLevel()     
        self.logLevel = 0
        
        if (level != None and level != ""):
            self.logLevel = int(level)
        
        if (self.logLevel == 2):
            self.LogCalls = True

    def logMsg(self, msg, level = 1):

        addonName = self.getAddonName()
        className = self.__class__.__name__
        
        if (self.logLevel >= level):
            try:
                xbmc.log("%s %s -> %s" % (addonName, className, str(msg)))
            except UnicodeEncodeError:
                try:
                    xbmc.log("%s %s -> %s" % (addonName, className, str(msg)))
                except: pass
    
    def getUsername(self):
        
        username = self.addon.getSetting('username')
        return username
    
    def getUserId(self):
        
        username = self.getUsername()
        w_userId = self.WINDOW.getProperty('userId%s' % username)
        s_userId = self.addon.getSetting('userId%s' % username)

        # Verify if userId is saved to Window
        if (w_userId != ""):
            self.logMsg("Returning saved (WINDOW) UserId for user: %s UserId: %s" % (username, w_userId))
            return w_userId
        # Verify if userId is saved in settings
        elif (s_userId != ""):
            self.logMsg("Returning saved (SETTINGS) UserId for user: %s UserId: %s" % (username, s_userId))
            self.WINDOW.setProperty('userId%s' % username, s_userId)
            return s_userId
        else:
            return ""
    
    def getToken(self):
        
        username = self.getUsername()
        w_token = self.WINDOW.getProperty('AccessToken%s' % username)
        s_token = self.addon.getSetting('AccessToken%s' % username)
        
        # Verify if token is saved to Window
        if (w_token != ""):
            self.logMsg("Returning saved (WINDOW) AccessToken for user: %s Token: %s" % (username, w_token))
            return w_token
        # Verify if token is saved in settings
        elif (s_token != ""):
            self.logMsg("Returning saved (SETTINGS) AccessToken for user: %s Token: %s" % (username, s_token))
            self.WINDOW.setProperty('AccessToken%s' % username, s_token)
            return s_token
        else:
            self.logMsg("User is not authenticated.")
            return ""
    
    def getServer(self):
        
        host = self.addon.getSetting('ipaddress')
        port = self.addon.getSetting('port')
        return host + ":" + port

    def getHTTPprefix(self):
        # For https support
        prefix = self.addon.getSetting('prefix')
        if prefix:
            return "https://" 
        else:
            return "http://"
    
    def getLogLevel(self):
        
        level = self.addon.getSetting('logLevel')
        return level
