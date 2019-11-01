# -*- coding: utf-8 -*-

#################################################################################################


class LibraryException(Exception):
    # Jellyfin library sync exception
    def __init__(self, status):
        self.status = status
