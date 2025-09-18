# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import warnings

#################################################################################################


class HTTPException(Exception):
    # Jellyfin HTTP exception
    def __init__(self, status, message):
        warnings.warn(
            f"{self.__class__.__name__} will be deprecated.",
            DeprecationWarning,
            stacklevel=2,
        )
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
