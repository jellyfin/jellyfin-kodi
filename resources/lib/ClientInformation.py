# -*- coding: utf-8 -*-

import os
from uuid import uuid4 as uuid4
from Lock import Lock

import xbmc
import xbmcaddon
import xbmcgui

import Utils as utils


class ClientInformation():

    def __init__(self):

        self.addon = xbmcaddon.Addon()
        self.addonName = self.getAddonName()

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))
    
    def getAddonId(self):
        # To use when declaring xbmcaddon.Addon(id=addonId)
        return "plugin.video.emby"

    def getAddonName(self):
        # Useful for logging
        return self.addon.getAddonInfo('name').upper()
    
    def getVersion(self):

        return self.addon.getAddonInfo('version')

    def getDeviceName(self):

        addon = self.addon

        if addon.getSetting('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            deviceName = xbmc.getInfoLabel('System.FriendlyName')
        else:
            deviceName = addon.getSetting('deviceName')
            deviceName = deviceName.replace("\"", "_")
            deviceName = deviceName.replace("/", "_")

        return deviceName
    
    def getMachineId(self):
    
        WINDOW = xbmcgui.Window(10000)
        
        clientId = WINDOW.getProperty("client_id")
        if clientId:
            return clientId
            
        # we need to load and or generate a client machine id    
        addon = self.addon
        addondir = addon.getAddonInfo('path').decode('utf-8')
        machine_guid_lock_path = xbmc.translatePath(os.path.join(addondir, "machine_guid.lock")).decode('utf-8')
        machine_guid_path = xbmc.translatePath(os.path.join(addondir, "machine_guid")).decode('utf-8')
        clientId = ""
        
        try:
            lock = Lock(machine_guid_lock_path)
            locked = lock.acquire()
            
            if locked:
            
                fd = os.open(machine_guid_path, os.O_CREAT|os.O_RDWR)
                clientId = os.read(fd, 256)
                
                if len(clientId) == 0:
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