import xbmc
import xbmcaddon
import xbmcgui

import os
from uuid import uuid4 as uuid4
from Lock import Lock

import Utils as utils


class ClientInformation():
    

    def __init__(self):
        addonId = self.getAddonId()
        self.addon = xbmcaddon.Addon(id=addonId)

        self.className = self.__class__.__name__
        self.addonName = self.getAddonName()

    def logMsg(self, msg, lvl=1):

        utils.logMsg("%s %s" % (self.addonName, self.className), str(msg), int(lvl))
    
    def getAddonId(self):
        # To use when declaring xbmcaddon.Addon(id=addonId)
        return "plugin.video.emby"

    def getAddonName(self):
        # Useful for logging
        return self.addon.getAddonInfo('name').upper()
    
    def getVersion(self):

        return self.addon.getAddonInfo('version')

    def getDeviceName(self):

        deviceName = self.addon.getSetting('deviceName')
        deviceName = deviceName.replace("\"", "_")
        deviceName = deviceName.replace("/", "_")

        return deviceName
    
    def getMachineId(self):
    
        WINDOW = xbmcgui.Window(10000)
        
        clientId = WINDOW.getProperty("client_id")
        if (clientId != None and clientId != ""):
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
            
            if (locked == True):
            
                fd = os.open(machine_guid_path, os.O_CREAT|os.O_RDWR)
                clientId = os.read(fd, 256)
                
                if (len(clientId) == 0):
                    uuid = uuid4()
                    clientId = str("%012X" % uuid)
                    self.logMsg("ClientId saved to FILE: %s" % clientId, 2)                    
                    os.write(fd, clientId)
                    os.fsync(fd)
                    
                os.close(fd)
                
                self.logMsg("ClientId saved to WINDOW: %s" % clientId, 1)
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
