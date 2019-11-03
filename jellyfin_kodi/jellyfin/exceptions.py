# -*- coding: utf-8 -*-

#################################################################################################


class HTTPException(Exception):
    # Jellyfin HTTP exception
    def __init__(self, status, message):
        self.status = status
        self.message = message
