# -*- coding: utf-8 -*-

##################################################################################################

import json

##################################################################################################

class JsonDebugPrinter(object):

    def __init__(self, json):
        self.json = json

    def __str__(self):
        return json.dumps(self.json, indent=4)
