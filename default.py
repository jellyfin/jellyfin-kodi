# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from jellyfin_kodi.entrypoint.default import Events
from jellyfin_kodi.helper import LazyLogger

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
