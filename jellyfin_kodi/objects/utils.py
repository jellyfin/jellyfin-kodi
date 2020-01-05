# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import logging

from helper import JSONRPC

#################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

#################################################################################################


def get_grouped_set():

    ''' Get if boxsets should be grouped
    '''
    result = JSONRPC('Settings.GetSettingValue').execute({'setting': "videolibrary.groupmoviesets"})
    return result.get('result', {}).get('value', False)
