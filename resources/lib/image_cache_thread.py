# -*- coding: utf-8 -*-

#################################################################################################

import threading
import requests

from utils import Logging

#################################################################################################

class image_cache_thread(threading.Thread):

    urlToProcess = None
    isFinished = False
    
    xbmc_host = ""
    xbmc_port = ""
    xbmc_username = ""
    xbmc_password = ""
    

    def __init__(self):

        global log
        log = Logging(self.__class__.__name__).log

        threading.Thread.__init__(self)

        
    def setUrl(self, url):

        self.urlToProcess = url
        
    def setHost(self, host, port):

        self.xbmc_host = host
        self.xbmc_port = port
        
    def setAuth(self, user, pwd):

        self.xbmc_username = user
        self.xbmc_password = pwd
         
    def run(self):
        
        log("Image Caching Thread Processing: %s" % self.urlToProcess, 2)
        
        try:
            response = requests.head(
                                url=(
                                    "http://%s:%s/image/image://%s"
                                    % (self.xbmc_host, self.xbmc_port, self.urlToProcess)),
                                auth=(self.xbmc_username, self.xbmc_password),
                                timeout=(35.1, 35.1))
        # We don't need the result
        except: pass
        
        log("Image Caching Thread Exited", 2)
        self.isFinished = True