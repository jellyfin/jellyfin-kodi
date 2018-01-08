# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys

import xbmc
import xbmcaddon

#################################################################################################

_ADDON = xbmcaddon.Addon(id='plugin.video.emby')
_CWD = _ADDON.getAddonInfo('path').decode('utf-8')
_BASE_LIB = xbmc.translatePath(os.path.join(_CWD, 'resources', 'lib')).decode('utf-8')
sys.path.append(_BASE_LIB)

#################################################################################################

import loghandler
from context_entry import ContextMenu

#################################################################################################

loghandler.config()
log = logging.getLogger("EMBY.contextmenu_play")

#################################################################################################

if __name__ == "__main__":

    try:
        # Start the context menu
        ContextMenu(True)
    except Exception as error:
        log.exception(error)
