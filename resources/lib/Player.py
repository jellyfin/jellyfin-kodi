import xbmcaddon
import xbmcplugin
import xbmc
import xbmcgui
import os
import threading
import json
import inspect
import KodiMonitor
import Utils as utils
from DownloadUtils import DownloadUtils
from PlayUtils import PlayUtils
from ClientInformation import ClientInformation
from LibrarySync import LibrarySync
from  PlaybackUtils import PlaybackUtils
from ReadEmbyDB import ReadEmbyDB
from API import API
librarySync = LibrarySync()

# service class for playback monitoring
class Player( xbmc.Player ):

    logLevel = 0
    played_information = {}
    downloadUtils = None
    settings = None
    playStats = {}
    
    def __init__( self, *args ):
        
        self.settings = xbmcaddon.Addon(id='plugin.video.emby')
        self.downloadUtils = DownloadUtils()
        try:
            self.logLevel = int(self.settings.getSetting('logLevel'))   
        except:
            pass        
        self.printDebug("emby Service -> starting playback monitor service",1)
        self.played_information = {}
        pass    
        
    def printDebug(self, msg, level = 1):
        if(self.logLevel >= level):
            if(self.logLevel == 2):
                try:
                    xbmc.log("emby " + str(level) + " -> " + inspect.stack()[1][3] + " : " + str(msg))
                except UnicodeEncodeError:
                    xbmc.log("emby " + str(level) + " -> " + inspect.stack()[1][3] + " : " + str(msg.encode('utf-8')))
            else:
                try:
                    xbmc.log("emby " + str(level) + " -> " + str(msg))
                except UnicodeEncodeError:
                    xbmc.log("emby " + str(level) + " -> " + str(msg.encode('utf-8')))        
    
    def hasData(self, data):
        if(data == None or len(data) == 0 or data == "None"):
            return False
        else:
            return True 
    
    def stopAll(self):

        if(len(self.played_information) == 0):
            return 
            
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        self.printDebug("emby Service -> played_information : " + str(self.played_information))
        
        for item_url in self.played_information:
            data = self.played_information.get(item_url)
            
            if(data != None):
                self.printDebug("emby Service -> item_url  : " + item_url)
                self.printDebug("emby Service -> item_data : " + str(data))
                
                runtime = data.get("runtime")
                currentPosition = data.get("currentPosition")
                item_id = data.get("item_id")
                refresh_id = data.get("refresh_id")
                currentFile = data.get("currentfile")
                type = data.get("Type")

                if(currentPosition != None and self.hasData(runtime)):
                    runtimeTicks = int(runtime)
                    self.printDebug("emby Service -> runtimeticks:" + str(runtimeTicks))
                    percentComplete = (currentPosition * 10000000) / runtimeTicks
                    markPlayedAt = float(90) / 100    

                    self.printDebug("emby Service -> Percent Complete:" + str(percentComplete) + " Mark Played At:" + str(markPlayedAt))
                    self.stopPlayback(data)
                    
                if(refresh_id != None):
                    #report updates playcount and resume status to Kodi and MB3
                    librarySync.updatePlayCount(item_id)
                    
                
        self.played_information.clear()
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)

        # stop transcoding - todo check we are actually transcoding?
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        url = "%s/mediabrowser/Videos/ActiveEncodings" % server  
        url = url + '?DeviceId=' + txt_mac
        self.downloadUtils.downloadUrl(url, type="DELETE")           
    
    def stopPlayback(self, data):
        self.printDebug("stopPlayback called")
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        
        item_id = data.get("item_id")
        audioindex = data.get("AudioStreamIndex")
        subtitleindex = data.get("SubtitleStreamIndex")
        playMethod = data.get("playmethod")
        currentPosition = data.get("currentPosition")
        positionTicks = str(int(currentPosition * 10000000))
        
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)

        url = "%s/mediabrowser/Sessions/Playing/Stopped" % server  
            
        url = url + "?itemId=" + item_id

        url = url + "&canSeek=true"
        url = url + "&PlayMethod=" + playMethod
        url = url + "&QueueableMediaTypes=Video"
        url = url + "&MediaSourceId=" + item_id
        url = url + "&PositionTicks=" + positionTicks   
        if(audioindex != None and audioindex!=""):
          url = url + "&AudioStreamIndex=" + audioindex
            
        if(subtitleindex != None and subtitleindex!=""):
          url = url + "&SubtitleStreamIndex=" + subtitleindex
            
        self.downloadUtils.downloadUrl(url, postBody="", type="POST")    
    
    
    def reportPlayback(self):
        self.printDebug("reportPlayback Called",2)
        
        currentFile = xbmc.Player().getPlayingFile()
        
        #TODO need to change this to use the one in the data map
        playTime = xbmc.Player().getTime()
        
        data = self.played_information.get(currentFile)
        
        # only report playback if emby has initiated the playback (item_id has value)
        if(data != None and data.get("item_id") != None):
            addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
            
            item_id = data.get("item_id")
            audioindex = data.get("AudioStreamIndex")
            subtitleindex = data.get("SubtitleStreamIndex")
            playMethod = data.get("playmethod")
            paused = data.get("paused")

            WINDOW = xbmcgui.Window(10000)
            username = WINDOW.getProperty('currUser')
            server = WINDOW.getProperty('server%s' % username)
            
            url = "%s/mediabrowser/Sessions/Playing/Progress" % server  
                
            url = url + "?itemId=" + item_id

            url = url + "&canSeek=true"
            url = url + "&PlayMethod=" + playMethod
            url = url + "&QueueableMediaTypes=Video"
            url = url + "&MediaSourceId=" + item_id
            
            url = url + "&PositionTicks=" + str(int(playTime * 10000000))   
                
            if(audioindex != None and audioindex!=""):
              url = url + "&AudioStreamIndex=" + audioindex
                
            if(subtitleindex != None and subtitleindex!=""):
              url = url + "&SubtitleStreamIndex=" + subtitleindex
            
            if(paused == None):
                paused = "false"
            url = url + "&IsPaused=" + paused
           
            self.downloadUtils.downloadUrl(url, postBody="", type="POST")
    
    def onPlayBackPaused( self ):
        currentFile = xbmc.Player().getPlayingFile()
        self.printDebug("PLAYBACK_PAUSED : " + currentFile,2)
        if(self.played_information.get(currentFile) != None):
            self.played_information[currentFile]["paused"] = "true"
        self.reportPlayback()
    
    def onPlayBackResumed( self ):
        currentFile = xbmc.Player().getPlayingFile()
        self.printDebug("PLAYBACK_RESUMED : " + currentFile,2)
        if(self.played_information.get(currentFile) != None):
            self.played_information[currentFile]["paused"] = "false"
        self.reportPlayback()
    
    def onPlayBackSeek( self, time, seekOffset ):
        self.printDebug("PLAYBACK_SEEK",2)
        self.reportPlayback()
        
    def onPlayBackStarted( self ):
        # Will be called when xbmc starts playing a file
        WINDOW = xbmcgui.Window( 10000 )
        self.stopAll()
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        xbmcplayer = xbmc.Player()
        
        if xbmcplayer.isPlaying():
            currentFile = xbmcplayer.getPlayingFile()
            self.printDebug("emby Service -> onPlayBackStarted : " + currentFile, 0)
            
            # we may need to wait until the info is available
            item_id = WINDOW.getProperty(currentFile + "item_id")
            tryCount = 0
            while(item_id == None or item_id == ""):
                xbmc.sleep(500)
                item_id = WINDOW.getProperty(currentFile + "item_id")
                tryCount += 1
                if(tryCount == 20): # try 20 times or about 10 seconds
                    return
            xbmc.sleep(500)
            
            # grab all the info about this item from the stored windows props
            # only ever use the win props here, use the data map in all other places
            runtime = WINDOW.getProperty(currentFile + "runtimeticks")
            refresh_id = WINDOW.getProperty(currentFile + "refresh_id")
            audioindex = WINDOW.getProperty(currentFile + "AudioStreamIndex")
            subtitleindex = WINDOW.getProperty(currentFile + "SubtitleStreamIndex")
            playMethod = WINDOW.getProperty(currentFile + "playmethod")
            itemType = WINDOW.getProperty(currentFile + "type")
            seekTime = WINDOW.getProperty(currentFile + "seektime")
            if seekTime != "":
                PlaybackUtils().seekToPosition(int(seekTime))
            
            if(item_id == None or len(item_id) == 0):
                self.printDebug("emby Service -> onPlayBackStarted : No info for current playing file", 0)
                return

            username = WINDOW.getProperty('currUser')
            server = WINDOW.getProperty('server%s' % username)

            url = "%s/mediabrowser/Sessions/Playing" % server

            url = url + "?itemId=" + item_id

            url = url + "&canSeek=true"
            url = url + "&PlayMethod=" + playMethod
            url = url + "&QueueableMediaTypes=Video"
            url = url + "&MediaSourceId=" + item_id
            
            if(audioindex != None and audioindex!=""):
              url = url + "&AudioStreamIndex=" + audioindex
            
            if(subtitleindex != None and subtitleindex!=""):
              url = url + "&SubtitleStreamIndex=" + subtitleindex
            
            self.printDebug("emby Service -> Sending Post Play Started : " + url, 0)
            self.downloadUtils.downloadUrl(url, postBody="", type="POST")   
            
            # save data map for updates and position calls
            data = {}
            data["runtime"] = runtime
            data["item_id"] = item_id
            data["refresh_id"] = refresh_id
            data["currentfile"] = currentFile
            data["AudioStreamIndex"] = audioindex
            data["SubtitleStreamIndex"] = subtitleindex
            data["playmethod"] = playMethod
            data["Type"] = itemType
            self.played_information[currentFile] = data
            
            self.printDebug("emby Service -> ADDING_FILE : " + currentFile, 0)
            self.printDebug("emby Service -> ADDING_FILE : " + str(self.played_information), 0)

            # log some playback stats
            if(itemType != None):
                if(self.playStats.get(itemType) != None):
                    count = self.playStats.get(itemType) + 1
                    self.playStats[itemType] = count
                else:
                    self.playStats[itemType] = 1
                    
            if(playMethod != None):
                if(self.playStats.get(playMethod) != None):
                    count = self.playStats.get(playMethod) + 1
                    self.playStats[playMethod] = count
                else:
                    self.playStats[playMethod] = 1
            
            # reset in progress position
            self.reportPlayback()
            
    def GetPlayStats(self):
        return self.playStats
        
    def onPlayBackEnded( self ):
        # Will be called when xbmc stops playing a file
        self.printDebug("emby Service -> onPlayBackEnded")
        
        #workaround when strm files are launched through the addon - mark watched when finished playing
        #TODO --> mark watched when 95% is played of the file
        WINDOW = xbmcgui.Window( 10000 )
        if WINDOW.getProperty("virtualstrm") != "":
            try:
                id = WINDOW.getProperty("virtualstrm")
                type = WINDOW.getProperty("virtualstrmtype")
                addon = xbmcaddon.Addon(id='plugin.video.emby')
                username = WINDOW.getProperty('currUser')
                userid = WINDOW.getProperty('userId%s' % username)
                server = WINDOW.getProperty('server%s' % username)
                watchedurl = "%s/mediabrowser/Users/%s/PlayedItems/%s" % (server, userid, id)
                self.downloadUtils.downloadUrl(watchedurl, postBody="", type="POST")
                librarySync.updatePlayCount(id)
            except: pass
        WINDOW.clearProperty("virtualstrm")
            
        self.stopAll()

    def onPlayBackStopped( self ):
        # Will be called when user stops xbmc playing a file
        self.printDebug("emby Service -> onPlayBackStopped")
        self.stopAll()
        
    
    def autoPlayPlayback(self):
        currentFile = xbmc.Player().getPlayingFile()
        data = self.played_information.get(currentFile)
        
        # only report playback if emby has initiated the playback (item_id has value)
        if(data != None and data.get("item_id") != None):
            addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
            
            item_id = data.get("item_id")
            type = data.get("Type")
          
            # if its an episode see if autoplay is enabled
            if addonSettings.getSetting("autoPlaySeason")=="true" and type=="Episode":
                    WINDOW = xbmcgui.Window( 10000 )
                    username = WINDOW.getProperty('currUser')
                    userid = WINDOW.getProperty('userId%s' % username)
                    server = WINDOW.getProperty('server%s' % username)
                    # add remaining unplayed episodes if applicable
                    MB3Episode = ReadEmbyDB().getItem(item_id)
                    userData = MB3Episode["UserData"]
                    if userData!=None and userData["Played"]==True:
                        pDialog = xbmcgui.DialogProgress()
                        seasonId = MB3Episode["SeasonId"]
                        url = "%s/mediabrowser/Users/%s/Items?ParentId=%s&ImageTypeLimit=1&Limit=1&SortBy=SortName&SortOrder=Ascending&Filters=IsUnPlayed&IncludeItemTypes=Episode&IsVirtualUnaired=false&Recursive=true&IsMissing=False&format=json" % (server, userid, seasonId)
                        jsonData = self.downloadUtils.downloadUrl(url, suppress=False, popup=1 )     
                        if(jsonData != ""):
                            seasonData = json.loads(jsonData)
                            if seasonData.get("Items") != None:
                                item = seasonData.get("Items")[0]
                                pDialog.create("Auto Play next episode", str(item.get("ParentIndexNumber")) + "x" + str(item.get("IndexNumber")) + ". " + item["Name"] + " found","Cancel to stop automatic play")
                                count = 0
                                while(pDialog.iscanceled()==False and count < 10):
                                    xbmc.sleep(1000)
                                    count += 1
                                    progress = count * 10
                                    remainingsecs = 10 - count
                                    pDialog.update(progress, str(item.get("ParentIndexNumber")) + "x" + str(item.get("IndexNumber")) + ". " + item["Name"] + " found","Cancel to stop automatic play", str(remainingsecs) + " second(s) until auto dismiss")
                                
                                pDialog.close()
                        
                            if pDialog.iscanceled()==False:
                                playTime = xbmc.Player().getTime()
                                totalTime = xbmc.Player().getTotalTime()
                                while xbmc.Player().isPlaying() and (totalTime-playTime > 2):
                                    xbmc.sleep(500)
                                    playTime = xbmc.Player().getTime()
                                    totalTime = xbmc.Player().getTotalTime()
                                
                                PlaybackUtils().PLAYAllEpisodes(seasonData.get("Items"))  