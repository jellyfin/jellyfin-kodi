################################################################
#       CLIENTINFORMATION: centralized client data
#       -------------------------------
#       addonId, addon version, clientId, platform
################################################################
#       USER: centralized Userdata
#       -------------------------------
#       username, userId, token, server, Loglvl
################################################################

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
    
    def getAddonId(self):
        # To use when declaring xbmcaddon.Addon(id=addonId)
        addonId = "plugin.video.mb3sync"
        return addonId
    
    def getVersion(self):
        
        version = self.addon.getAddonInfo('version')
        return version
    
    def getMachineId(self):
    
        WINDOW = xbmcgui.Window( 10000 )
        
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
                    xbmc.log("CLIENT_ID - > Client ID saved to FILE : " + clientId)                    
                    os.write(fd, clientId)
                    os.fsync(fd)
                    
                os.close(fd)
                
                xbmc.log("CLIENT_ID - > Client ID saved to WINDOW : " + clientId)
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
    
    def getUsername(self):
        
        username = self.addon.getSetting('username')
        return username
    
    def getUserId(self):
        
        userId = self.addon.getSetting('userId')
        return userId
    
    def getToken(self):
        
        token = self.addon.getSetting('token')
        return token
    
    def getServer(self):
        
        host = self.addon.getSetting('ipaddress')
        port = self.addon.getSetting('port')
        return host + ":" + port
    
    def getLoglvl(self):
        
        level = self.addon.getSetting('loglevel')
        return level
