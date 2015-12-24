# -*- coding: utf-8 -*-

#################################################################################################

from uuid import uuid4

import xbmc
import xbmcaddon

import utils

#################################################################################################


class ClientInfo():


    def __init__(self):

        self.addon = xbmcaddon.Addon()
        self.addonName = self.getAddonName()

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def getAddonName(self):
        # Used for logging
        return self.addon.getAddonInfo('name').upper()

    def getAddonId(self):

        return "plugin.video.emby"

    def getVersion(self):

        return self.addon.getAddonInfo('version')

    def getDeviceName(self):

        if utils.settings('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            deviceName = xbmc.getInfoLabel('System.FriendlyName')
        else:
            deviceName = utils.settings('deviceName')
            deviceName = deviceName.replace("\"", "_")
            deviceName = deviceName.replace("/", "_")

        return deviceName

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
        else:
            return "Unknown"

    def getDeviceId(self):

        clientId = utils.window('emby_deviceId')
        if clientId:
            return clientId

        addon_path = self.addon.getAddonInfo('path').decode('utf-8')
        GUID_file = xbmc.translatePath("%s\machine_guid" % addon_path).decode('utf-8')

        try:
            GUID = open(GUID_file)
        
        except IOError: # machine_guid does not exists.
            clientId = str("%012X" % uuid4())
            GUID = open(GUID_file, 'w')
            GUID.write(clientId)

        else: # machine_guid already exists. Get guid.
            clientId = GUID.read()
        
        finally:
            GUID.close()

        self.logMsg("DeviceId loaded: %s" % clientId, 1)
        utils.window('emby_deviceId', value=clientId)
        
        return clientId