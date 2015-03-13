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
import Utils as utils
import encodings
import time
import traceback

addonSettings = xbmcaddon.Addon(id='plugin.video.mb3sync')
getString = addonSettings.getLocalizedString
    
class DownloadUtils():

    logLevel = 0
    getString = None
    LogCalls = False
    TrackLog = ""
    TotalUrlCalls = 0
    
    def __init__(self, *args):
        pass

    def getServer(self):
        port = addonSettings.getSetting('port')
        host = addonSettings.getSetting('ipaddress')    
        return host + ":" + port
    
    def getUserId(self, suppress=True):

        WINDOW = xbmcgui.Window( 10000 )
        port = addonSettings.getSetting('port')
        host = addonSettings.getSetting('ipaddress')
        userName = addonSettings.getSetting('username')
        
        userid = WINDOW.getProperty("userid" + userName)

        if(userid != None and userid != ""):
            utils.logMsg("MB3 Sync","DownloadUtils -> Returning saved UserID : " + userid + "UserName: " + userName)
            return userid
    
        utils.logMsg("MB3 Sync","Looking for user name: " + userName)

        authOk = self.authenticate()
        if(authOk == ""):
            if(suppress == False):
                xbmcgui.Dialog().ok(getString(30044), getString(30044))
            return ""

        userid = WINDOW.getProperty("userid"+ userName)
        if(userid == "" and suppress == False):
            xbmcgui.Dialog().ok(getString(30045),getString(30045))

        utils.logMsg("MB3 Sync","userid : " + userid)         
        self.postcapabilities()
        
        return userid
        
    def postcapabilities(self):
        utils.logMsg("MB3 Sync","postcapabilities called")
        
        # Set Capabilities
        mb3Port = addonSettings.getSetting('port')
        mb3Host = addonSettings.getSetting('ipaddress')
        clientInfo = ClientInformation()
        machineId = clientInfo.getMachineId()
        
        # get session id
        url = "http://" + mb3Host + ":" + mb3Port + "/mediabrowser/Sessions?DeviceId=" + machineId + "&format=json"
        utils.logMsg("MB3 Sync","Session URL : " + url);
        jsonData = self.downloadUrl(url)
        utils.logMsg("MB3 Sync","Session JsonData : " + jsonData)
        result = json.loads(jsonData)
        utils.logMsg("MB3 Sync","Session JsonData : " + str(result))
        sessionId = result[0].get("Id")
        utils.logMsg("MB3 Sync","Session Id : " + str(sessionId))
        
        # post capability data
        playableMediaTypes = "Audio,Video,Photo"
        supportedCommands = "Play,Playstate,DisplayContent,GoHome,SendString,GoToSettings,DisplayMessage,PlayNext"
        
        url = "http://" + mb3Host + ":" + mb3Port + "/mediabrowser/Sessions/Capabilities?Id=" + sessionId + "&PlayableMediaTypes=" + playableMediaTypes + "&SupportedCommands=" + supportedCommands
        
        postData = {}
        #postData["Id"] = sessionId;
        #postData["PlayableMediaTypes"] = "Video";
        #postData["SupportedCommands"] = "MoveUp";
        stringdata = json.dumps(postData)
        utils.logMsg("MB3 Sync","Capabilities URL : " + url);
        utils.logMsg("MB3 Sync","Capabilities Data : " + stringdata)
        
        self.downloadUrl(url, postBody=stringdata, type="POST")

    def authenticate(self):    
        WINDOW = xbmcgui.Window( 10000 )
        token = WINDOW.getProperty("AccessToken"+addonSettings.getSetting('username'))
        if(token != None and token != ""):
            utils.logMsg("MB3 Sync","DownloadUtils -> Returning saved AccessToken for user : " + addonSettings.getSetting('username') + " token: "+ token)
            return token
        
        port = addonSettings.getSetting("port")
        host = addonSettings.getSetting("ipaddress")
        if(host == None or host == "" or port == None or port == ""):
            return ""
            
        url = "http://" + addonSettings.getSetting("ipaddress") + ":" + addonSettings.getSetting("port") + "/mediabrowser/Users/AuthenticateByName?format=json"
    
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        version = clientInfo.getVersion()

        deviceName = addonSettings.getSetting('deviceName')
        deviceName = deviceName.replace("\"", "_")

        authString = "Mediabrowser Client=\"Kodi\",Device=\"" + deviceName + "\",DeviceId=\"" + txt_mac + "\",Version=\"" + version + "\""
        headers = {'Accept-encoding': 'gzip', 'Authorization' : authString}
        
        if addonSettings.getSetting('password') !=None and  addonSettings.getSetting('password') !='':   
            sha1 = hashlib.sha1(addonSettings.getSetting('password'))
            sha1 = sha1.hexdigest()
        else:
            sha1 = 'da39a3ee5e6b4b0d3255bfef95601890afd80709'
        
        messageData = "username=" + addonSettings.getSetting('username') + "&password=" + sha1

        resp = self.downloadUrl(url, postBody=messageData, type="POST", authenticate=False, suppress=True)

        result = None
        accessToken = None
        try:
            result = json.loads(resp)
            accessToken = result.get("AccessToken")
        except:
            pass

        if(result != None and accessToken != None):
            utils.logMsg("MB3 Sync","User Authenticated : " + accessToken)
            WINDOW.setProperty("AccessToken"+addonSettings.getSetting('username'), accessToken)
            WINDOW.setProperty("userid"+addonSettings.getSetting('username'), result.get("User").get("Id"))
            WINDOW.setProperty("mb3_authenticated", "true")
            return accessToken
        else:
            utils.logMsg("MB3 Sync","User NOT Authenticated")
            WINDOW.setProperty("AccessToken"+addonSettings.getSetting('username'), "")
            WINDOW.setProperty("mb3_authenticated", "false")
            return ""            

    def getArtwork(self, data, type, index = "0", userParentInfo = False):

        id = data.get("Id")
        getSeriesData = False
        userData = data.get("UserData") 

        if type == "tvshow.poster": # Change the Id to the series to get the overall series poster
            if data.get("Type") == "Season" or data.get("Type")== "Episode":
                id = data.get("SeriesId")
                getSeriesData = True
        elif type == "poster" and data.get("Type") == "Episode" and addonSettings.getSetting('useSeasonPoster')=='true': # Change the Id to the Season to get the season poster
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

        if addonSettings.getSetting('showArtIndicators')=='true': # add watched, unplayedcount and percentage played indicators to posters
            if (originalType =="Primary" or  originalType =="Backdrop" or  originalType =="Banner") and data.get("Type") != "Episode":
                if originalType =="Backdrop" and index == "0" and data.get("BackdropImageTags") != None:
                  totalbackdrops = len(data.get("BackdropImageTags"))
                  if totalbackdrops != 0:
                    index = str(randrange(0,totalbackdrops))
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)


                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)

            elif originalType =="Primary2":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "338"
                    width = "226"
                    
            elif originalType =="Primary3" or originalType == "SeriesPrimary":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                   
            
            elif originalType =="Primary4":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "270"
                    width = "180"    
                    
            elif type =="Primary" and data.get("Type") == "Episode":
                if userData != None:

                    UnWatched = 0 if userData.get("UnplayedItemCount")==None else userData.get("UnplayedItemCount")        

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
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

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
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

                    if UnWatched <> 0 and addonSettings.getSetting('showUnplayedIndicators')=='true':
                        query = query + "&UnplayedCount=" + str(UnWatched)

                    if(userData != None and userData.get("Played") == True and addonSettings.getSetting('showWatchedIndicators')=='true'):
                        query = query + "&AddPlayedIndicator=true"

                    PlayedPercentage = 0 if userData.get("PlayedPercentage")==None else userData.get("PlayedPercentage")
                    if PlayedPercentage == 0 and userData!=None and userData.get("PlayedPercentage")!=None :
                        PlayedPercentage = userData.get("PlayedPercentage")
                    if (PlayedPercentage != 100 or PlayedPercentage) != 0 and addonSettings.getSetting('showPlayedPrecentageIndicators')=='true':
                        played = str(PlayedPercentage)
                        
                    height = "910"
                    width = "1620"                        
        
        if originalType =="BackdropNoIndicators" and index == "0" and data.get("BackdropImageTags") != None:
            totalbackdrops = len(data.get("BackdropImageTags"))
            if totalbackdrops != 0:
                index = str(randrange(0,totalbackdrops))
        # use the local image proxy server that is made available by this addons service
        
        port = addonSettings.getSetting('port')
        host = addonSettings.getSetting('ipaddress')
        server = host + ":" + port
        
        if addonSettings.getSetting('compressArt')=='true':
            query = query + "&Quality=90"
        
        if imageTag == None:
            imageTag = "e3ab56fe27d389446754d0fb04910a34"
        artwork = "http://" + server + "/mediabrowser/Items/" + str(id) + "/Images/" + type + "/" + index + "/" + imageTag + "/original/" + width + "/" + height + "/" + played + "?" + query
        if addonSettings.getSetting('disableCoverArt')=='true':
            artwork = artwork + "&EnableImageEnhancers=false"
        
        utils.logMsg("MB3 Sync","getArtwork : " + artwork, level=2)
        
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

        port = addonSettings.getSetting('port')
        host = addonSettings.getSetting('ipaddress')
        server = host + ":" + port

        artwork = "http://" + server + "/mediabrowser/Users/" + str(id) + "/Images/" + type  + "?Format=original"
       
        return artwork                  

    def imageUrl(self, id, type, index, width, height):
    
        port = addonSettings.getSetting('port')
        host = addonSettings.getSetting('ipaddress')
        server = host + ":" + port
        
        return "http://" + server + "/mediabrowser/Items/" + str(id) + "/Images/" + type + "/" + str(index) + "/e3ab56fe27d389446754d0fb04910a34/original/" + str(width) + "/" + str(height) + "/0"
    
    def getAuthHeader(self, authenticate=True):
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        version = clientInfo.getVersion()
        
        deviceName = addonSettings.getSetting('deviceName')
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
                    
            utils.logMsg("MB3 Sync","Authentication Header : " + str(headers))
            return headers
        
    def downloadUrl(self, url, suppress=False, postBody=None, type="GET", popup=0, authenticate=True ):
        utils.logMsg("MB3 Sync","== ENTER: getURL ==")
        
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

            utils.logMsg("MB3 Sync","DOWNLOAD_URL = " + url)
            utils.logMsg("MB3 Sync","server = "+str(server), level=2)
            utils.logMsg("MB3 Sync","urlPath = "+str(urlPath), level=2)
            
            conn = httplib.HTTPConnection(server, timeout=5)
            
            head = self.getAuthHeader(authenticate)
            utils.logMsg("MB3 Sync","HEADERS : " + str(head), level=1)

            # make the connection and send the request
            if(postBody != None):
                head["Content-Type"] = "application/x-www-form-urlencoded"
                head["Content-Length"] = str(len(postBody))
                utils.logMsg("MB3 Sync","POST DATA : " + postBody)
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
            
            utils.logMsg("MB3 Sync","GET URL HEADERS : " + str(data.getheaders()), level=2)

            # process the response
            contentType = "none"
            if int(data.status) == 200:
                retData = data.read()
                contentType = data.getheader('content-encoding')
                utils.logMsg("MB3 Sync","Data Len Before : " + str(len(retData)), level=2)
                if(contentType == "gzip"):
                    retData = StringIO.StringIO(retData)
                    gzipper = gzip.GzipFile(fileobj=retData)
                    link = gzipper.read()
                else:
                    link = retData
                utils.logMsg("MB3 Sync","Data Len After : " + str(len(link)), level=2)
                utils.logMsg("MB3 Sync","====== 200 returned =======", level=2)
                utils.logMsg("MB3 Sync","Content-Type : " + str(contentType), level=2)
                utils.logMsg("MB3 Sync",link, level=2)
                utils.logMsg("MB3 Sync","====== 200 finished ======", level=2)

            elif ( int(data.status) == 301 ) or ( int(data.status) == 302 ):
                try: 
                    conn.close()
                except: 
                    pass
                return data.getheader('Location')

            elif int(data.status) == 401:
                error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
                xbmc.log(error)
                
                WINDOW = xbmcgui.Window(10000)
                timeStamp = WINDOW.getProperty("mb3sync_LAST_USER_ERROR")
                if(timeStamp == None or timeStamp == ""):
                    timeStamp = "0"
                    
                if((int(timeStamp) + 10) < int(time.time())):
                    xbmcgui.Dialog().ok(getString(30135), getString(30044))
                    WINDOW.setProperty("mb3sync_LAST_USER_ERROR", str(int(time.time())))
                
                try: 
                    conn.close()
                except: 
                    pass
                return ""
                
            elif int(data.status) >= 400:
                error = "HTTP response error: " + str(data.status) + " " + str(data.reason)
                xbmc.log(error)
                if suppress is False:
                    if popup == 0:
                        xbmc.executebuiltin("XBMC.Notification(URL error: "+ str(data.reason) +",)")
                    else:
                        xbmcgui.Dialog().ok(getString(30135),server)
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
            utils.logMsg("MB3 Sync",stack)
            if suppress is False:
                if popup == 0:
                    xbmc.executebuiltin("XBMC.Notification(: Connection Error: Error connecting to server,)")
                else:
                    xbmcgui.Dialog().ok(getString(30204), str(msg))
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
