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

    logLevel = 0
    addonSettings = None
    getString = None
    LogCalls = False
    TrackLog = ""
    TotalUrlCalls = 0

    def __init__(self, *args):
        self.addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
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
                xbmc.log("mb3sync DownloadUtils -> " + str(msg))
            except UnicodeEncodeError:
                try:
                    xbmc.log("mb3sync DownloadUtils -> " + str(msg.encode('utf-8')))
                except: pass

    def getServer(self):
        port = self.addonSettings.getSetting('port')
        host = self.addonSettings.getSetting('ipaddress')    
        return host + ":" + port
    
    def getUserId(self, suppress=True):

        WINDOW = xbmcgui.Window( 10000 )
        self.addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = self.addonSettings.getSetting('port')
        host = self.addonSettings.getSetting('ipaddress')
        userName = self.addonSettings.getSetting('username')
        
        userid = WINDOW.getProperty("userid" + userName)

        if(userid != None and userid != ""):
            self.logMsg("DownloadUtils -> Returning saved (WINDOW) UserID : " + userid + "UserName: " + userName)
            return userid
            
        userid = self.addonSettings.getSetting("userid" + userName)
        if(userid != None and userid != ""):
            WINDOW.setProperty("userid" + userName, userid)
            self.logMsg("DownloadUtils -> Returning saved (SETTING) UserID : " + userid + "UserName: " + userName)
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
        mb3Port = self.addonSettings.getSetting('port')
        mb3Host = self.addonSettings.getSetting('ipaddress')
        clientInfo = ClientInformation()
        machineId = clientInfo.getMachineId()
        
        # get session id
        url = "http://" + mb3Host + ":" + mb3Port + "/mediabrowser/Sessions?DeviceId=" + machineId + "&format=json"
        self.logMsg("Session URL : " + url);
        jsonData = self.downloadUrl(url)
        self.logMsg("Session JsonData : " + jsonData)
        result = json.loads(jsonData)
        self.logMsg("Session JsonData : " + str(result))
        sessionId = result[0].get("Id")
        self.logMsg("Session Id : " + str(sessionId))
        
        # post capability data
        playableMediaTypes = "Audio,Video,Photo"
        supportedCommands = "Play,Playstate,DisplayContent,GoHome,SendString,GoToSettings,DisplayMessage,PlayNext"
        
        url = "http://" + mb3Host + ":" + mb3Port + "/mediabrowser/Sessions/Capabilities?Id=" + sessionId + "&PlayableMediaTypes=" + playableMediaTypes + "&SupportedCommands=" + supportedCommands
        
        postData = {}
        #postData["Id"] = sessionId;
        #postData["PlayableMediaTypes"] = "Video";
        #postData["SupportedCommands"] = "MoveUp";
        stringdata = json.dumps(postData)
        self.logMsg("Capabilities URL : " + url);
        self.logMsg("Capabilities Data : " + stringdata)
        
        self.downloadUrl(url, postBody=stringdata, type="POST")

    def authenticate(self, retreive=True):
    
        WINDOW = xbmcgui.Window(10000)
        self.addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
        username = self.addonSettings.getSetting('username')
        
        token = WINDOW.getProperty("AccessToken" + username)
        if(token != None and token != ""):
            self.logMsg("DownloadUtils -> Returning saved (WINDOW) AccessToken for user:" + username + " token:" + token)
            return token
        
        token = self.addonSettings.getSetting("AccessToken" + username)
        if(token != None and token != ""):
            WINDOW.setProperty("AccessToken" + username, token)
            self.logMsg("DownloadUtils -> Returning saved (SETTINGS) AccessToken for user:" + username + " token:" + token)
            return token        
        
        port = self.addonSettings.getSetting("port")
        host = self.addonSettings.getSetting("ipaddress")
        if(host == None or host == "" or host == "<none>" or port == None or port == ""):
            return ""
        
        if(retreive == False):
            return ""
        
        url = "http://" + host + ":" + port + "/mediabrowser/Users/AuthenticateByName?format=json"
    
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        version = clientInfo.getVersion()
        
        # get user info
        jsonData = self.downloadUrl("http://" + host + ":" + port + "/mediabrowser/Users/Public?format=json", authenticate=False)
        users = []
        if(jsonData != ""):
            users = json.loads(jsonData)
        userHasPassword = False
        for user in users:
            name = user.get("Name")
            if(username == name):
                if(user.get("HasPassword") == True):
                    userHasPassword = True
                break
        
        password = ""
        if(userHasPassword):
            password = xbmcgui.Dialog().input("Enter Password for user : " + username)
            
        if (password != ""):   
            sha1 = hashlib.sha1(password)
            sha1 = sha1.hexdigest()
        else:
            sha1 = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        
        messageData = "username=" + username + "&password=" + sha1

        resp = self.downloadUrl(url, postBody=messageData, type="POST", authenticate=False)

        result = None
        accessToken = None
        try:
            xbmc.log("Auth_Reponce: " + str(resp))
            result = json.loads(resp)
            accessToken = result.get("AccessToken")
        except:
            pass

        if(result != None and accessToken != None):
            userID = result.get("User").get("Id")
            self.logMsg("User Authenticated : " + accessToken)
            WINDOW.setProperty("AccessToken" + username, accessToken)
            WINDOW.setProperty("userid" + username, userID)
            self.addonSettings.setSetting("AccessToken" + username, accessToken)
            self.addonSettings.setSetting("userid" + username, userID)
            return accessToken
        else:
            self.logMsg("User NOT Authenticated")
            WINDOW.setProperty("AccessToken" + username, "")
            WINDOW.setProperty("userid" + username, "")
            self.addonSettings.setSetting("AccessToken" + username, "")
            self.addonSettings.setSetting("userid" + username, "")
            return ""            

    def getArtwork(self, data, type, index = "0", userParentInfo = False):

        id = data.get("Id")
        getSeriesData = False
        userData = data.get("UserData") 

        if type == "tvshow.poster": # Change the Id to the series to get the overall series poster
            if data.get("Type") == "Season" or data.get("Type")== "Episode":
                id = data.get("SeriesId")
                getSeriesData = True
        elif type == "poster" and data.get("Type") == "Episode" and self.addonSettings.getSetting('useSeasonPoster')=='true': # Change the Id to the Season to get the season poster
            id = data.get("SeasonId")
        if type == "poster" or type == "tvshow.poster": # Now that the Ids are right, change type to MB3 name
            type="Primary"
        if data.get("Type") == "Season":  # For seasons: primary (poster), thumb and banner get season art, rest series art
            if type != "Primary" and type != "Primary2" and type != "Primary3" and type != "Primary4" and type != "Thumb" and type != "Banner" and type!="Thumb3":
                id = data.get("SeriesId")
                getSeriesData = True
        if data.get("Type") == "Episode":  # For episodes: primary (episode thumb) gets episode art, rest series art. 
            if type != "Primary" and type != "Primary2" and type != "Primary3" and type != "Primary4":
                id = data.get("SeriesId")
                getSeriesData = True
            if type =="Primary2" or type=="Primary3" or type=="Primary4":
                id = data.get("SeasonId")
                getSeriesData = True
                if  data.get("SeasonUserData") != None:
                    userData = data.get("SeasonUserData")
        if id == None:
            id=data.get("Id")
                
        imageTag = "e3ab56fe27d389446754d0fb04910a34" # a place holder tag, needs to be in this format
        originalType = type
        if type == "Primary2" or type == "Primary3" or type == "Primary4" or type=="SeriesPrimary":
            type = "Primary"
        if type == "Backdrop2" or type=="Backdrop3" or type=="BackdropNoIndicators":
            type = "Backdrop"
        if type == "Thumb2" or type=="Thumb3":
            type = "Thumb"
        if(data.get("ImageTags") != None and data.get("ImageTags").get(type) != None):
            imageTag = data.get("ImageTags").get(type)   

        if (data.get("Type") == "Episode" or data.get("Type") == "Season") and type=="Logo":
            imageTag = data.get("ParentLogoImageTag")
        if (data.get("Type") == "Episode" or data.get("Type") == "Season") and type=="Art":
            imageTag = data.get("ParentArtImageTag")
        if (data.get("Type") == "Episode") and originalType=="Thumb3":
            imageTag = data.get("SeriesThumbImageTag")
        if (data.get("Type") == "Season") and originalType=="Thumb3" and imageTag=="e3ab56fe27d389446754d0fb04910a34" :
            imageTag = data.get("ParentThumbImageTag")
            id = data.get("SeriesId")
     
        query = ""
        height = "10000"
        width = "10000"
        played = "0"
        totalbackdrops = 0

        if self.addonSettings.getSetting('showArtIndicators')=='true': # add watched, unplayedcount and percentage played indicators to posters
            if (originalType =="Primary" or  originalType =="Backdrop" or  originalType =="Banner") and data.get("Type") != "Episode":
                if originalType =="Backdrop" and index == "0" and data.get("BackdropImageTags") != None:
                  totalbackdrops = len(data.get("BackdropImageTags"))
                  if totalbackdrops != 0:
                    index = str(randrange(0,totalbackdrops))
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)


                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)

            elif originalType =="Primary2":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "338"
                    width = "226"
                    
            elif originalType =="Primary3" or originalType == "SeriesPrimary":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                   
            
            elif originalType =="Primary4":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "270"
                    width = "180"    
                    
            elif type =="Primary" and data.get("Type") == "Episode":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "410"
                    width = "770"
                                   
                    
            elif originalType =="Backdrop2" or originalType =="Thumb2" and data.get("Type") != "Episode":
                if originalType =="Backdrop2" and data.get("BackdropImageTags") != None: 
                  totalbackdrops = len(data.get("BackdropImageTags"))
                  if totalbackdrops != 0:
                    index = str(randrange(0,totalbackdrops))
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "370"
                    width = "660"      
                    
            elif originalType =="Backdrop3" or originalType =="Thumb3" and data.get("Type") != "Episode":
                if originalType =="Backdrop3" and data.get("BackdropImageTags") != None:
                  totalbackdrops = len(data.get("BackdropImageTags"))
                  if totalbackdrops != 0:
                    index = str(randrange(0,totalbackdrops))
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and self.addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and self.addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and self.addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "910"
                    width = "1620"                        
        
        if originalType =="BackdropNoIndicators" and index == "0" and data.get("BackdropImageTags") != None:
            totalbackdrops = len(data.get("BackdropImageTags"))
            if totalbackdrops != 0:
                index = str(randrange(0,totalbackdrops))
        # use the local image proxy server that is made available by this addons service
        
        port = self.addonSettings.getSetting('port')
        host = self.addonSettings.getSetting('ipaddress')
        server = host + ":" + port
        
        if self.addonSettings.getSetting('compressArt')=='true':
            query = query + "&Quality=90"
        
        if imageTag == None:
            imageTag = "e3ab56fe27d389446754d0fb04910a34"
        artwork = "http://" + server + "/mediabrowser/Items/" + str(id) + "/Images/" + type + "/" + index + "/" + imageTag + "/original/" + width + "/" + height + "/" + played + "?" + query
        if self.addonSettings.getSetting('disableCoverArt')=='true':
            artwork = artwork + "&EnableImageEnhancers=false"
        
        self.logMsg("getArtwork : " + artwork, level=2)
        
        # do not return non-existing images
        if (    (type!="Backdrop" and imageTag=="e3ab56fe27d389446754d0fb04910a34") |  #Remember, this is the placeholder tag, meaning we didn't find a valid tag
                (type=="Backdrop" and data.get("BackdropImageTags") != None and len(data.get("BackdropImageTags")) == 0) | 
                (type=="Backdrop" and data.get("BackdropImageTag") != None and len(data.get("BackdropImageTag")) == 0)                
                ):
            if type != "Backdrop" or (type=="Backdrop" and getSeriesData==True and data.get("ParentBackdropImageTags") == None) or (type=="Backdrop" and getSeriesData!=True):
                artwork=''        
        
        return artwork
    
    def getUserArtwork(self, data, type, index = "0"):

        id = data.get("Id")

        port = self.addonSettings.getSetting('port')
        host = self.addonSettings.getSetting('ipaddress')
        server = host + ":" + port

        artwork = "http://" + server + "/mediabrowser/Users/" + str(id) + "/Images/" + type  + "?Format=original"
       
        return artwork                  

    def imageUrl(self, id, type, index, width, height):
    
        port = self.addonSettings.getSetting('port')
        host = self.addonSettings.getSetting('ipaddress')
        server = host + ":" + port
        
        return "http://" + server + "/mediabrowser/Items/" + str(id) + "/Images/" + type + "/" + str(index) + "/e3ab56fe27d389446754d0fb04910a34/original/" + str(width) + "/" + str(height) + "/0"
    
    def getAuthHeader(self, authenticate=True):
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        version = clientInfo.getVersion()
        
        deviceName = self.addonSettings.getSetting('deviceName')
        deviceName = deviceName.replace("\"", "_")

        if(authenticate == False):
            authString = "MediaBrowser Client=\"Kodi\",Device=\"" + deviceName + "\",DeviceId=\"" + txt_mac + "\",Version=\"" + version + "\""
            headers = {"Accept-encoding": "gzip", "Accept-Charset" : "UTF-8,*", "Authorization" : authString}        
            return headers
        else:
            userid = self.getUserId()
            authString = "MediaBrowser UserId=\"" + userid + "\",Client=\"Kodi\",Device=\"" + deviceName + "\",DeviceId=\"" + txt_mac + "\",Version=\"" + version + "\""
            headers = {"Accept-encoding": "gzip", "Accept-Charset" : "UTF-8,*", "Authorization" : authString}        
                
            authToken = self.authenticate()
            if(authToken != ""):
                headers["X-MediaBrowser-Token"] = authToken
                    
            self.logMsg("Authentication Header : " + str(headers))
            return headers
        
    def downloadUrl(self, url, suppress=False, postBody=None, type="GET", popup=0, authenticate=True ):
        self.logMsg("== ENTER: getURL ==")

        if(authenticate == True and suppress == True):
            token = self.authenticate(retreive=False)
            if(token == ""):
                self.logMsg("No auth info set and suppress is true so returning no data!")
                return ""
        
        suppress = False
        
        self.TotalUrlCalls = self.TotalUrlCalls + 1
        if(self.LogCalls):
            stackString = ""
            for f in inspect.stack():
                stackString = stackString + "\r - " + str(f)
            self.TrackLog = self.TrackLog + "HTTP_API_CALL : " + url + stackString + "\r"
            
        link = ""
        try:
            if url[0:4] == "http":
                serversplit = 2
                urlsplit = 3
            else:
                serversplit = 0
                urlsplit = 1

            server = url.split('/')[serversplit]
            urlPath = "/"+"/".join(url.split('/')[urlsplit:])

            self.logMsg("DOWNLOAD_URL = " + url)
            self.logMsg("server = " + str(server))
            self.logMsg("urlPath = " + str(urlPath))
            
            if(server[0:1] == ":" or server[-1:] == ":"):
                self.logMsg("No server host or port set in url")
                return ""
            
            head = self.getAuthHeader(authenticate)
            self.logMsg("HEADERS : " + str(head), level=1)
            
            conn = httplib.HTTPConnection(server, timeout=5)

            # make the connection and send the request
            if(postBody != None):
                head["Content-Type"] = "application/x-www-form-urlencoded"
                head["Content-Length"] = str(len(postBody))
                self.logMsg("POST DATA : " + postBody)
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
                error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
                xbmc.log(error)
                
                username = self.addonSettings.getSetting("username")
                WINDOW = xbmcgui.Window(10000)
                WINDOW.setProperty("AccessToken" + username, "")
                WINDOW.setProperty("userid" + username, "")
                self.addonSettings.setSetting("AccessToken" + username, "")
                self.addonSettings.setSetting("userid" + username, "")
                
                xbmcgui.Dialog().ok(self.getString(30135), self.getString(30044), "Reason : " + str(data.reason))
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
