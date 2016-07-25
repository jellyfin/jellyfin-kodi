# -*- coding: utf-8 -*-

#################################################################################################

import logging
import requests
import threading

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################

class image_cache_thread(threading.Thread):

    urlToProcess = None
    isFinished = False
    
    xbmc_host = ""
    xbmc_port = ""
    xbmc_username = ""
    xbmc_password = ""
    

    def __init__(self):

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
        
        log.debug("Image Caching Thread Processing: %s" % self.urlToProcess)
        
        try:
            response = requests.head(
                                url=(
                                    "http://%s:%s/image/image://%s"
                                    % (self.xbmc_host, self.xbmc_port, self.urlToProcess)),
                                auth=(self.xbmc_username, self.xbmc_password),
                                timeout=(35.1, 35.1))
        # We don't need the result
        except: pass
        
        log.debug("Image Caching Thread Exited")
        self.isFinished = True