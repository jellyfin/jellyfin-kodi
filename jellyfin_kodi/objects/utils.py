# -*- coding: utf-8 -*-

#################################################################################################

from ..helper import JSONRPC
from ..helper import LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


def get_grouped_set():
    """Get if boxsets should be grouped"""
    result = JSONRPC("Settings.GetSettingValue").execute(
        {"setting": "videolibrary.groupmoviesets"}
    )
    return result.get("result", {}).get("value", False)
