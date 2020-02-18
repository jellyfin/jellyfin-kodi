# -*- coding: utf-8 -*-

##################################################################################################

import cProfile
import json
import logging
import pstats
import StringIO

##################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

class JsonDebugPrinter(object):

    def __init__(self, json):
        self.json = json

    def __str__(self):
        return json.dumps(self.json, indent=4)

def profile(fn):
    def profiling_wrapper(*args, **kargs):
        pr = cProfile.Profile()
        pr.enable()

        fn(*args, **kargs)

        pr.disable()
        s = StringIO.StringIO()
        sortby = 'cumulative'
        ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        ps.print_stats()
        LOG.debug(s.getvalue())
    return profiling_wrapper

