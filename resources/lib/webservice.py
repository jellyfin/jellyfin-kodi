# -*- coding: utf-8 -*-

#################################################################################################

import logging
import threading

import xbmc
import xbmcvfs

import cherrypy

#################################################################################################

PORT = 57578
LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Root(object):

    @cherrypy.expose
    def default(self, *args, **kwargs):

        try:
            if not kwargs.get('Id').isdigit():
                raise IndexError("Incorrect Id format: %s" % kwargs.get('Id'))

            LOG.info("Webservice called with params: %s", kwargs)

            return ("plugin://plugin.video.emby?mode=play&id=%s&dbid=%s&filename=%s&transcode=%s"
                    % (kwargs.get('Id'), kwargs.get('KodiId'), kwargs.get('Name'), kwargs.get('transcode') or False))

        except IndexError as error:
            LOG.error(error)

            raise cherrypy.HTTPError(404, error)

        except Exception as error:
            LOG.exception(error)

            raise cherrypy.HTTPError(500, "Exception occurred: %s" % error)

class WebService(threading.Thread):

    root = None

    def __init__(self):

        self.root = Root()
        cherrypy.config.update({
            'engine.autoreload.on' : False,
            'log.screen': False,
            'engine.timeout_monitor.frequency': 5,
            'server.shutdown_timeout': 1,
        })
        threading.Thread.__init__(self)

    def run(self):
        
        LOG.info("--->[ webservice/%s ]", PORT)
        conf = {
            'global': {
                'server.socket_host': '0.0.0.0',
                'server.socket_port': PORT
            }, '/': {}
        }
        cherrypy.quickstart(self.root, '/', conf)

    def stop(self):

        cherrypy.engine.exit()
        self.join(0)

        del self.root
