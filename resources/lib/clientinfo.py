# -*- coding: utf-8 -*-

#################################################################################################

import logging
import hashlib
import os
import platform

import xbmc
import xbmcaddon
import xbmcvfs

from utils import window, settings, create_id

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class ClientInfo(object):


    def __init__(self):

        self.addon = xbmcaddon.Addon(self.get_addon_id())

    @staticmethod
    def get_addon_id():
        return "plugin.video.emby"

    def get_addon_name(self):
        # Used for logging
        return self.addon.getAddonInfo('name').upper()

    def get_version(self):
        return self.addon.getAddonInfo('version')

    @classmethod
    def get_device_name(cls):

        if settings('deviceNameOpt') == "false":
            # Use Kodi's deviceName
            device_name = xbmc.getInfoLabel('System.FriendlyName').decode('utf-8')
        else:
            device_name = settings('deviceName')
            device_name = device_name.replace("\"", "_")
            device_name = device_name.replace("/", "_")

        return device_name

    @classmethod
    def get_platform(cls):

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

    @classmethod
    def get_device_id(cls):

        client_id = window('emby_deviceId')
        if client_id:
            return client_id

        """
        emby_guid = xbmc.translatePath("special://temp/emby_guid").decode('utf-8')

        if reset and xbmcvfs.exists(emby_guid):
            xbmcvfs.delete(emby_guid)

        guid = xbmcvfs.File(emby_guid)
        client_id = guid.read()
        if not client_id:
            log.info("Generating a new guid...")
            client_id = str("%012X" % create_id())
            guid = xbmcvfs.File(emby_guid, 'w')
            guid.write(client_id)

        guid.close()
        """

        guid = xbmc.getInfoLabel('Network.MacAddress') or ''.join(platform.uname())
        client_id = hashlib.sha1(guid).hexdigest().upper()

        xbmc.log("EMBY DeviceId: %s" % client_id, level=xbmc.LOGNOTICE)
        window('emby_deviceId', value=client_id)

        return client_id
