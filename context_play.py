# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys

import xbmc
import xbmcaddon

#################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.emby').getAddonInfo('path').decode('utf-8')
__base__ = xbmc.translatePath(os.path.join(__addon__, 'resources', 'lib')).decode('utf-8')
sys.path.append(__base__)

#################################################################################################

from entrypoint import Context

#################################################################################################

LOG = logging.getLogger("EMBY.context")

#################################################################################################


if __name__ == "__main__":

    LOG.info("--->[ context ]")

    try:
        Context(True)
    except Exception as error:
        LOG.exception(error)

    LOG.info("---<[ context ]")
