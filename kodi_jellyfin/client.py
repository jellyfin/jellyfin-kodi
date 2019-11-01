# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os

import xbmc
import xbmcaddon
import xbmcvfs

from helper import _, window, settings, addon_id, dialog
from helper.utils import create_id

##################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

##################################################################################################


def get_addon_name():

    ''' Used for logging.
    '''
    return xbmcaddon.Addon(addon_id()).getAddonInfo('name').upper()


def get_version():
    return xbmcaddon.Addon(addon_id()).getAddonInfo('version')


def get_platform():

    if xbmc.getCondVisibility('system.platform.osx'):
        return "OSX"
    elif xbmc.getCondVisibility('System.HasAddon(service.coreelec.settings)'):
        return "CoreElec"
    elif xbmc.getCondVisibility('System.HasAddon(service.libreelec.settings)'):
        return "LibreElec"
    elif xbmc.getCondVisibility('System.HasAddon(service.osmc.settings)'):
        return "OSMC"
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


def get_device_name():

    ''' Detect the device name. If deviceNameOpt, then
        use the device name in the add-on settings.
        Otherwise fallback to the Kodi device name.
    '''
    if not settings('deviceNameOpt.bool'):
        device_name = xbmc.getInfoLabel('System.FriendlyName').decode('utf-8')
    else:
        device_name = settings('deviceName')
        device_name = device_name.replace("\"", "_")
        device_name = device_name.replace("/", "_")

    return device_name


def get_device_id(reset=False):

    ''' Return the device_id if already loaded.
        It will load from jellyfin_guid file. If it's a fresh
        setup, it will generate a new GUID to uniquely
        identify the setup for all users.

        window prop: jellyfin_deviceId
    '''
    client_id = window('jellyfin_deviceId')

    if client_id:
        return client_id

    directory = xbmc.translatePath('special://profile/addon_data/plugin.video.jellyfin/').decode('utf-8')

    if not xbmcvfs.exists(directory):
        xbmcvfs.mkdir(directory)

    jellyfin_guid = os.path.join(directory, "jellyfin_guid")
    file_guid = xbmcvfs.File(jellyfin_guid)
    client_id = file_guid.read()

    if not client_id or reset:
        LOG.info("Generating a new GUID.")

        client_id = str("%012X" % create_id())
        file_guid = xbmcvfs.File(jellyfin_guid, 'w')
        file_guid.write(client_id)

    file_guid.close()

    LOG.info("DeviceId loaded: %s", client_id)
    window('jellyfin_deviceId', value=client_id)

    return client_id


def reset_device_id():

    window('jellyfin_deviceId', clear=True)
    get_device_id(True)
    dialog("ok", heading="{jellyfin}", line1=_(33033))
    xbmc.executebuiltin('RestartApp')


def get_info():
    return {
        'DeviceName': get_device_name(),
        'Version': get_version(),
        'DeviceId': get_device_id()
    }
