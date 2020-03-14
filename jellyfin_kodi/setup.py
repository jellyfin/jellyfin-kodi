# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import logging

from helper import translate, settings, dialog, JSONRPC

#################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

#################################################################################################


class Setup(object):

    def __init__(self):

        self.setup()

        LOG.info("---<[ setup ]")

    def setup(self):

        minimum = "3.0.24"
        cached = settings('MinimumSetup')

        if cached == minimum:
            return

        if not cached:

            self._is_mode()
            LOG.info("Add-on playback: %s", settings('useDirectPaths') == "0")

        # Setup completed
        settings('MinimumSetup', minimum)

    def _is_mode(self):

        ''' Setup playback mode. If native mode selected, check network credentials.
        '''
        value = dialog("yesno",
                       heading=translate('playback_mode'),
                       line1=translate(33035),
                       nolabel=translate('addon_mode'),
                       yeslabel=translate('native_mode'))

        settings('useDirectPaths', value="1" if value else "0")

        if value:
            dialog("ok", heading="{jellyfin}", line1=translate(33145))

    def _is_music(self):

        value = dialog("yesno", heading="{jellyfin}", line1=translate(33039))
        settings('enableMusic.bool', value=value)
