# -*- coding: utf-8 -*-

##################################################################################################

import json
import requests
import logging

import clientinfo
from utils import window

##################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class ConnectUtils():

    # Borg - multiple instances, shared state
    _shared_state = {}
    clientInfo = clientinfo.ClientInfo()

    # Requests session
    c = None
    timeout = 30


    def __init__(self):

        self.__dict__ = self._shared_state


    def setUserId(self, userId):
        # Reserved for userclient only
        self.userId = userId
        log.debug("Set connect userId: %s" % userId)

    def setServer(self, server):
        # Reserved for userclient only
        self.server = server
        log.debug("Set connect server: %s" % server)

    def setToken(self, token):
        # Reserved for userclient only
        self.token = token
        log.debug("Set connect token: %s" % token)


    def startSession(self):

        self.deviceId = self.clientInfo.getDeviceId()

        # User is identified from this point
        # Attach authenticated header to the session
        verify = False
        header = self.getHeader()

        # If user enabled host certificate verification
        try:
            verify = self.sslverify
            if self.sslclient is not None:
                verify = self.sslclient
        except:
            log.info("Could not load SSL settings.")

        # Start session
        self.c = requests.Session()
        self.c.headers = header
        self.c.verify = verify
        # Retry connections to the server
        self.c.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.c.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        log.info("Requests session started on: %s" % self.server)

    def stopSession(self):
        try:
            self.c.close()
        except Exception:
            log.warn("Requests session could not be terminated")

    def getHeader(self, authenticate=True):

        version = self.clientInfo.getVersion()

        if not authenticate:
            # If user is not authenticated
            header = {

                'X-Application': "Kodi/%s" % version,
                'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': "application/json"
            }
            log.info("Header: %s" % header)

        else:
            token = self.token
            # Attached to the requests session
            header = {

                'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': "application/json",
                'X-Application': "Kodi/%s" % version,
                'X-Connect-UserToken': token
            }
            log.info("Header: %s" % header)

        return header

    def doUrl(self, url, data=None, postBody=None, rtype="GET",
                parameters=None, authenticate=True, timeout=None):

        log.debug("=== ENTER connectUrl ===")
        
        default_link = ""
        
        if timeout is None:
            timeout = self.timeout

        # Get requests session
        try:
            # If connect user is authenticated
            if authenticate:
                try:
                    c = self.c
                    # Replace for the real values
                    url = url.replace("{server}", self.server)
                    url = url.replace("{UserId}", self.userId)

                    # Prepare request
                    if rtype == "GET":
                        r = c.get(url, json=postBody, params=parameters, timeout=timeout)
                    elif rtype == "POST":
                        r = c.post(url, data=data, timeout=timeout)
                    elif rtype == "DELETE":
                        r = c.delete(url, json=postBody, timeout=timeout)

                except AttributeError:
                    # request session does not exists
                    self.server = "https://connect.emby.media/service"
                    self.userId = window('embyco_currUser')
                    self.token = window('embyco_accessToken%s' % self.userId)

                    header = self.getHeader()
                    verifyssl = False

                    # If user enables ssl verification
                    try:
                        verifyssl = self.sslverify
                        if self.sslclient is not None:
                            verifyssl = self.sslclient
                    except AttributeError:
                        pass

                    # Prepare request
                    if rtype == "GET":
                        r = requests.get(url,
                                        json=postBody,
                                        params=parameters,
                                        headers=header,
                                        timeout=timeout,
                                        verify=verifyssl)

                    elif rtype == "POST":
                        r = requests.post(url,
                                        data=data,
                                        headers=header,
                                        timeout=timeout,
                                        verify=verifyssl)
            # If user is not authenticated
            else:
                header = self.getHeader(authenticate=False)
                verifyssl = False

                # If user enables ssl verification
                try:
                    verifyssl = self.sslverify
                    if self.sslclient is not None:
                        verifyssl = self.sslclient
                except AttributeError:
                    pass

                # Prepare request
                if rtype == "GET":
                    r = requests.get(url,
                                    json=postBody,
                                    params=parameters,
                                    headers=header,
                                    timeout=timeout,
                                    verify=verifyssl)

                elif rtype == "POST":
                    r = requests.post(url,
                                    data=data,
                                    headers=header,
                                    timeout=timeout,
                                    verify=verifyssl)

            ##### THE RESPONSE #####
            log.info(r.url)
            log.info(r)

            if r.status_code == 204:
                # No body in the response
                log.info("====== 204 Success ======")

            elif r.status_code == requests.codes.ok:

                try:
                    # UNICODE - JSON object
                    r = r.json()
                    log.info("====== 200 Success ======")
                    log.info("Response: %s" % r)
                    return r

                except:
                    if r.headers.get('content-type') != "text/html":
                        log.info("Unable to convert the response for: %s" % url)
            else:
                r.raise_for_status()

        ##### EXCEPTIONS #####

        except requests.exceptions.ConnectionError as e:
            # Make the addon aware of status
            pass

        except requests.exceptions.ConnectTimeout as e:
            log.warn("Server timeout at: %s" % url)

        except requests.exceptions.HTTPError as e:

            if r.status_code == 401:
                # Unauthorized
                pass

            elif r.status_code in (301, 302):
                # Redirects
                pass
            elif r.status_code == 400:
                # Bad requests
                pass

        except requests.exceptions.SSLError as e:
            log.warn("Invalid SSL certificate for: %s" % url)

        except requests.exceptions.RequestException as e:
            log.warn("Unknown error connecting to: %s" % url)

        return default_link