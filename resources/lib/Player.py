# -*- coding: utf-8 -*-

#################################################################################################

import json as json

import xbmc
import xbmcgui

from DownloadUtils import DownloadUtils
from WebSocketClient import WebSocketThread
from ClientInformation import ClientInformation
from LibrarySync import LibrarySync
import Utils as utils

#################################################################################################

class Player( xbmc.Player ):

    # Borg - multiple instances, shared state
    _shared_state = {}

    xbmcplayer = xbmc.Player()
    doUtils = DownloadUtils()
    clientInfo = ClientInformation()
    ws = WebSocketThread()
    librarySync = LibrarySync()

    addonName = clientInfo.getAddonName()

    played_information = {}
    playStats = {}
    currentFile = None
    stackFiles = None
    stackElapsed = 0

    def __init__(self, *args):

        self.__dict__ = self._shared_state
        self.logMsg("Starting playback monitor.", 2)

    def logMsg(self, msg, lvl=1):
        
        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))

    def GetPlayStats(self):
        return self.playStats

    def currentStackItem(self, stackItems):
        # Only for stacked items - stack://
        xbmcplayer = self.xbmcplayer
        
        stack = stackItems.replace("stack://", "").split(" , ")
        position = xbmcplayer.getTime()
        totalRuntime = 0

        for item in stack:
            runtime = int(utils.window("%sruntimeticks" % item)) / 10000000
            # Verify the position compared to the totalRuntime for stacked items processed in loop so far.
            if position < (runtime + totalRuntime):
                self.stackElapsed = totalRuntime
                self.currentFile = item
                return item
            else:
                totalRuntime += runtime

    def onPlayBackStarted( self ):
        # Will be called when xbmc starts playing a file
        xbmcplayer = self.xbmcplayer
        self.stopAll()
        
        # Get current file - if stack://, get currently playing item
        currentFile = xbmcplayer.getPlayingFile()
        if "stack://" in currentFile:
            self.stackFiles = currentFile
            currentFile = self.currentStackItem(currentFile)
        else:
            self.stackFiles = None
            self.currentFile = currentFile
            self.stackElapsed = 0

        self.logMsg("ONPLAYBACK_STARTED: %s" % currentFile, 0)
        
        # We may need to wait for info to be set in kodi monitor
        itemId = utils.window("%sitem_id" % currentFile)
        tryCount = 0
        while not itemId:
            
            xbmc.sleep(500)
            itemId = utils.window("%sitem_id" % currentFile)
            if tryCount == 20: # try 20 times or about 10 seconds
                break
            else: tryCount += 1
        
        else:
            # Only proceed if an itemId was found.
            runtime = utils.window("%sruntimeticks" % currentFile)
            refresh_id = utils.window("%srefresh_id" % currentFile)
            playMethod = utils.window("%splaymethod" % currentFile)
            itemType = utils.window("%stype" % currentFile)
            mapping = utils.window("%sIndexMapping" % currentFile)
            seekTime = xbmc.Player().getTime()

            self.logMsg("Mapping for subtitles index: %s" % mapping, 2)

            # Get playback volume
            volume_query = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume","muted"]}, "id": 1}'
            result = xbmc.executeJSONRPC(volume_query)
            result = json.loads(result)
            volume = result.get('result').get('volume')
            muted = result.get('result').get('muted')

            url = "{server}/mediabrowser/Sessions/Playing"
            postdata = {

                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': itemId,
                'MediaSourceId': itemId,
                'PlayMethod': playMethod,
                'VolumeLevel': volume,
                'PositionTicks': int(seekTime * 10000000) - int(self.stackElapsed * 10000000),
                'IsMuted': muted
            }

            # Get the current audio track and subtitles
            if playMethod == "Transcode":
                # property set in PlayUtils.py
                postdata['AudioStreamIndex'] = utils.window("%sAudioStreamIndex" % currentFile)
                postdata['SubtitleStreamIndex'] = utils.window("%sSubtitleStreamIndex" % currentFile)

            else:
                track_query = '{"jsonrpc": "2.0", "method": "Player.GetProperties",  "params": {"playerid": 1,"properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]} , "id": 1}'
                result = xbmc.executeJSONRPC(track_query)
                result = json.loads(result)
                
                # Audio tracks
                indexAudio = result.get('result', 0)
                if indexAudio:
                    indexAudio = indexAudio.get('currentaudiostream', {}).get('index', 0)
                # Subtitles tracks
                indexSubs = result.get('result', 0)
                if indexSubs:
                    indexSubs = indexSubs.get('currentsubtitle', {}).get('index', 0)
                # If subtitles are enabled
                subsEnabled = result.get('result', "")
                if subsEnabled:
                    subsEnabled = subsEnabled.get('subtitleenabled', "")
                
                # Postdata for the audio and subs tracks
                audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                postdata['AudioStreamIndex'] = indexAudio + 1
                
                if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                    
                    if mapping:
                        externalIndex = json.loads(mapping)
                    else: # Direct paths scenario
                        externalIndex = ""

                    if externalIndex:
                        # If there's external subtitles added via PlaybackUtils
                        if externalIndex.get(str(indexSubs)):
                            # If the current subtitle is in the mapping
                            postdata['SubtitleStreamIndex'] = externalIndex[str(indexSubs)]
                        else:
                            # Internal subtitle currently selected
                            external = len(externalIndex)
                            postdata['SubtitleStreamIndex'] = indexSubs - external + audioTracks + 1
                    else:
                        # No external subtitles added via PlayUtils
                        postdata['SubtitleStreamIndex'] = indexSubs + audioTracks + 1
                else:
                    postdata['SubtitleStreamIndex'] = ""
            
            # Post playback to server
            self.logMsg("Sending POST play started.", 1)
            self.doUtils.downloadUrl(url, postBody=postdata, type="POST")
            
            # save data map for updates and position calls
            data = {
                
                'runtime': runtime,
                'item_id': itemId,
                'refresh_id': refresh_id,
                'currentfile': currentFile,
                'AudioStreamIndex': postdata['AudioStreamIndex'],
                'SubtitleStreamIndex': postdata['SubtitleStreamIndex'],
                'playmethod': playMethod,
                'Type': itemType,
                'currentPosition': int(seekTime) - int(self.stackElapsed)
            }
            
            self.played_information[currentFile] = data
            self.logMsg("ADDING_FILE: %s" % self.played_information, 1)

            # log some playback stats
            '''if(itemType != None):
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
                    self.playStats[playMethod] = 1'''

    def reportPlayback(self):
        
        self.logMsg("reportPlayback Called", 2)
        xbmcplayer = self.xbmcplayer

        # Get current file
        currentFile = self.currentFile
        data = self.played_information.get(currentFile)

        # only report playback if emby has initiated the playback (item_id has value)
        if data:

            # Get playback information
            itemId = data.get("item_id")
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
            volume = result.get('result').get('volume')
            muted = result.get('result').get('muted')

            postdata = {

                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': itemId,
                'MediaSourceId': itemId,
                'PlayMethod': playMethod,
                'IsPaused': paused,
                'VolumeLevel': volume,
                'IsMuted': muted
            }

            if playTime:
                postdata['PositionTicks'] = int(playTime * 10000000) - int(self.stackElapsed * 10000000)

            if playMethod == "Transcode":

                data['AudioStreamIndex'] = audioindex
                data['SubtitleStreamIndex'] = subtitleindex

            else:
                # Get current audio and subtitles track
                track_query = '{"jsonrpc": "2.0", "method": "Player.GetProperties",  "params": {"playerid":1,"properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]} , "id": 1}'
                result = xbmc.executeJSONRPC(track_query)
                result = json.loads(result)
                # Audio tracks
                indexAudio = result.get('result', 0)
                if indexAudio:
                    indexAudio = indexAudio.get('currentaudiostream', {}).get('index', 0)
                # Subtitles tracks
                indexSubs = result.get('result', 0)
                if indexSubs:
                    indexSubs = indexSubs.get('currentsubtitle', {}).get('index', 0)
                # If subtitles are enabled
                subsEnabled = result.get('result', "")
                if subsEnabled:
                    subsEnabled = subsEnabled.get('subtitleenabled', "")

                # Convert back into an Emby index
                audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                indexAudio = indexAudio + 1

                if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                    WINDOW = xbmcgui.Window(10000)
                    mapping = WINDOW.getProperty("%sIndexMapping" % currentFile)
                    
                    if mapping:
                        externalIndex = json.loads(mapping)
                    else: # Direct paths scenario
                        externalIndex = ""

                    if externalIndex:
                        # If there's external subtitles added via PlaybackUtils
                        if externalIndex.get(str(indexSubs)):
                            # If the current subtitle is in the mapping
                            indexSubs = externalIndex[str(indexSubs)]
                        else:
                            # Internal subtitle currently selected
                            external = len(externalIndex)
                            indexSubs = indexSubs - external + audioTracks + 1
                    else:
                        # No external subtitles added via PlayUtils
                        audioTracks = len(xbmc.Player().getAvailableAudioStreams())
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

            postdata = json.dumps(postdata)
            self.logMsg("Report: %s" % postdata, 2)
            self.ws.sendProgressUpdate(postdata)

    def onPlayBackPaused( self ):

        currentFile = self.currentFile
        self.logMsg("PLAYBACK_PAUSED: %s" % currentFile, 2)

        if self.played_information.get(currentFile):
            self.played_information[currentFile]['paused'] = "true"
        
        self.reportPlayback()

    def onPlayBackResumed( self ):

        currentFile = self.currentFile
        self.logMsg("PLAYBACK_RESUMED: %s" % currentFile, 2)

        if self.played_information.get(currentFile):
            self.played_information[currentFile]['paused'] = "false"
        
        self.reportPlayback()

    def onPlayBackSeek( self, time, seekOffset ):
        
        self.logMsg("PLAYBACK_SEEK", 2)
        xbmcplayer = self.xbmcplayer
        # Make position when seeking a bit more accurate
        position = xbmcplayer.getTime()
        currentFile = self.currentFile

        if self.played_information.get(currentFile):
            self.played_information[currentFile]['currentPosition'] = position

        self.reportPlayback()
    
    def onPlayBackStopped( self ):
        # Will be called when user stops xbmc playing a file
        self.logMsg("ONPLAYBACK_STOPPED", 2)
        self.stopAll()

    def onPlayBackEnded( self ):
        # Will be called when xbmc stops playing a file
        self.logMsg("ONPLAYBACK_ENDED", 2)
        self.stopAll()

    def stopAll(self):

        if not self.played_information:
            return 
            
        self.logMsg("Played_information: %s" % str(self.played_information), 1)
        # Process each items
        for item in self.played_information:
            
            data = self.played_information.get(item)
            if data:
                
                self.logMsg("Item path: %s" % item, 1)
                self.logMsg("Item data: %s" % str(data), 1)

                runtime = data.get('runtime')
                currentPosition = data.get('currentPosition')
                itemId = data.get('item_id')
                refresh_id = data.get('refresh_id')
                currentFile = data.get('currentfile')
                type = data.get('Type')
                playMethod = data.get('playmethod')

                if currentPosition and runtime:
                    self.logMsg("RuntimeTicks: %s" % runtime, 1)
                    percentComplete = (currentPosition * 10000000) / int(runtime)
                    markPlayedAt = float(utils.settings('markPlayed')) / 100

                    self.logMsg("Percent complete: %s Mark played at: %s" % (percentComplete, markPlayedAt))
                    if percentComplete < markPlayedAt:
                        # Do not mark as watched for Kodi Monitor
                        utils.window('played_skipWatched', value="true")

                    self.stopPlayback(data)
                    offerDelete = False

                    if type == "Episode" and utils.settings('offerDeleteTV') == "true":
                        offerDelete = True

                    elif type == "Movie" and utils.settings('offerDeleteMovies') == "true":
                        offerDelete = True

                    if percentComplete >= markPlayedAt and offerDelete:
                        # Item could be stacked, so only offer to delete the main item.
                        if not self.stackFiles or itemId == utils.window('%sitem_id' % self.stackFiles):
                            return_value = xbmcgui.Dialog().yesno("Offer Delete", "Delete %s" % data.get('currentfile').split("/")[-1], "on Emby Server?")
                            if return_value:
                                # Delete Kodi entry before Emby
                                listItem = [itemId]
                                LibrarySync().removefromDB(listItem, True)
                    
                # Stop transcoding
                if playMethod == "Transcode":
                    self.logMsg("Transcoding for %s terminated." % itemId, 1)
                    deviceId = self.clientInfo.getMachineId()
                    url = "{server}/mediabrowser/Videos/ActiveEncodings?DeviceId=%s" % deviceId
                    self.doUtils.downloadUrl(url, type="DELETE")
    
        self.played_information.clear()
    
    def stopPlayback(self, data):
        
        self.logMsg("stopPlayback called", 2)
        
        itemId = data.get('item_id')
        currentPosition = data.get('currentPosition')
        positionTicks = int(currentPosition * 10000000)

        url = "{server}/mediabrowser/Sessions/Playing/Stopped"
        postdata = {
            
            'ItemId': itemId,
            'MediaSourceId': itemId,
            'PositionTicks': positionTicks
        }
            
        self.doUtils.downloadUrl(url, postBody=postdata, type="POST")