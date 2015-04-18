import xbmc
import xbmcgui
import xbmcaddon
import urllib
import urllib2
import httplib
import hashlib
import StringIO
import gzip
import sys
import inspect
import json as json
from random import randrange
from uuid import uuid4 as uuid4
from ClientInformation import ClientInformation
import encodings
import time
import traceback

class DownloadUtils():

    WINDOW = xbmcgui.Window(10000)
    logLevel = 0
    addonSettings = None
    getString = None
    LogCalls = False
    TrackLog = ""
    TotalUrlCalls = 0

    def __init__(self, *args):
        addonId = ClientInformation().getAddonId()
        self.addonSettings = xbmcaddon.Addon(id=addonId)
        self.addon = xbmcaddon.Addon(id=addonId)
        self.getString = self.addonSettings.getLocalizedString
        level = self.addonSettings.getSetting('logLevel')        
        self.logLevel = 0
        if(level != None and level != ""):
            self.logLevel = int(level)
        if(self.logLevel == 2):
            self.LogCalls = True

    def logMsg(self, msg, level = 1):
        if(self.logLevel >= level):
            try:
                xbmc.log("emby DownloadUtils -> " + str(msg))
            except UnicodeEncodeError:
                try:
                    xbmc.log("emby DownloadUtils -> " + str(msg.encode('utf-8')))
                except: pass

    def getServer(self, prefix=True):
        
        WINDOW = self.WINDOW
        username = WINDOW.getProperty("currUser")
        
        if prefix:
            server = WINDOW.getProperty("server%s" % username)
        else:
            server = WINDOW.getProperty("server_%s" % username)

        return server

    def getUserId(self, suppress=True):

        WINDOW = xbmcgui.Window( 10000 )
        self.addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        port = self.addonSettings.getSetting('port')
        host = self.addonSettings.getSetting('ipaddress')
        userName = self.addonSettings.getSetting('username')
        
        userid = WINDOW.getProperty("userid" + userName)

        if(userid != None and userid != ""):
            self.logMsg("DownloadUtils -> Returning saved (WINDOW) UserID : " + userid + "UserName: " + userName,2)
            return userid
            
        userid = self.addonSettings.getSetting("userid" + userName)
        if(userid != None and userid != ""):
            WINDOW.setProperty("userid" + userName, userid)
            self.logMsg("DownloadUtils -> Returning saved (SETTING) UserID : " + userid + "UserName: " + userName,2)
            return userid
    
        self.logMsg("Looking for user name: " + userName)

        authOk = self.authenticate()
        if(authOk == ""):
            if(suppress == False):
                xbmcgui.Dialog().ok(self.getString(30044), self.getString(30044))
            return ""

        userid = WINDOW.getProperty("userid" + userName)
        if(userid == "" and suppress == False):
            xbmcgui.Dialog().ok(self.getString(30045),self.getString(30045))

        self.logMsg("userid : " + userid)
        self.postcapabilities()
        
        return userid
        
    def postcapabilities(self):
        self.logMsg("postcapabilities called")
        
        # Set Capabilities
        server = self.getServer()
        clientInfo = ClientInformation()
        machineId = clientInfo.getMachineId()
        
        # get session id
        url = "%s/mediabrowser/Sessions?DeviceId=%s&format=json" % (server, machineId)
        self.logMsg("Session URL : " + url);
        jsonData = self.downloadUrl(url)
        self.logMsg("Session JsonData : " + jsonData)
        result = json.loads(jsonData)
        self.logMsg("Session JsonData : " + str(result))
        sessionId = result[0].get("Id")
        self.logMsg("Session Id : " + str(sessionId))
        
        # post capability data
        #playableMediaTypes = "Audio,Video,Photo"
        playableMediaTypes = "Audio,Video"
        #supportedCommands = "Play,Playstate,DisplayContent,GoHome,SendString,GoToSettings,DisplayMessage,PlayNext"
        supportedCommands = "Play,Playstate,SendString,DisplayMessage,PlayNext"
        
        url = "%s/mediabrowser/Sessions/Capabilities?Id=%s&PlayableMediaTypes=%s&SupportedCommands=%s&SupportsMediaControl=True" % (server, sessionId, playableMediaTypes, supportedCommands)
        postData = {}
        #postData["Id"] = sessionId;
        #postData["PlayableMediaTypes"] = "Video";
        #postData["SupportedCommands"] = "MoveUp";
        stringdata = json.dumps(postData)
        self.logMsg("Capabilities URL : " + url);
        self.logMsg("Capabilities Data : " + stringdata)
        
        self.downloadUrl(url, postBody=stringdata, type="POST")

    def imageUrl(self, id, type, index, width, height):
    
        server = self.getServer()
        
        return "%s/mediabrowser/Items/%s/Images/%s?MaxWidth=%s&MaxHeight=%s&Index=%s" % (server, id, type, width, height, index)
    
    def getAuthHeader(self, authenticate=True):
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        version = clientInfo.getVersion()
        
        deviceName = self.addonSettings.getSetting('deviceName')
        deviceName = deviceName.replace("\"", "_")
        username = self.WINDOW.getProperty("currUser")

        if(authenticate == False):
            authString = "MediaBrowser Client=\"Kodi\",Device=\"" + deviceName + "\",DeviceId=\"" + txt_mac + "\",Version=\"" + version + "\""
            headers = {"Accept-encoding": "gzip", "Accept-Charset" : "UTF-8,*", "Authorization" : authString}        
            return headers
        else:
            userid = self.getUserId()
            authString = "MediaBrowser UserId=\"" + userid + "\",Client=\"Kodi\",Device=\"" + deviceName + "\",DeviceId=\"" + txt_mac + "\",Version=\"" + version + "\""
            headers = {"Accept-encoding": "gzip", "Accept-Charset" : "UTF-8,*", "Authorization" : authString}        
                
            authToken = self.WINDOW.getProperty("accessToken%s" % username)
            if(authToken != ""):
                headers["X-MediaBrowser-Token"] = authToken
                    
            self.logMsg("Authentication Header : " + str(headers),2)
            return headers
        
    def downloadUrl(self, url, suppress=False, postBody=None, type="GET", popup=0, authenticate=True ):
        self.logMsg("== ENTER: getURL ==",2)

        if(authenticate == True and suppress == True):
            token = self.authenticate(retreive=False)
            if(token == ""):
                self.logMsg("No auth info set and suppress is true so returning no data!")
                return ""
        
        self.TotalUrlCalls = self.TotalUrlCalls + 1
        if(self.LogCalls):
            stackString = ""
            for f in inspect.stack():
                stackString = stackString + "\r - " + str(f)
            self.TrackLog = self.TrackLog + "HTTP_API_CALL : " + url + stackString + "\r"
            
        link = ""
        https = None
        try:
            if url[0:5] == "https":
                serversplit = 2
                urlsplit = 3
            elif url[0:4] == "http":
                serversplit = 2
                urlsplit = 3
            else:
                serversplit = 0
                urlsplit = 1

            https = self.addonSettings.getSetting('https')

            server = url.split('/')[serversplit]
            urlPath = "/"+"/".join(url.split('/')[urlsplit:])

            self.logMsg("DOWNLOAD_URL = " + url,2)
            self.logMsg("server = " + str(server),2)
            self.logMsg("urlPath = " + str(urlPath),2)
            
            if(server[0:1] == ":" or server[-1:] == ":"):
                self.logMsg("No server host or port set in url")
                return ""
            
            head = self.getAuthHeader(authenticate)
            self.logMsg("HEADERS : " + str(head), level=2)
            
            if (https == 'false'):
                #xbmc.log("Https disabled.")
                conn = httplib.HTTPConnection(server, timeout=30)
            elif (https == 'true'):
                #xbmc.log("Https enabled.")
                conn = httplib.HTTPSConnection(server, timeout=30)

            # make the connection and send the request
            if(postBody != None):
                head["Content-Type"] = "application/x-www-form-urlencoded"
                head["Content-Length"] = str(len(postBody))
                self.logMsg("POST DATA : " + postBody,2)
                conn.request(method=type, url=urlPath, body=postBody, headers=head)
            else:
                conn.request(method=type, url=urlPath, headers=head)

            # get the response
            tries = 0
            while tries <= 4:
                try:
                    data = conn.getresponse()
                    break
                except:
                    # TODO: we need to work out which errors we can just quit trying immediately
                    if(xbmc.abortRequested == True):
                        return ""
                    xbmc.sleep(100)
                    if(xbmc.abortRequested == True):
                        return ""                    
                    tries += 1
            if tries == 5:
                data = conn.getresponse()
            
            self.logMsg("GET URL HEADERS : " + str(data.getheaders()), level=2)

            # process the response
            contentType = "none"
            if int(data.status) == 200:
                retData = data.read()
                contentType = data.getheader('content-encoding')
                self.logMsg("Data Len Before : " + str(len(retData)), level=2)
                if(contentType == "gzip"):
                    retData = StringIO.StringIO(retData)
                    gzipper = gzip.GzipFile(fileobj=retData)
                    link = gzipper.read()
                else:
                    link = retData
                self.logMsg("Data Len After : " + str(len(link)), level=2)
                self.logMsg("====== 200 returned =======", level=2)
                self.logMsg("Content-Type : " + str(contentType), level=2)
                self.logMsg(link, level=2)
                self.logMsg("====== 200 finished ======", level=2)

            elif ( int(data.status) == 301 ) or ( int(data.status) == 302 ):
                try: 
                    conn.close()
                except: 
                    pass
                return data.getheader('Location')

            elif int(data.status) == 401:
                WINDOW = xbmcgui.Window(10000)
                status = WINDOW.getProperty("Server_status")
                # Prevent multiple re-auth
                if (status == "401") or (status == "Auth"):
                    pass
                else:
                    # Tell UserClient token has been revoked.
                    WINDOW.setProperty("Server_status", "401")
                    error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
                    xbmc.log(error)
                    #xbmcgui.Dialog().ok(self.getString(30135),"Reason: %s" % data.reason) #self.getString(30044), 
            
                    try: 
                        conn.close()
                    except: 
                        pass
                    return ""
                
            elif int(data.status) >= 400:
                error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
                xbmc.log(error)
                stack = self.FormatException()
                self.logMsg(stack)                
                if suppress is False:
                    if popup == 0:
                        xbmc.executebuiltin("XBMC.Notification(URL error: "+ str(data.reason) +",)")
                    else:
                        xbmcgui.Dialog().ok(self.getString(30135),server)
                try: 
                    conn.close()
                except: 
                    pass
                return ""
            else:
                link = ""
        except Exception, msg:
            error = "Unable to connect to " + str(server) + " : " + str(msg)
            xbmc.log(error)
            stack = self.FormatException()
            self.logMsg(stack)
            if suppress is False:
                if popup == 0:
                    xbmc.executebuiltin("XBMC.Notification(: Connection Error: Error connecting to server,)")
                else:
                    xbmcgui.Dialog().ok(self.getString(30204), str(msg))
            pass
        else:
            try: 
                conn.close()
            except: 
                pass

        return link
        
    def FormatException(self):
        exception_list = traceback.format_stack()
        exception_list = exception_list[:-2]
        exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
        exception_list.extend(traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]))

        exception_str = "Traceback (most recent call last):\n"
        exception_str += "".join(exception_list)
        # Removing the last \n
        exception_str = exception_str[:-1]

        return exception_str          
    
    def __del__(self):
        return
        # xbmc.log("\rURL_REQUEST_REPORT : Total Calls : " + str(self.TotalUrlCalls) + "\r" + self.TrackLog)
