# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging

import xbmc
import xbmcvfs
import xbmcgui

import clientinfo
import downloadutils
import read_embyserver as embyserver
import websocket_client as wsc
from utils import window, settings, language as lang, JSONRPC

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Player(xbmc.Player):

    # Borg - multiple instances, shared state
    _shared_state = {}

    played_info = {}
    currentFile = None


    def __init__(self):

        self.__dict__ = self._shared_state

        self.clientInfo = clientinfo.ClientInfo()
        self.doUtils = downloadutils.DownloadUtils().downloadUrl
        self.emby = embyserver.Read_EmbyServer()
        self.ws = wsc.WebSocketClient()

        log.debug("Starting playback monitor.")
        xbmc.Player.__init__(self)

    def set_audio_subs(self, audio_index=None, subs_index=None):

        ''' Only for after playback started
        '''
        player = xbmc.Player()
        log.info("Setting audio: %s subs: %s", audio_index, subs_index)

        if audio_index and len(player.getAvailableAudioStreams()) > 1:
            player.setAudioStream(audio_index - 1)

        if subs_index:
            mapping = window('emby_%s.indexMapping.json' % self.current_file)

            if subs_index == -1:
                player.showSubtitles(False)

            elif mapping:
                external_index = mapping
                # If there's external subtitles added via playbackutils
                for index in external_index:
                    if external_index[index] == subs_index:
                        player.setSubtitleStream(int(index))
                        break
                else:
                    # User selected internal subtitles
                    external = len(external_index)
                    audio_tracks = len(player.getAvailableAudioStreams())
                    player.setSubtitleStream(external + subs_index - audio_tracks - 1)
            else:
                # Emby merges audio and subtitle index together
                audio_tracks = len(player.getAvailableAudioStreams())
                player.setSubtitleStream(subs_index - audio_tracks - 1)

    #@log_error()
    def onPlayBackStarted(self):
        # Will be called when xbmc starts playing a file
        self.stopAll()

        # Get current file
        try:
            currentFile = self.getPlayingFile()
            xbmc.sleep(300)
        except:
            currentFile = ""
            count = 0
            while not currentFile:
                xbmc.sleep(100)
                try:
                    currentFile = self.getPlayingFile()
                except: pass

                if count == 10: # try 5 times
                    log.info("Cancelling playback report...")
                    break
                else: count += 1

        # if we did not get the current file return
        if currentFile == "":
            return

        # process the playing file
        self.currentFile = currentFile

        # We may need to wait for info to be set in kodi monitor
        item = window('emby_%s.json' % currentFile)
        #itemId = window("emby_%s.itemid" % currentFile)
        tryCount = 0
        while not item:

            xbmc.sleep(200)
            item = window('emby_%s.json' % currentFile)
            if tryCount == 20: # try 20 times or about 10 seconds
                log.info("Could not find item, cancelling playback report...")
                break
            else: tryCount += 1

        else:
            item_id = item.get('id')
            log.info("ONPLAYBACK_STARTED: %s itemid: %s", currentFile.decode('utf-8'), item_id)

            # Only proceed if an itemId was found.
            runtime = item.get('runtime')
            refresh_id = item.get('refreshid')
            play_method = item.get('playmethod')
            item_type = item.get('type')
            playsession_id = item.get('playsession_id')
            mediasource_id = item.get('mediasource_id')


            #self.set_audio_subs(item.get('forcedaudio'), item.get('forcedsubs'))

            # Prevent manually mark as watched in Kodi monitor
            window('emby.skip.%s' % item_id, value="true")

            customseek = window('emby_customPlaylist.seektime')
            if window('emby_customPlaylist') == "true" and customseek:
                # Start at, when using custom playlist (play to Kodi from webclient)
                log.info("Seeking to: %s", customseek)
                self.seekTime(int(customseek)/10000000.0)
                window('emby_customPlaylist.seektime', clear=True)

            try:
                seekTime = self.getTime()
            except:
                # at this point we should be playing and if not then bail out
                return

            # Get playback volume
            result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
            result = result.get('result')

            volume = result.get('volume')
            muted = result.get('muted')

            # Postdata structure to send to Emby server
            url = "{server}/emby/Sessions/Playing"
            postdata = {

                'QueueableMediaTypes': "Video,Audio",
                'CanSeek': True,
                'ItemId': item_id,
                'MediaSourceId': mediasource_id or item_id,
                'PlayMethod': play_method,
                'VolumeLevel': volume,
                'PositionTicks': int(seekTime * 10000000),
                'IsMuted': muted,
                'PlaySessionId': playsession_id
            }

            # Get the current audio track and subtitles
            if play_method == "Transcode":
                # property set in PlayUtils.py
                postdata['AudioStreamIndex'] = window("%sAudioStreamIndex" % currentFile)
                postdata['SubtitleStreamIndex'] = window("%sSubtitleStreamIndex" % currentFile)
            else:
                # Get the current kodi audio and subtitles and convert to Emby equivalent
                params = {
                    'playerid': 1,
                    'properties': ["currentsubtitle","currentaudiostream","subtitleenabled"]
                }
                result = JSONRPC('Player.GetProperties').execute(params)
                tracks_data = None
                try:
                    tracks_data = json.loads(result)
                    tracks_data = tracks_data.get('result')
                except:
                    tracks_data = None

                try: # Audio tracks
                    indexAudio = tracks_data['currentaudiostream']['index']
                except:
                    indexAudio = 0

                try: # Subtitles tracks
                    indexSubs = tracks_data['currentsubtitle']['index']
                except:
                    indexSubs = 0

                try: # If subtitles are enabled
                    subsEnabled = tracks_data['subtitleenabled']
                except:
                    subsEnabled = ""

                # Postdata for the audio
                postdata['AudioStreamIndex'] = indexAudio + 1

                # Postdata for the subtitles
                if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:

                    # Number of audiotracks to help get Emby Index
                    audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                    mapping = window("emby_%s.indexMapping" % currentFile)

                    if mapping: # Set in playbackutils.py

                        log.debug("Mapping for external subtitles index: %s", mapping)
                        externalIndex = json.loads(mapping)

                        if externalIndex.get(str(indexSubs)):
                            # If the current subtitle is in the mapping
                            postdata['SubtitleStreamIndex'] = externalIndex[str(indexSubs)]
                        else:
                            # Internal subtitle currently selected
                            subindex = indexSubs - len(externalIndex) + audioTracks + 1
                            postdata['SubtitleStreamIndex'] = subindex

                    else: # Direct paths enabled scenario or no external subtitles set
                        postdata['SubtitleStreamIndex'] = indexSubs + audioTracks + 1
                else:
                    postdata['SubtitleStreamIndex'] = ""


            # Post playback to server
            log.debug("Sending POST play started: %s.", postdata)
            self.doUtils(url, postBody=postdata, action_type="POST")

            # Ensure we do have a runtime
            try:
                runtime = int(runtime)
            except ValueError:
                try:
                    runtime = int(self.getTotalTime())
                    log.info("Runtime is missing, Kodi runtime: %s" % runtime)
                except:
                    runtime = 0
                    log.info("Runtime is missing, Using Zero")

            # Save data map for updates and position calls
            data = {

                'runtime': runtime,
                'item_id': item_id,
                'mediasource_id': mediasource_id,
                'refresh_id': refresh_id,
                'currentfile': currentFile,
                'AudioStreamIndex': postdata['AudioStreamIndex'],
                'SubtitleStreamIndex': postdata['SubtitleStreamIndex'],
                'playmethod': play_method,
                'Type': item_type,
                'currentPosition': int(seekTime),
                'playsession_id': playsession_id
            }

            self.played_info[currentFile] = data
            log.info("ADDING_FILE: %s", self.played_info)

    def reportPlayback(self):
        
        log.debug("reportPlayback Called")

        # Get current file
        currentFile = self.currentFile
        data = self.played_info.get(currentFile)

        # only report playback if emby has initiated the playback (item_id has value)
        if data:
            # Get playback information
            itemId = data['item_id']
            audioindex = data['AudioStreamIndex']
            subtitleindex = data['SubtitleStreamIndex']
            playTime = data['currentPosition']
            playMethod = data['playmethod']
            paused = data.get('paused', False)
            playsession_id = data.get('playsession_id')
            mediasource_id = data.get('mediasource_id')


            # Get playback volume
            result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
            result = result.get('result')

            volume = result.get('volume')
            muted = result.get('muted')

            # Postdata for the websocketclient report
            postdata = {

                'QueueableMediaTypes': "Video",
                'CanSeek': True,
                'ItemId': itemId,
                'MediaSourceId': mediasource_id or itemId,
                'PlayMethod': playMethod,
                'PositionTicks': int(playTime * 10000000),
                'IsPaused': paused,
                'VolumeLevel': volume,
                'IsMuted': muted,
                'PlaySessionId': playsession_id
            }

            if playMethod == "Transcode":
                # Track can't be changed, keep reporting the same index
                postdata['AudioStreamIndex'] = audioindex
                postdata['AudioStreamIndex'] = subtitleindex

            else:
                # Get current audio and subtitles track
                params = {
                    'playerid': 1,
                    'properties': ["currentsubtitle","currentaudiostream","subtitleenabled"]
                }
                result = JSONRPC('Player.GetProperties').execute(params)
                result = result.get('result')

                try: # Audio tracks
                    indexAudio = result['currentaudiostream']['index']
                except (KeyError, TypeError):
                    indexAudio = 0
                
                try: # Subtitles tracks
                    indexSubs = result['currentsubtitle']['index']
                except (KeyError, TypeError):
                    indexSubs = 0

                try: # If subtitles are enabled
                    subsEnabled = result['subtitleenabled']
                except (KeyError, TypeError):
                    subsEnabled = ""

                # Postdata for the audio
                data['AudioStreamIndex'], postdata['AudioStreamIndex'] = [indexAudio + 1] * 2
                
                # Postdata for the subtitles
                if subsEnabled and len(xbmc.Player().getAvailableSubtitleStreams()) > 0:
                    
                    # Number of audiotracks to help get Emby Index
                    audioTracks = len(xbmc.Player().getAvailableAudioStreams())
                    mapping = window("emby_%s.indexMapping" % currentFile)

                    if mapping: # Set in PlaybackUtils.py
                        
                        log.debug("Mapping for external subtitles index: %s" % mapping)
                        externalIndex = json.loads(mapping)

                        if externalIndex.get(str(indexSubs)):
                            # If the current subtitle is in the mapping
                            subindex = [externalIndex[str(indexSubs)]] * 2
                            data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = subindex
                        else:
                            # Internal subtitle currently selected
                            subindex = [indexSubs - len(externalIndex) + audioTracks + 1] * 2
                            data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = subindex
                    
                    else: # Direct paths enabled scenario or no external subtitles set
                        subindex = [indexSubs + audioTracks + 1] * 2
                        data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = subindex
                else:
                    data['SubtitleStreamIndex'], postdata['SubtitleStreamIndex'] = [""] * 2

            # Report progress via websocketclient
            log.debug("Report: %s", postdata)
            self.emby.progress_report(postdata)

    #@log_error()
    def onPlayBackPaused(self):

        currentFile = self.currentFile
        log.debug("PLAYBACK_PAUSED: %s" % currentFile)

        if self.played_info.get(currentFile):

            self.played_info[currentFile]['paused'] = True
            self.played_info[currentFile]['currentPosition'] = self.getTime()
            self.reportPlayback()

    #@log_error()
    def onPlayBackResumed(self):

        currentFile = self.currentFile
        log.debug("PLAYBACK_RESUMED: %s" % currentFile)

        if self.played_info.get(currentFile):

            self.played_info[currentFile]['paused'] = False
            self.played_info[currentFile]['currentPosition'] = self.getTime()
            self.reportPlayback()

    #@log_error()
    def onPlayBackSeek(self, time, seekOffset):
        # Make position when seeking a bit more accurate
        currentFile = self.currentFile
        log.debug("PLAYBACK_SEEK: %s" % currentFile)

        if self.played_info.get(currentFile):
            position = None
            try:
                position = self.getTime()
            except:
                pass

            if position is not None:
                self.played_info[currentFile]['currentPosition'] = position
                self.reportPlayback()
    
    #@log_error()
    def onPlayBackStopped(self):
        # Will be called when user stops xbmc playing a file
        log.debug("ONPLAYBACK_STOPPED")
        window('emby_customPlaylist.seektime', clear=True)
        self.stopAll()

    #@log_error()
    def onPlayBackEnded(self):
        # Will be called when xbmc stops playing a file
        log.debug("ONPLAYBACK_ENDED")
        window('emby_customPlaylist.seektime', clear=True)
        self.stopAll()

    def stopAll(self):

        if not self.played_info:
            return
            
        log.info("Played_information: %s" % self.played_info)
        # Process each items
        for item in self.played_info:
            
            data = self.played_info.get(item)
            if data:
                
                log.debug("Item path: %s" % item)
                log.debug("Item data: %s" % data)

                runtime = data['runtime']
                currentPosition = data['currentPosition']
                itemid = data['item_id']
                refresh_id = data['refresh_id']
                currentFile = data['currentfile']
                media_type = data['Type']
                playMethod = data['playmethod']

                window('emby.skip.%s' % itemid, value="true")

                self.stop_playback(data)

                if currentPosition and runtime:
                    try:
                        if window('emby.external'):
                            window('emby.external', clear=True)
                            raise ValueError

                        percentComplete = (currentPosition * 10000000) / int(runtime)
                    except ZeroDivisionError:
                        # Runtime is 0.
                        percentComplete = 0
                    except ValueError:
                        percentComplete = 100
                        
                    markPlayedAt = float(settings('markPlayed')) / 100
                    log.info("Percent complete: %s Mark played at: %s"
                        % (percentComplete, markPlayedAt))

                    # Send the delete action to the server.
                    offerDelete = False

                    if media_type == "Episode" and settings('deleteTV') == "true":
                        offerDelete = True
                    elif media_type == "Movie" and settings('deleteMovies') == "true":
                        offerDelete = True

                    if settings('offerDelete') != "true":
                        # Delete could be disabled, even if the subsetting is enabled.
                        offerDelete = False

                    if percentComplete >= markPlayedAt and offerDelete:
                        resp = xbmcgui.Dialog().yesno(lang(30091), lang(33015), autoclose=120000)
                        if resp:
                            url = "{server}/emby/Items/%s?format=json" % itemid
                            log.info("Deleting request: %s" % itemid)
                            self.doUtils(url, action_type="DELETE")
                        else:
                            log.info("User skipped deletion.")

                window('emby.external_check', clear=True)

                ##### Track end of playlist
                if media_type == "Audio":
                    playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
                else:
                    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

                if int(playlist.getposition()) < 0:
                    ''' If playback is stopped within the first 30 seconds,
                        Kodi doesn't consider this watched and playlist should not be cleared.
                        When the end is reached, position is -1.
                    '''
                    log.info("Clear playlist, end detected.")
                    playlist.clear()

                path = xbmc.translatePath(
                       "special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

                dirs, files = xbmcvfs.listdir(path)
                for file in files:
                    xbmcvfs.delete("%s%s" % (path, file))
    
        self.played_info.clear()
    
    def stop_playback(self, data):
        
        log.info("stop playback called.")

        position_ticks = int(data['currentPosition'] * 10000000)
        position = data['runtime'] if position_ticks and window('emby.external') else position_ticks

        self.emby.stop_playback(data['item_id'], position, data['playsession_id'], data.get('mediasource_id'))

        # Stop transcode
        if data['playmethod'] == "Transcode":
            log.info("Transcoding for %s terminated." % data['item_id'])
            url = "{server}/emby/Videos/ActiveEncodings?DeviceId=%s" % self.clientInfo.get_device_id()
            self.doUtils(url, action_type="DELETE")
