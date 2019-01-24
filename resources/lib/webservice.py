# -*- coding: utf-8 -*-

#################################################################################################

import SimpleHTTPServer
import BaseHTTPServer
import logging
import httplib
import threading
import urlparse
import urllib

import xbmc
import xbmcvfs

#################################################################################################

PORT = 57578
LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class WebService(threading.Thread):

    ''' Run a webservice to trigger playback.
        Inspired from script.skin.helper.service by marcelveldt.
    '''
    stop_thread = False

    def __init__(self):
        threading.Thread.__init__(self)

    def stop(self):

        ''' Called when the thread needs to stop
        '''
        try:
            conn = httplib.HTTPConnection("127.0.0.1:%d" % PORT)
            conn.request("QUIT", "/")
            conn.getresponse()
            self.stop_thread = True
        except Exception as error:
            LOG.exception(error)

    def run(self):

        ''' Called to start the webservice.
        '''
        LOG.info("--->[ webservice/%s ]", PORT)

        try:
            server = StoppableHttpServer(('127.0.0.1', PORT), StoppableHttpRequestHandler)
            server.serve_forever()
        except Exception as error:

            if '10053' not in error: # ignore host diconnected errors
                LOG.exception(error)

        LOG.info("---<[ webservice ]")


class Request(object):

    ''' Attributes from urlsplit that this class also sets
    '''
    uri_attrs = ('scheme', 'netloc', 'path', 'query', 'fragment')

    def __init__(self, uri, headers, rfile=None):

        self.uri = uri
        self.headers = headers
        parsed = urlparse.urlsplit(uri)

        for i, attr in enumerate(self.uri_attrs):
            setattr(self, attr, parsed[i])

        try:
            body_len = int(self.headers.get('Content-length', 0))
        except ValueError:
            body_len = 0

        self.body = rfile.read(body_len) if body_len and rfile else None


class StoppableHttpServer(BaseHTTPServer.HTTPServer):

    ''' Http server that reacts to self.stop flag.
    '''
    def serve_forever(self):

        ''' Handle one request at a time until stopped.
        '''
        self.stop = False

        while not self.stop:

            self.handle_request()
            xbmc.sleep(100)


class StoppableHttpRequestHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    ''' http request handler with QUIT stopping the server
    '''
    raw_requestline = ""

    def __init__(self, request, client_address, server):
        try:
            SimpleHTTPServer.SimpleHTTPRequestHandler.__init__(self, request, client_address, server)
        except Exception:
            pass

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

    def parse_request(self):

        ''' Modify here to workaround unencoded requests.
        '''
        retval = SimpleHTTPServer.SimpleHTTPRequestHandler.parse_request(self)
        self.request = Request(self.path, self.headers, self.rfile)

        return retval

    def do_HEAD(self):

        ''' Called on HEAD requests
        '''
        self.handle_request(True)

        return

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

    def handle_request(self, headers_only=False):

        ''' Send headers and reponse
        '''
        try:
            params = self.get_params()
            LOG.info("Webservice called with params: %s", params)

            path = ("plugin://plugin.video.emby?mode=play&id=%s&dbid=%s&filename=%s&transcode=%s"
                    % (params.get('Id'), params.get('KodiId'), params.get('Name'), params.get('transcode') or False))
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.send_header('Content-Length', len(path))
            self.end_headers()

            if not headers_only:
                self.wfile.write(path)

        except Exception as error:

            LOG.exception(error)
            self.send_error(500, "Exception occurred: %s" % error)

        return

    def do_GET(self):

        ''' Called on GET requests
        '''
        self.handle_request()

        return
