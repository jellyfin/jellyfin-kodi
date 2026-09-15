# -*- coding: utf-8 -*-
from typing_extensions import deprecated

#################################################################################################


@deprecated("Jellyfin-specific http exception class should be phased out")
class HTTPException(Exception):
    # Jellyfin HTTP exception
    def __init__(self, status, message):
        self.status = status
        self.message = message


class LibraryException(Exception):
    pass


class LibraryExitException(LibraryException):
    "Exception raised to propagate application exit."


class LibrarySyncLaterException(LibraryException):
    "Raised when no libraries are selected for sync."


class PathValidationException(Exception):
    """
    Replacing generic `Exception`

    TODO: Investigate the usage of this to see if it can be done better.
    """
