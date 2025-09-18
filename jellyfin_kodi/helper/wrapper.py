# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

from functools import wraps

#################################################################################################

import xbmcgui
import xbmc

from . import LazyLogger

from .utils import window
from .exceptions import LibraryExitException
from .translate import translate

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


def progress(message=None):
    """Will start and close the progress dialog."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, item=None, *args, **kwargs):

            dialog = xbmcgui.DialogProgressBG()

            if item and isinstance(item, dict):

                dialog.create(
                    translate("addon_name"),
                    "%s %s" % (translate("gathering"), item["Name"]),
                )
                LOG.info("Processing %s: %s", item["Name"], item["Id"])
            else:
                dialog.create(translate("addon_name"), message)
                LOG.info("Processing %s", message)

            if item:
                args = (item,) + args

            result = func(self, dialog=dialog, *args, **kwargs)
            dialog.close()

            return result

        return wrapper

    return decorator


def stop(func):
    """Wrapper to catch exceptions and return using catch"""

    @wraps(func)
    def wrapper(*args, **kwargs):

        if xbmc.Monitor().waitForAbort(0.00001):
            raise LibraryExitException("Kodi aborted, exiting...")

        if window("jellyfin_should_stop.bool"):
            LOG.info("exiiiiitttinggg")
            raise LibraryExitException("Should stop flag raised, exiting...")

        if not window("jellyfin_online.bool"):
            raise LibraryExitException("Jellyfin not online, exiting...")

        return func(*args, **kwargs)

    return wrapper


def jellyfin_item(func):
    """Wrapper to retrieve the jellyfin_db item."""

    @wraps(func)
    def wrapper(self, item, *args, **kwargs):
        e_item = self.jellyfin_db.get_item_by_id(
            item["Id"] if isinstance(item, dict) else item
        )

        return func(self, item, e_item=e_item, *args, **kwargs)

    return wrapper
