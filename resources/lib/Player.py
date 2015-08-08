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

    audioPref = "default"
    subsPref = "default"
    
    def __init__( self, *args ):
        
        self.__dict__ = self._shared_state
        self.logMsg("Starting playback monitor service", 1)
        
    def logMsg(self, msg, lvl=1):
        
        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))

    def setAudioSubsPref(self, audio, subs):
        self.audioPref = audio
        self.subsPref = subs
    
    def hasData(self, data):
        if(data == None or len(data) == 0 or data == "None"):
            return False
        else:
            return True 
    
    def stopAll(self):

        WINDOW = xbmcgui.Window(10000)

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
                playMethod = data.get('playmethod')

                # Prevent websocket feedback
                self.WINDOW.setProperty("played_itemId", item_id)

                if(currentPosition != None and self.hasData(runtime)):
                    runtimeTicks = int(runtime)
                    self.logMsg("emby Service -> runtimeticks:" + str(runtimeTicks))
                    percentComplete = (currentPosition * 10000000) / runtimeTicks
                    markPlayedAt = float(90) / 100    

                    self.logMsg("emby Service -> Percent Complete:" + str(percentComplete) + " Mark Played At:" + str(markPlayedAt))
                    if percentComplete < markPlayedAt:
                        # Do not mark as watched
                        self.WINDOW.setProperty('played_skipWatched', 'true')

                    self.stopPlayback(data)
                    
                    offerDelete=False
                    if data.get("Type") == "Episode" and addonSettings.getSetting("offerDeleteTV")=="true":
                        offerDelete = True
                    elif data.get("Type") == "Movie" and addonSettings.getSetting("offerDeleteMovies")=="true":
                        offerDelete = True

                    if percentComplete > .80 and offerDelete == True:
                        return_value = xbmcgui.Dialog().yesno("Offer Delete", "Delete\n" + data.get("currentfile").split("/")[-1] + "\non Emby Server? ")
                        if return_value:
                            # Delete Kodi entry before Emby
                            listItem = [item_id]
                            LibrarySync().removefromDB(listItem, True)
                    
                # Stop transcoding
                if playMethod == "Transcode":
                    self.logMsg("Transcoding for %s terminated." % item_id)
                    deviceId = self.clientInfo.getMachineId()
                    url = "{server}/mediabrowser/Videos/ActiveEncodings?DeviceId=%s" % deviceId
                    self.doUtils.downloadUrl(url, type="DELETE")
                
        self.played_information.clear()
    
    def stopPlayback(self, data):
        
        self.logMsg("stopPlayback called", 2)
        
        item_id = data.get("item_id")
        currentPosition = data.get("currentPosition")
        positionTicks = int(currentPosition * 10000000)

        url = "{server}/mediabrowser/Sessions/Playing/Stopped"
        
        postdata = {
            'ItemId': item_id,
            'MediaSourceId': item_id,
            'PositionTicks': positionTicks
        } 
            
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
        if data is not None and data.get("item_id") is not None:

            # Get playback information
            item_id = data.get("item_id")
            audioindex = data.get("AudioStreamIndex")
            subtitleindex = data.get("SubtitleStreamIndex")
            playTime = data.get("currentPosition")
            playMethod = data.get("playmethod")
            paused = data.get("paused")
            
            if paused is None:
                paused = False

            # Get playback volume
            volume_query = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume","muted"]}, "id": 1}'
            result = xbmc.executeJSONRPC(volume_query)
            result = json.loads(result)
            volume = result.get(u'result').get(u'volume')
            muted = result.get(u'result').get(u'muted')

            postdata = {
                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': item_id,
                'MediaSourceId': item_id,
                'PlayMethod': playMethod,
                'IsPaused': paused,
                'VolumeLevel': volume,
                'IsMuted': muted
            }

            if playTime:
                postdata['PositionTicks'] = int(playTime * 10000000)

            if playMethod != "Transcode":
                # Get current audio and subtitles track
                track_query = '{"jsonrpc": "2.0", "method": "Player.GetProperties",  "params": {"playerid":1,"properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]} , "id": 1}'
                result = xbmc.executeJSONRPC(track_query)
                result = json.loads(result)
                indexAudio = result.get('result', "").get('currentaudiostream', "").get('index', 0)
                indexSubs = result.get('result', "").get('currentsubtitle', "").get('index', 0)
                subsEnabled = result.get('result', "").get('subtitleenabled', "")

                # Convert back into an Emby index
                audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                indexAudio = indexAudio + 1
                if subsEnabled:
                    indexSubs = indexSubs + audioTracks + 1
                else:
                    indexSubs = ""

                if audioindex == indexAudio:
                    postdata['AudioStreamIndex'] = audioindex
                else:
                    postdata['AudioStreamIndex'] = indexAudio
                    data['AudioStreamIndex'] = indexAudio

                if subtitleindex == indexSubs:
                    postdata['SubtitleStreamIndex'] = subtitleindex
                else:
                    postdata['SubtitleStreamIndex'] = indexSubs
                    data['SubtitleStreamIndex'] = indexSubs

            else:
                data['AudioStreamIndex'] = audioindex
                data['SubtitleStreamIndex'] = subtitleindex

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
        # Make position when seeking a bit more accurate
        try:
            playTime = xbmc.Player().getTime()
            currentFile = xbmc.Player().getPlayingFile()
            if(self.played_information.get(currentFile) != None):
                self.played_information[currentFile]["currentPosition"] = playTime
        except: pass
        self.reportPlayback()
        
    def onPlayBackStarted( self ):
        # Will be called when xbmc starts playing a file
        WINDOW = xbmcgui.Window(10000)
        addon = self.addon
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
            playMethod = WINDOW.getProperty(currentFile + "playmethod")
            itemType = WINDOW.getProperty(currentFile + "type")
            
            # Get playback volume
            volume_query = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume","muted"]}, "id": 1}'
            result = xbmc.executeJSONRPC(volume_query)
            result = json.loads(result)
            volume = result.get(u'result').get(u'volume')
            muted = result.get(u'result').get(u'muted')

            seekTime = xbmc.Player().getTime()

            url = "{server}/mediabrowser/Sessions/Playing"
            postdata = {
                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': item_id,
                'MediaSourceId': item_id,
                'PlayMethod': playMethod,
                'VolumeLevel': volume,
                'PositionTicks': int(seekTime * 10000000),
                'IsMuted': muted
            }

            # Get the current audio track and subtitles
            if playMethod == "Transcode":
                audioindex = WINDOW.getProperty(currentFile + "AudioStreamIndex")
                subtitleindex = WINDOW.getProperty(currentFile + "SubtitleStreamIndex")
                postdata['AudioStreamIndex'] = audioindex
                postdata['SubtitleStreamIndex'] = subtitleindex

            else:
                track_query = '{"jsonrpc": "2.0", "method": "Player.GetProperties",  "params": {"playerid": 1,"properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]} , "id": 1}'
                result = xbmc.executeJSONRPC(track_query)
                result = json.loads(result)
                indexAudio = result.get('result', "").get('currentaudiostream', "").get('index', 0)
                indexSubs = result.get('result', "").get('currentsubtitle', "").get('index', 0)
                subsEnabled = result.get('result', "").get('subtitleenabled', "")

                postdata['AudioStreamIndex'] = indexAudio + 1
                if subsEnabled:
                    audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                    postdata['SubtitleStreamIndex'] = indexSubs + audioTracks + 1
                else:
                    postdata['SubtitleStreamIndex'] = ""
            
            # Post playback to server
            self.logMsg("Sending POST play started.", 1)
            self.doUtils.downloadUrl(url, postBody=postdata, type="POST")
            
            # save data map for updates and position calls
            data = {
                'runtime': runtime,
                'item_id': item_id,
                'refresh_id': refresh_id,
                'currentfile': currentFile,
                'AudioStreamIndex': postdata['AudioStreamIndex'],
                'SubtitleStreamIndex': postdata['SubtitleStreamIndex'],
                'playmethod': playMethod,
                'Type': itemType,
                'currentPosition': int(seekTime)
            }
            self.played_information[currentFile] = data
            self.logMsg("ADDING_FILE: %s" % self.played_information, 1)

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
            #self.reportPlayback()
            
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