# -*- coding: utf-8 -*-

#################################################################################################

class HTTPException(Exception):
    # Emby HTTP exception
    def __init__(self, status, message):
        self.status = status
        self.message = message


