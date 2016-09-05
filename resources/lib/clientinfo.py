# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
from uuid import uuid4

import xbmc
import xbmcaddon
import xbmcvfs

from utils import window, settings

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class ClientInfo(object):


    def __init__(self):

        self.addon = xbmcaddon.Addon()

    def getAddonName(self):
        # Used for logging
        return self.addon.getAddonInfo('name').upper()

    @classmethod
    def getAddonId(cls):
        return "plugin.video.emby"

    def getVersion(self):
        return self.addon.getAddonInfo('version')

    @classmethod
    def getDeviceName(cls):

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
        elif xbmc.getCondVisibility('system.platform.android'):
            return "Linux/Android"
        elif xbmc.getCondVisibility('system.platform.linux.raspberrypi'):
            return "Linux/RPi"
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux"
        else:
            return "Unknown"

    def getDeviceId(self, reset=False):

        client_id = window('emby_deviceId')
        if client_id:
            return client_id

        emby_guid = xbmc.translatePath("special://temp/emby_guid").decode('utf-8')
        
        ###$ Begin migration $###
        if not xbmcvfs.exists(emby_guid):
            addon_path = self.addon.getAddonInfo('path').decode('utf-8')
            if os.path.supports_unicode_filenames:
                path = os.path.join(addon_path, "machine_guid")
            else:
                path = os.path.join(addon_path.encode('utf-8'), "machine_guid")
            
            guid_file = xbmc.translatePath(path).decode('utf-8')
            if xbmcvfs.exists(guid_file):
                xbmcvfs.copy(guid_file, emby_guid)
        ###$ End migration $###

        if reset and xbmcvfs.exists(emby_guid):
            # Reset the file
            xbmcvfs.delete(emby_guid)

        guid = xbmcvfs.File(emby_guid)
        client_id = guid.read()
        if not client_id:
            log.info("Generating a new guid...")
            client_id = str("%012X" % uuid4())
            guid = xbmcvfs.File(emby_guid, 'w')
            guid.write(client_id)

        guid.close()

        log.info("DeviceId loaded: %s", client_id)
        window('emby_deviceId', value=client_id)

        return client_id
