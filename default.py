# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os
import sys

from kodi_six import xbmc, xbmcaddon

#################################################################################################

__addon__ = xbmcaddon.Addon(id='plugin.video.jellyfin')
__base__ = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'), 'jellyfin_kodi'))

sys.path.insert(0, __base__)

#################################################################################################

from entrypoint import Events  # noqa: E402
from helper import LazyLogger  # noqa: E402

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


if __name__ == "__main__":

    LOG.debug("--->[ default ]")

    try:
        Events()
    except Exception as error:
        LOG.exception(error)

    LOG.info("---<[ default ]")
