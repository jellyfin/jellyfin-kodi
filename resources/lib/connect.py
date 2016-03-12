# -*- coding: utf-8 -*-

##################################################################################################

import json
import requests
import logging

import utils
import clientinfo

##################################################################################################

# Disable requests logging
from requests.packages.urllib3.exceptions import InsecureRequestWarning, InsecurePlatformWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
requests.packages.urllib3.disable_warnings(InsecurePlatformWarning)
#logging.getLogger('requests').setLevel(logging.WARNING)

##################################################################################################


class ConnectUtils():
    
    # Borg - multiple instances, shared state
    _shared_state = {}
    clientInfo = clientinfo.ClientInfo()
    addonName = clientInfo.getAddonName()

    # Requests session
    c = None
    timeout = 30


    def __init__(self):

        self.__dict__ = self._shared_state

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)


    def setUserId(self, userId):
        # Reserved for userclient only
        self.userId = userId
        self.logMsg("Set connect userId: %s" % userId, 2)

    def setServer(self, server):
        # Reserved for userclient only
        self.server = server
        self.logMsg("Set connect server: %s" % server, 2)

    def setToken(self, token):
        # Reserved for userclient only
        self.token = token
        self.logMsg("Set connect token: %s" % token, 2)


    def startSession(self):

        log = self.logMsg

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
            log("Could not load SSL settings.", 1)
        
        # Start session
        self.c = requests.Session()
        self.c.headers = header
        self.c.verify = verify
        # Retry connections to the server
        self.c.mount("http://", requests.adapters.HTTPAdapter(max_retries=1))
        self.c.mount("https://", requests.adapters.HTTPAdapter(max_retries=1))

        log("Requests session started on: %s" % self.server, 1)

    def stopSession(self):
        try:
            self.c.close()
        except Exception as e:
            self.logMsg("Requests session could not be terminated: %s" % e, 1)

    def getHeader(self, authenticate=True):

        clientInfo = self.clientInfo
        version = clientInfo.getVersion()

        if not authenticate:
            # If user is not authenticated
            header = {

                'X-Application': "Kodi/%s" % version,
                'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': "application/json"
            }      
            self.logMsg("Header: %s" % header, 1)
        
        else:
            token = self.token
            # Attached to the requests session
            header = {

                'Content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Accept': "application/json",
                'X-Application': "Kodi/%s" % version,
                'X-Connect-UserToken': token
            }        
            self.logMsg("Header: %s" % header, 1)
        
        return header

    def doUrl(self, url, data=None, postBody=None, rtype="GET",
                parameters=None, authenticate=True, timeout=None):

        log = self.logMsg
        window = utils.window

        log("=== ENTER connectUrl ===", 2)
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
            log(r.url, 1)
            log(r, 1)

            if r.status_code == 204:
                # No body in the response
                log("====== 204 Success ======", 1)

            elif r.status_code == requests.codes.ok:
               
                try: 
                    # UNICODE - JSON object
                    r = r.json()
                    log("====== 200 Success ======", 1)
                    log("Response: %s" % r, 1)
                    return r

                except:
                    if r.headers.get('content-type') != "text/html":
                        log("Unable to convert the response for: %s" % url, 1)
            else:
                r.raise_for_status()
        
        ##### EXCEPTIONS #####

        except requests.exceptions.ConnectionError as e:
            # Make the addon aware of status
            pass

        except requests.exceptions.ConnectTimeout as e:
            log("Server timeout at: %s" % url, 0)
            log(e, 1)

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
            log("Invalid SSL certificate for: %s" % url, 0)
            log(e, 1)

        except requests.exceptions.RequestException as e:
            log("Unknown error connecting to: %s" % url, 0)
            log(e, 1)

        return default_link
