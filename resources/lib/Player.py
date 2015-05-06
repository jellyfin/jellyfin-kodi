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
from WebSocketClient import WebSocketThread
from PlayUtils import PlayUtils
from ClientInformation import ClientInformation
from LibrarySync import LibrarySync
from  PlaybackUtils import PlaybackUtils
from ReadEmbyDB import ReadEmbyDB
from API import API
from NextUpInfo import NextUpInfo
librarySync = LibrarySync()

# service class for playback monitoring
class Player( xbmc.Player ):

    # Borg - multiple instances, shared state
    _shared_state = {}
    
    xbmcplayer = xbmc.Player()
    doUtils = DownloadUtils()
    clientInfo = ClientInformation()
    ws = WebSocketThread()

    addonName = clientInfo.getAddonName()
    addonId = clientInfo.getAddonId()
    addon = xbmcaddon.Addon(id=addonId)

    WINDOW = xbmcgui.Window(10000)

    logLevel = 0
    played_information = {}
    settings = None
    playStats = {}
    
    def __init__( self, *args ):
        
        self.__dict__ = self._shared_state
        self.logMsg("Starting playback monitor service", 1)
        
    def logMsg(self, msg, lvl=1):
        
        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))      
    
    def hasData(self, data):
        if(data == None or len(data) == 0 or data == "None"):
            return False
        else:
            return True 
    
    def stopAll(self):

        self.ws.processPendingActions()
        if(len(self.played_information) == 0):
            return 
            
        addonSettings = xbmcaddon.Addon(id='plugin.video.emby')
        self.logMsg("emby Service -> played_information : " + str(self.played_information))
        
        for item_url in self.played_information:
            data = self.played_information.get(item_url)
            
            if (data is not None):
                self.logMsg("emby Service -> item_url  : " + item_url)
                self.logMsg("emby Service -> item_data : " + str(data))
                
                runtime = data.get("runtime")
                currentPosition = data.get("currentPosition")
                item_id = data.get("item_id")
                refresh_id = data.get("refresh_id")
                currentFile = data.get("currentfile")
                type = data.get("Type")

                if(currentPosition != None and self.hasData(runtime)):
                    runtimeTicks = int(runtime)
                    self.logMsg("emby Service -> runtimeticks:" + str(runtimeTicks))
                    percentComplete = (currentPosition * 10000000) / runtimeTicks
                    markPlayedAt = float(90) / 100    

                    self.logMsg("emby Service -> Percent Complete:" + str(percentComplete) + " Mark Played At:" + str(markPlayedAt))
                    self.stopPlayback(data)
                    
                #if(refresh_id != None):
                    #report updates playcount and resume status to Kodi and MB3
                    #librarySync.updatePlayCount(item_id)
                    
                
        self.played_information.clear()

        # stop transcoding - todo check we are actually transcoding?
        clientInfo = ClientInformation()
        txt_mac = clientInfo.getMachineId()
        url = "{server}/mediabrowser/Videos/ActiveEncodings"
        url = url + '?DeviceId=' + txt_mac
        self.doUtils.downloadUrl(url, type="DELETE")
    
    def stopPlayback(self, data):
        
        self.logMsg("stopPlayback called", 2)
        
        item_id = data.get("item_id")
        audioindex = data.get("AudioStreamIndex")
        subtitleindex = data.get("SubtitleStreamIndex")
        playMethod = data.get("playmethod")
        currentPosition = data.get("currentPosition")
        positionTicks = int(currentPosition * 10000000)

        url = "{server}/mediabrowser/Sessions/Playing/Stopped"
        
        postdata = {
            'QueueableMediaTypes': "Video",
            'CanSeek': True,
            'ItemId': item_id,
            'MediaSourceId': item_id,
            'PlayMethod': playMethod,
            'PositionTicks': positionTicks
        }

        if audioindex:
            postdata['AudioStreamIndex'] = audioindex

        if subtitleindex:
            postdata['SubtitleStreamIndex'] = subtitleindex    
            
        self.doUtils.downloadUrl(url, postBody=postdata, type="POST")
    
    def reportPlayback(self):
        
        self.logMsg("reportPlayback Called", 2)
        xbmcplayer = self.xbmcplayer
        
        if not xbmcplayer.isPlaying():
            self.logMsg("reportPlayback: Not playing anything so returning", 0)
            return

        currentFile = xbmcplayer.getPlayingFile()
        data = self.played_information.get(currentFile)

        # only report playback if emby has initiated the playback (item_id has value)
        if (data is not None) and (data.get("item_id") is not None):

            # Get playback information
            item_id = data.get("item_id")
            audioindex = data.get("AudioStreamIndex")
            subtitleindex = data.get("SubtitleStreamIndex")
            playTime = data.get("currentPosition")
            playMethod = data.get("playmethod")
            paused = data.get("paused")
            
            if paused is None:
                paused = False

            #url = "{server}/mediabrowser/Sessions/Playing/Progress" 
            postdata = {
                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': item_id,
                'MediaSourceId': item_id,
                'IsPaused': paused,
                'PlayMethod': playMethod
            }

            if playTime:
                postdata['PositionTicks'] = int(playTime * 10000000)

            if audioindex:
                postdata['AudioStreamIndex'] = audioindex

            if subtitleindex:
                postdata['SubtitleStreamIndex'] = subtitleindex

            postdata = json.dumps(postdata)
            self.logMsg("Report: %s" % postdata, 2)
            self.ws.sendProgressUpdate(postdata)
    
    def onPlayBackPaused( self ):
        currentFile = xbmc.Player().getPlayingFile()
        self.logMsg("PLAYBACK_PAUSED : " + currentFile,2)
        if(self.played_information.get(currentFile) != None):
            self.played_information[currentFile]["paused"] = "true"
        self.reportPlayback()
    
    def onPlayBackResumed( self ):
        currentFile = xbmc.Player().getPlayingFile()
        self.logMsg("PLAYBACK_RESUMED : " + currentFile,2)
        if(self.played_information.get(currentFile) != None):
            self.played_information[currentFile]["paused"] = "false"
        self.reportPlayback()
    
    def onPlayBackSeek( self, time, seekOffset ):
        self.logMsg("PLAYBACK_SEEK",2)
        self.reportPlayback()
        
    def onPlayBackStarted( self ):
        # Will be called when xbmc starts playing a file
        WINDOW = self.WINDOW
        xbmcplayer = self.xbmcplayer
        self.stopAll()
        
        if xbmcplayer.isPlaying():
            
            currentFile = ""
            try:
                currentFile = xbmcplayer.getPlayingFile()
            except: pass
            self.logMsg("onPlayBackStarted: %s" % currentFile, 0)
            
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
            
            username = WINDOW.getProperty('currUser')
            sessionId = WINDOW.getProperty('sessionId%s' % username)

            if seekTime != "":
                PlaybackUtils().seekToPosition(int(seekTime))
            
            if (not item_id) or (len(item_id) == 0):
                self.logMsg("onPlayBackStarted: No info for current playing file", 0)
                return

            url = "{server}/mediabrowser/Sessions/Playing"
            postdata = {
                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': item_id,
                'MediaSourceId': item_id,
                'PlayMethod': playMethod
            }

            if audioindex:
                postdata['AudioStreamIndex'] = audioindex

            if subtitleindex:
                postdata['SubtitleStreamIndex'] = subtitleindex
            
            self.logMsg("Sending POST play started.", 1)
            #self.logMsg("emby Service -> Sending Post Play Started : " + url, 0)
            self.doUtils.downloadUrl(url, postBody=postdata, type="POST")   
            
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
            
            self.logMsg("emby Service -> ADDING_FILE : " + currentFile, 0)
            self.logMsg("emby Service -> ADDING_FILE : " + str(self.played_information), 0)

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
        self.logMsg("onPlayBackEnded", 0)
        
        #workaround when strm files are launched through the addon - mark watched when finished playing
        #TODO --> mark watched when 95% is played of the file
        WINDOW = xbmcgui.Window( 10000 )
        if WINDOW.getProperty("virtualstrm") != "":
            try:
                id = WINDOW.getProperty("virtualstrm")
                type = WINDOW.getProperty("virtualstrmtype")
                watchedurl = "{server}/mediabrowser/Users/{UserId}/PlayedItems/%s" % id
                self.doUtils.downloadUrl(watchedurl, postBody="", type="POST")
                librarySync.updatePlayCount(id)
            except: pass
        WINDOW.clearProperty("virtualstrm")
            
        self.stopAll()

    def onPlayBackStopped( self ):
        # Will be called when user stops xbmc playing a file
        self.logMsg("onPlayBackStopped", 0)
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
                        url = "{server}/mediabrowser/Users/{UserId}/Items?ParentId=%s&ImageTypeLimit=1&Limit=1&SortBy=SortName&SortOrder=Ascending&Filters=IsUnPlayed&IncludeItemTypes=Episode&IsVirtualUnaired=false&Recursive=true&IsMissing=False&format=json" % seasonId
                        jsonData = self.doUtils.downloadUrl(url)     
                        if(jsonData != ""):
                            seasonData = jsonData
                            if seasonData.get("Items") != None:
                                item = seasonData.get("Items")[0]
                                item = ReadEmbyDB().getItem(item["Id"])
                                nextUpPage = NextUpInfo("NextUpInfo.xml", addonSettings.getAddonInfo('path'), "default", "720p")
                                nextUpPage.setItem(item)
                                playTime = xbmc.Player().getTime()
                                totalTime = xbmc.Player().getTotalTime()
                                nextUpPage.show()
                                playTime = xbmc.Player().getTime()
                                totalTime = xbmc.Player().getTotalTime()
                                while xbmc.Player().isPlaying() and (totalTime-playTime > 1) and not nextUpPage.isCancel() and not nextUpPage.isWatchNow():
                                    xbmc.sleep(100)
                                    playTime = xbmc.Player().getTime()
                                    totalTime = xbmc.Player().getTotalTime()
                                nextUpPage.close()
                                if not nextUpPage.isCancel():
                                    PlaybackUtils().PLAY(item)
                            
