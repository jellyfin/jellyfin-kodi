# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################


class LibraryException(Exception):
    # Jellyfin library sync exception
    def __init__(self, status):
        self.status = status
