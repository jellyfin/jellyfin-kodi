# -*- coding: utf-8 -*-

#################################################################################################

import os
from uuid import uuid4

import xbmc
import xbmcaddon
import xbmcvfs

from utils import Logging, window, settings

#################################################################################################


class ClientInfo():


    def __init__(self):

        global log
        log = Logging(self.__class__.__name__).log

        self.addon = xbmcaddon.Addon()
        self.addonName = self.getAddonName()


    def getAddonName(self):
        # Used for logging
        return self.addon.getAddonInfo('name').upper()

    def getAddonId(self):

        return "plugin.video.emby"

    def getVersion(self):

        return self.addon.getAddonInfo('version')

    def getDeviceName(self):

        if settings('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            deviceName = xbmc.getInfoLabel('System.FriendlyName').decode('utf-8')
        else:
            deviceName = settings('deviceName')
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

    def getDeviceId(self, reset=False):

        clientId = window('emby_deviceId')
        if clientId:
            return clientId

        addon_path = self.addon.getAddonInfo('path').decode('utf-8')
        if os.path.supports_unicode_filenames:
            path = os.path.join(addon_path, "machine_guid")
        else:
            path = os.path.join(addon_path.encode('utf-8'), "machine_guid")
        
        GUID_file = xbmc.translatePath(path).decode('utf-8')
        
        if reset and xbmcvfs.exists(GUID_file):
            # Reset the file
            xbmcvfs.delete(GUID_file)

        GUID = xbmcvfs.File(GUID_file)
        clientId = GUID.read()
        if not clientId:
            log("Generating a new deviceid...", 1)
            clientId = str("%012X" % uuid4())
            GUID = xbmcvfs.File(GUID_file, 'w')
            GUID.write(clientId)

        GUID.close()

        log("DeviceId loaded: %s" % clientId, 1)
        window('emby_deviceId', value=clientId)
        
        return clientId