# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from kodi_six import xbmc, xbmcaddon

from . import LazyLogger

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


def translate(string):

    ''' Get add-on string. Returns in unicode.
    '''
    if type(string) != int:
        string = STRINGS[string]

    result = xbmcaddon.Addon('plugin.video.jellyfin').getLocalizedString(string)

    if not result:
        result = xbmc.getLocalizedString(string)

    return result


STRINGS = {
    'addon_name': 29999,
    'playback_mode': 30511,
    'empty_user': 30613,
    'empty_user_pass': 30608,
    'empty_server': 30617,
    'network_credentials': 30517,
    'invalid_auth': 33009,
    'addon_mode': 33036,
    'native_mode': 33037,
    'cancel': 30606,
    'username': 30024,
    'password': 30602,
    'gathering': 33021,
    'boxsets': 30185,
    'movies': 30302,
    'tvshows': 30305,
    'fav_movies': 30180,
    'fav_tvshows': 30181,
    'fav_episodes': 30182
}
