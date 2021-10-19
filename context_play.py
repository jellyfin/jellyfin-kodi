# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from jellyfin_kodi.entrypoint.context import Context
from jellyfin_kodi.helper import LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


if __name__ == "__main__":

    LOG.debug("--->[ context ]")

    try:
        Context(True)
    except Exception as error:
        LOG.exception(error)

    LOG.info("---<[ context ]")
