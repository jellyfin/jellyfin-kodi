# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################


class HTTPException(Exception):
    # Jellyfin HTTP exception
    def __init__(self, status, message):
        self.status = status
        self.message = message


class LibraryException(Exception):
    # Jellyfin library sync exception
    def __init__(self, status):
        self.status = status


class PathValidationException(Exception):
    # raise Exception("Failed to validate path. User stopped.")
    pass
