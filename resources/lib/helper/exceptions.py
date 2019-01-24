# -*- coding: utf-8 -*-

#################################################################################################

class LibraryException(Exception):
    # Emby library sync exception
    def __init__(self, status):
        self.status = status


