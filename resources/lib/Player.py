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

    def __init__(self, *args):

        self.__dict__ = self._shared_state
        self.logMsg("Starting playback monitor.", 2)

    def logMsg(self, msg, lvl=1):
        
        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, int(lvl))

    def GetPlayStats(self):
        return self.playStats

    def onPlayBackStarted( self ):
        # Will be called when xbmc starts playing a file
        xbmcplayer = self.xbmcplayer
        self.stopAll()

        # Get current file
        try:
            currentFile = xbmcplayer.getPlayingFile()
            xbmc.sleep(300)
        except:
            currentFile = ""
            count = 0
            while not currentFile:
                xbmc.sleep(100)
                try:
                    currentFile = xbmcplayer.getPlayingFile()
                except: pass

                if count == 5: # try 5 times
                    self.logMsg("Cancelling playback report...", 1)
                    break
                else: count += 1


        if currentFile:

            self.currentFile = currentFile
            
            # We may need to wait for info to be set in kodi monitor
            itemId = utils.window("%sitem_id" % currentFile)
            tryCount = 0
            while not itemId:
                
                xbmc.sleep(200)
                itemId = utils.window("%sitem_id" % currentFile)
                if tryCount == 20: # try 20 times or about 10 seconds
                    self.logMsg("Could not find itemId, cancelling playback report...", 1)
                    break
                else: tryCount += 1
            
            else:
                self.logMsg("ONPLAYBACK_STARTED: %s ITEMID: %s" % (currentFile, itemId), 0)

                # Only proceed if an itemId was found.
                runtime = utils.window("%sruntimeticks" % currentFile)
                refresh_id = utils.window("%srefresh_id" % currentFile)
                playMethod = utils.window("%splaymethod" % currentFile)
                itemType = utils.window("%stype" % currentFile)
                seekTime = xbmcplayer.getTime()


                # Get playback volume
                volume_query = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume","muted"]}, "id": 1}'
                result = xbmc.executeJSONRPC(volume_query)
                result = json.loads(result)
                result = result.get('result')

                volume = result.get('volume')
                muted = result.get('muted')

                # Postdata structure to send to Emby server
                url = "{server}/mediabrowser/Sessions/Playing"
                postdata = {

                    'QueueableMediaTypes': "Video",
                    'CanSeek': True,
                    'ItemId': itemId,
                    'MediaSourceId': itemId,
                    'PlayMethod': playMethod,
                    'VolumeLevel': volume,
                    'PositionTicks': int(seekTime * 10000000),
                    'IsMuted': muted
                }

                # Get the current audio track and subtitles
                if playMethod == "Transcode":
                    # property set in PlayUtils.py
                    postdata['AudioStreamIndex'] = utils.window("%sAudioStreamIndex" % currentFile)
                    postdata['SubtitleStreamIndex'] = utils.window("%sSubtitleStreamIndex" % currentFile)

                else:
                    # Get the current kodi audio and subtitles and convert to Emby equivalent
                    track_query = '{"jsonrpc": "2.0", "method": "Player.GetProperties",  "params": {"playerid": 1,"properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]} , "id": 1}'
                    result = xbmc.executeJSONRPC(track_query)
                    result = json.loads(result)
                    result = result.get('result')

                    try: # Audio tracks
                        indexAudio = result['currentaudiostream']['index']
                    except KeyError:
                        indexAudio = 0
                    
                    try: # Subtitles tracks
                        indexSubs = result['currentsubtitle']['index']
                    except KeyError:
                        indexSubs = 0

                    try: # If subtitles are enabled
                        subsEnabled = result['subtitleenabled']
                    except KeyError:
                        subsEnabled = ""

                    # Postdata for the audio
                    postdata['AudioStreamIndex'] = indexAudio + 1
                    
                    # Postdata for the subtitles
                    if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                        
                        # Number of audiotracks to help get Emby Index
                        audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                        mapping = utils.window("%sIndexMapping" % currentFile)

                        if mapping: # Set in PlaybackUtils.py
                            
                            self.logMsg("Mapping for external subtitles index: %s" % mapping, 2)
                            externalIndex = json.loads(mapping)

                            if externalIndex.get(str(indexSubs)):
                                # If the current subtitle is in the mapping
                                postdata['SubtitleStreamIndex'] = externalIndex[str(indexSubs)]
                            else:
                                # Internal subtitle currently selected
                                postdata['SubtitleStreamIndex'] = indexSubs - len(externalIndex) + audioTracks + 1
                        
                        else: # Direct paths enabled scenario or no external subtitles set
                            postdata['SubtitleStreamIndex'] = indexSubs + audioTracks + 1
                    else:
                        postdata['SubtitleStreamIndex'] = ""
                

                # Post playback to server
                self.logMsg("Sending POST play started: %s." % postdata, 2)
                self.doUtils.downloadUrl(url, postBody=postdata, type="POST")
                
                # Ensure we do have a runtime
                try:
                    runtime = int(runtime)
                except ValueError:
                    runtime = xbmcplayer.getTotalTime()
                    self.logMsg("Runtime is missing, grabbing runtime from Kodi player: %s" % runtime, 1)

                # Save data map for updates and position calls
                data = {
                    
                    'runtime': runtime,
                    'item_id': itemId,
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
            itemId = data['item_id']
            audioindex = data['AudioStreamIndex']
            subtitleindex = data['SubtitleStreamIndex']
            playTime = data['currentPosition']
            playMethod = data['playmethod']
            paused = data.get('paused', False)


            # Get playback volume
            volume_query = '{"jsonrpc": "2.0", "method": "Application.GetProperties", "params": {"properties": ["volume","muted"]}, "id": 1}'
            result = xbmc.executeJSONRPC(volume_query)
            result = json.loads(result)
            result = result.get('result')

            volume = result.get('volume')
            muted = result.get('muted')


            # Postdata for the websocketclient report
            postdata = {

                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': itemId,
                'MediaSourceId': itemId,
                'PlayMethod': playMethod,
                'PositionTicks': int(playTime * 10000000),
                'IsPaused': paused,
                'VolumeLevel': volume,
                'IsMuted': muted
            }

            if playMethod == "Transcode":
                # Track can't be changed, keep reporting the same index
                postdata['AudioStreamIndex'] = audioindex
                postdata['AudioStreamIndex'] = subtitleindex

            else:
                # Get current audio and subtitles track
                track_query = '{"jsonrpc": "2.0", "method": "Player.GetProperties",  "params": {"playerid":1,"properties": ["currentsubtitle","currentaudiostream","subtitleenabled"]} , "id": 1}'
                result = xbmc.executeJSONRPC(track_query)
                result = json.loads(result)
                result = result.get('result')

                try: # Audio tracks
                    indexAudio = result['currentaudiostream']['index']
                except KeyError:
                    indexAudio = 0
                
                try: # Subtitles tracks
                    indexSubs = result['currentsubtitle']['index']
                except KeyError:
                    indexSubs = 0

                try: # If subtitles are enabled
                    subsEnabled = result['subtitleenabled']
                except KeyError:
                    subsEnabled = ""

                # Postdata for the audio
                data['AudioStreamIndex'], postdata['AudioStreamIndex'] = [indexAudio + 1] * 2
                
                # Postdata for the subtitles
                if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                    
                    # Number of audiotracks to help get Emby Index
                    audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                    mapping = utils.window("%sIndexMapping" % currentFile)

                    if mapping: # Set in PlaybackUtils.py
                        
                        self.logMsg("Mapping for external subtitles index: %s" % mapping, 2)
                        externalIndex = json.loads(mapping)

                        if externalIndex.get(str(indexSubs)):
                            # If the current subtitle is in the mapping
                            data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = [externalIndex[str(indexSubs)]] * 2
                        else:
                            # Internal subtitle currently selected
                            data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = [indexSubs - len(externalIndex) + audioTracks + 1] * 2
                    
                    else: # Direct paths enabled scenario or no external subtitles set
                        data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = [indexSubs + audioTracks + 1] * 2
                else:
                    data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = [""] * 2

            # Report progress via websocketclient
            postdata = json.dumps(postdata)
            self.logMsg("Report: %s" % postdata, 2)
            self.ws.sendProgressUpdate(postdata)

    def onPlayBackPaused( self ):

        currentFile = self.currentFile
        self.logMsg("PLAYBACK_PAUSED: %s" % currentFile, 2)

        if self.played_information.get(currentFile):
            self.played_information[currentFile]['paused'] = True
        
            self.reportPlayback()

    def onPlayBackResumed( self ):

        currentFile = self.currentFile
        self.logMsg("PLAYBACK_RESUMED: %s" % currentFile, 2)

        if self.played_information.get(currentFile):
            self.played_information[currentFile]['paused'] = False
        
            self.reportPlayback()

    def onPlayBackSeek( self, time, seekOffset ):
        # Make position when seeking a bit more accurate
        currentFile = self.currentFile
        self.logMsg("PLAYBACK_SEEK: %s" % currentFile, 2)

        if self.played_information.get(currentFile):
            position = self.xbmcplayer.getTime()
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
            
        self.logMsg("Played_information: %s" % self.played_information, 1)
        # Process each items
        for item in self.played_information:
            
            data = self.played_information.get(item)
            if data:
                
                self.logMsg("Item path: %s" % item, 2)
                self.logMsg("Item data: %s" % data, 2)

                runtime = data['runtime']
                currentPosition = data['currentPosition']
                itemId = data['item_id']
                refresh_id = data['refresh_id']
                currentFile = data['currentfile']
                type = data['Type']
                playMethod = data['playmethod']

                if currentPosition and runtime:
                    percentComplete = (currentPosition * 10000000) / int(runtime)
                    markPlayedAt = float(utils.settings('markPlayed')) / 100

                    self.logMsg("Percent complete: %s Mark played at: %s" % (percentComplete, markPlayedAt), 1)
                    # Prevent manually mark as watched in Kodi monitor > WriteKodiVideoDB().UpdatePlaycountFromKodi()
                    utils.window('SkipWatched%s' % itemId, "true")

                    self.stopPlayback(data)
                    offerDelete = utils.settings('offerDelete') == "true"
                    offerTypeDelete = False

                    if type == "Episode" and utils.settings('offerDeleteTV') == "true":
                        offerTypeDelete = True

                    elif type == "Movie" and utils.settings('offerDeleteMovies') == "true":
                        offerTypeDelete = True

                    if percentComplete >= markPlayedAt and offerDelete and offerTypeDelete:
                        # Make the bigger setting be able to disable option easily.
                        self.logMsg("Offering deletion for: %s." % itemId, 1)
                        return_value = xbmcgui.Dialog().yesno("Offer Delete", "Delete %s" % currentFile.split("/")[-1], "on Emby Server?")
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
        
        itemId = data['item_id']
        currentPosition = data['currentPosition']
        positionTicks = int(currentPosition * 10000000)

        url = "{server}/mediabrowser/Sessions/Playing/Stopped"
        postdata = {
            
            'ItemId': itemId,
            'MediaSourceId': itemId,
            'PositionTicks': positionTicks
        }
            
        self.doUtils.downloadUrl(url, postBody=postdata, type="POST")