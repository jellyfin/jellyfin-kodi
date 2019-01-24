# -*- coding: utf-8 -*-

#################################################################################################

import logging

from helper import JSONRPC

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################

def get_play_action():

    ''' I could not figure out a way to listen to kodi setting changes?
        For now, verify the play action every time play is called.
    '''
    options = ['Choose', 'Play', 'Resume', 'Show information']
    result = JSONRPC('Settings.GetSettingValue').execute({'setting': "myvideos.selectaction"})
    try:
        return options[result['result']['value']]
    except Exception as error:
        log.error("Returning play action due to error: %s", error)

        return options[1]

def get_grouped_set():

    ''' Get if boxsets should be grouped
    '''
    result = JSONRPC('Settings.GetSettingValue').execute({'setting': "videolibrary.groupmoviesets"})
    try:
        return result['result']['value']
    except Exception as error:
        return False
