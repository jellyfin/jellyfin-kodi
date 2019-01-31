# -*- coding: utf-8 -*-

#################################################################################################

import BaseHTTPServer
import logging
import httplib
import threading
import urlparse

import xbmc

#################################################################################################

PORT = 57578
LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################

class WebService(threading.Thread):

    ''' Run a webservice to trigger playback.
    '''
    def __init__(self):
        threading.Thread.__init__(self)

    def stop(self):

        ''' Called when the thread needs to stop
        '''
        try:
            conn = httplib.HTTPConnection("127.0.0.1:%d" % PORT)
            conn.request("QUIT", "/")
            conn.getresponse()
        except Exception as error:
            pass

    def run(self):

        ''' Called to start the webservice.
        '''
        LOG.info("--->[ webservice/%s ]", PORT)

        try:
            server = HttpServer(('127.0.0.1', PORT), requestHandler)
            server.serve_forever()
        except Exception as error:

            if '10053' not in error: # ignore host diconnected errors
                LOG.exception(error)

        LOG.info("---<[ webservice ]")


class HttpServer(BaseHTTPServer.HTTPServer):

    ''' Http server that reacts to self.stop flag.
    '''
    def serve_forever(self):

        ''' Handle one request at a time until stopped.
        '''
        self.stop = False

        while not self.stop:
            self.handle_request()


class requestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    ''' Http request handler. Do not use LOG here,
        it will hang requests in Kodi > show information dialog.
    '''

    def log_message(self, format, *args):

        ''' Mute the webservice requests.
        '''
        pass

    def do_QUIT(self):

        ''' send 200 OK response, and set server.stop to True
        '''
        self.send_response(200)
        self.end_headers()
        self.server.stop = True

    def get_params(self):

        ''' Get the params
        '''
        try:
            path = self.path[1:]

            if '?' in path:
                path = path.split('?', 1)[1]

            params = dict(urlparse.parse_qsl(path))
        except Exception:
            params = {}

        return params

    def do_HEAD(self):

        ''' Called on HEAD requests
        '''
        self.send_response(200)
        self.end_headers()

        return

    def do_GET(self):

        ''' Return plugin path
        '''
        try:
            params = self.get_params()

            if not params:
                raise IndexError("Incomplete URL format")

            if not params.get('Id').isdigit():
                raise IndexError("Incorrect Id format %s" % params.get('Id'))

            xbmc.log("[ webservice ] path: %s params: %s" % (str(self.path), str(params)), xbmc.LOGWARNING)

            path = ("plugin://plugin.video.emby?mode=play&id=%s&dbid=%s&filename=%s&transcode=%s"
                    % (params.get('Id'), params.get('KodiId'), params.get('Name'), params.get('transcode') or False))

            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write(path)

        except IndexError as error:

            xbmc.log(str(error), xbmc.LOGWARNING)
            self.send_error(404, "Exception occurred: %s" % error)

        except Exception as error:

            xbmc.log(str(error), xbmc.LOGWARNING)
            self.send_error(500, "Exception occurred: %s" % error)

        return

