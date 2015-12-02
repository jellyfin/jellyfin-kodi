# -*- coding: utf-8 -*-

#################################################################################################

import xbmc
import xbmcgui
import xbmcvfs

from ClientInformation import ClientInformation
import Utils as utils

#################################################################################################

class PlayUtils():

    clientInfo = ClientInformation()
    addonName = clientInfo.getAddonName()

    def logMsg(self, msg, lvl=1):
        
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))

    def getPlayUrl(self, server, id, result):

        if self.isDirectPlay(result,True):
            # Try direct play
            playurl = self.directPlay(result)
            if playurl:
                self.logMsg("File is direct playing.", 1)
                utils.window("%splaymethod" % playurl.encode('utf-8'), value="DirectPlay")

        elif self.isDirectStream(result):
            # Try direct stream
            playurl = self.directStream(result, server, id)
            if playurl:
                self.logMsg("File is direct streaming.", 1)
                utils.window("%splaymethod" % playurl, value="DirectStream")

        elif self.isTranscoding(result):
            # Try transcoding
            playurl = self.transcoding(result, server, id)
            if playurl:
                self.logMsg("File is transcoding.", 1)
                utils.window("%splaymethod" % playurl, value="Transcode")
        
        else: # Error
            utils.window("playurlFalse", value="true")
            return

        return playurl.encode('utf-8')


    def isDirectPlay(self, result, dialog = False):
        # Requirements for Direct play:
        # FileSystem, Accessible path
        if utils.settings('playFromStream') == "true":
            # User forcing to play via HTTP instead of SMB
            self.logMsg("Can't direct play: Play from HTTP is enabled.", 1)
            return False

        # Avoid H265 1080p
        if result['MediaSources'][0]['Name'].startswith("1080P/H265"):
            self.logMsg("Skip direct play for 1080P/H265 since format playback is not stable.", 1)
            return False

        canDirectPlay = result['MediaSources'][0]['SupportsDirectPlay']
        # Make sure it's supported by server
        if not canDirectPlay:
            self.logMsg("Can't direct play: Server does not allow or support it.", 1)
            return False

        location = result['LocationType']
        # File needs to be "FileSystem"
        if 'FileSystem' in location:
            # Verify if path is accessible
            if self.fileExists(result):
                return True
            else:
                self.logMsg("Unable to direct play. Verify the following path is accessible by the device: %s. You might also need to add SMB credentials in the add-on settings." % result['MediaSources'][0]['Path'], 1)
                if dialog:
                    
                    failCount = int(utils.settings('directSteamFailedCount'))
                    self.logMsg("Direct Play failCount: %s." % failCount, 1)
                    
                    if failCount < 2:
                        # Let user know that direct play failed
                        utils.settings('directSteamFailedCount', value=str(failCount + 1))
                        xbmcgui.Dialog().notification("Emby server", "Unable to direct play. Verify your log for more information.", icon="special://home/addons/plugin.video.emby/icon.png", sound=False)
                    elif utils.settings('playFromStream') != "true":
                        # Permanently set direct stream as true
                        utils.settings('playFromStream', value="true")
                        xbmcgui.Dialog().notification("Emby server", "Enabled play from HTTP in add-on settings.", icon="special://home/addons/plugin.video.emby/icon.png", sound=False)

                return False

    def directPlay(self, result):

        try:
            playurl = result['MediaSources'][0]['Path']
        except KeyError:
            playurl = result['Path']

        if 'VideoType' in result:
            # Specific format modification
            if 'Dvd' in result['VideoType']:
                playurl = "%s/VIDEO_TS/VIDEO_TS.IFO" % playurl
            elif 'BluRay' in result['VideoType']:
                playurl = "%s/BDMV/index.bdmv" % playurl

        # Network - SMB protocol
        if "\\\\" in playurl:
            smbuser = utils.settings('smbusername')
            smbpass = utils.settings('smbpassword')
            # Network share
            if smbuser:
                playurl = playurl.replace("\\\\", "smb://%s:%s@" % (smbuser, smbpass))
            else:
                playurl = playurl.replace("\\\\", "smb://")
            playurl = playurl.replace("\\", "/")
            
        if "apple.com" in playurl:
            USER_AGENT = "QuickTime/7.7.4"
            playurl += "?|User-Agent=%s" % USER_AGENT

        return playurl


    def isDirectStream(self, result):
        # Requirements for Direct stream:
        # FileSystem or Remote, BitRate, supported encoding

        # Avoid H265 1080p
        if item['MediaSources'][0]['Name'].startswith("1080P/H265"):
            self.logMsg("Skip direct stream for 1080P/H265 since format playback is not stable.", 1)
            return False
            
        canDirectStream = result['MediaSources'][0]['SupportsDirectStream']
        # Make sure it's supported by server
        if not canDirectStream:
            return False

        location = result['LocationType']
        # File can be FileSystem or Remote, not Virtual
        if 'Virtual' in location:
            self.logMsg("File location is virtual. Can't proceed.", 1)
            return False

        # Verify BitRate
        if not self.isNetworkQualitySufficient(result):
            self.logMsg("The network speed is insufficient to playback the file.", 1)
            return False

        return True
  
    def directStream(self, result, server, id, type = "Video"):

        if result['Path'].endswith('.strm'):
            # Allow strm loading when direct streaming
            playurl = self.directPlay(result)
            return playurl
        
        if "ThemeVideo" in type:
            playurl = "%s/mediabrowser/Videos/%s/stream?static=true" % (server, id)

        elif "Video" in type:
            playurl = "%s/mediabrowser/Videos/%s/stream?static=true" % (server, id)
        
        elif "Audio" in type:
            playurl = "%s/mediabrowser/Audio/%s/stream.mp3" % (server, id)
        
        return playurl


    def isTranscoding(self, result):
        # Last resort, no requirements
        # BitRate
        canTranscode = result['MediaSources'][0]['SupportsTranscoding']
        # Make sure it's supported by server
        if not canTranscode:
            return False

        location = result['LocationType']
        # File can be FileSystem or Remote, not Virtual
        if 'Virtual' in location:
            return False

        return True

    def transcoding(self, result, server, id):

        if result['Path'].endswith('.strm'):
            # Allow strm loading when transcoding
            playurl = self.directPlay(result)
            return playurl

        # Play transcoding
        deviceId = self.clientInfo.getMachineId()
        playurl = "%s/mediabrowser/Videos/%s/master.m3u8?mediaSourceId=%s" % (server, id, id)
        playurl = "%s&VideoCodec=h264&AudioCodec=ac3&MaxAudioChannels=6&deviceId=%s&VideoBitrate=%s" % (playurl, deviceId, self.getVideoBitRate()*1000)
        
        playurl = self.audioSubsPref(playurl, result.get('MediaSources'))
        self.logMsg("Playurl: %s" % playurl, 1)
        
        return playurl
        

    def isNetworkQualitySufficient(self, result):
        # Works out if the network quality can play directly or if transcoding is needed
        settingsVideoBitRate = self.getVideoBitRate()
        settingsVideoBitRate = settingsVideoBitRate * 1000

        try:
            mediaSources = result['MediaSources']
            sourceBitRate = int(mediaSources[0]['Bitrate'])
        except KeyError:
            self.logMsg("Bitrate value is missing.", 1)
        else:
            self.logMsg("The video quality selected is: %s, the video bitrate required to direct stream is: %s." % (settingsVideoBitRate, sourceBitRate), 1)
            if settingsVideoBitRate < sourceBitRate:
                return False
        
        return True
      
    def getVideoBitRate(self):
        # get the addon video quality
        videoQuality = utils.settings('videoBitRate')
        bitrate = {

            '0': 664,
            '1': 996,
            '2': 1320,
            '3': 2000,
            '4': 3200,
            '5': 4700,
            '6': 6200,
            '7': 7700,
            '8': 9200,
            '9': 10700,
            '10': 12200,
            '11': 13700,
            '12': 15200,
            '13': 16700,
            '14': 18200,
            '15': 20000,
            '16': 40000,
            '17': 100000,
            '18': 1000000
        }

        # max bit rate supported by server (max signed 32bit integer)
        return bitrate.get(videoQuality, 2147483)
            
    def fileExists(self, result):
        
        if 'Path' not in result:
            # File has no path in server
            return False

        # Convert Emby path to a path we can verify
        path = self.directPlay(result)

        try:
            pathexists = xbmcvfs.exists(path)
        except:
            pathexists = False

        # Verify the device has access to the direct path
        if pathexists:
            # Local or Network path
            self.logMsg("Path exists.", 2)
            return True
        elif ":" not in path:
            # Give benefit of the doubt for nfs.
            self.logMsg("Can't verify path (assumed NFS). Still try direct play.", 2)
            return True
        else:
            self.logMsg("Path is detected as follow: %s. Try direct streaming." % path, 2)
            return False

    def audioSubsPref(self, url, mediaSources):
        # For transcoding only
        # Present the list of audio to select from
        audioStreamsList = {}
        audioStreams = []
        audioStreamsChannelsList = {}
        subtitleStreamsList = {}
        subtitleStreams = ['No subtitles']
        selectAudioIndex = ""
        selectSubsIndex = ""
        playurlprefs = "%s" % url

        mediaStream = mediaSources[0].get('MediaStreams')
        for stream in mediaStream:
            # Since Emby returns all possible tracks together, have to sort them.
            index = stream['Index']
            type = stream['Type']

            if 'Audio' in type:
                codec = stream['Codec']
                channelLayout = stream['ChannelLayout']
               
                try:
                    track = "%s - %s - %s %s" % (index, stream['Language'], codec, channelLayout)
                except:
                    track = "%s - %s %s" % (index, codec, channelLayout)
                
                audioStreamsChannelsList[index] = stream['Channels']
                audioStreamsList[track] = index
                audioStreams.append(track)

            elif 'Subtitle' in type:
                try:
                    track = "%s - %s" % (index, stream['Language'])
                except:
                    track = "%s - %s" % (index, stream['Codec'])

                default = stream['IsDefault']
                forced = stream['IsForced']
                if default:
                    track = "%s - Default" % track
                if forced:
                    track = "%s - Forced" % track

                subtitleStreamsList[track] = index
                subtitleStreams.append(track)


        if len(audioStreams) > 1:
            resp = xbmcgui.Dialog().select("Choose the audio stream", audioStreams)
            if resp > -1:
                # User selected audio
                selected = audioStreams[resp]
                selectAudioIndex = audioStreamsList[selected]
                playurlprefs += "&AudioStreamIndex=%s" % selectAudioIndex
            else: # User backed out of selection
                playurlprefs += "&AudioStreamIndex=%s" % mediaSources[0]['DefaultAudioStreamIndex']
        else: # There's only one audiotrack.
            selectAudioIndex = audioStreamsList[audioStreams[0]]
            playurlprefs += "&AudioStreamIndex=%s" % selectAudioIndex

        if len(subtitleStreams) > 1:
            resp = xbmcgui.Dialog().select("Choose the subtitle stream", subtitleStreams)
            if resp == 0:
                # User selected no subtitles
                pass
            elif resp > -1:
                # User selected subtitles
                selected = subtitleStreams[resp]
                selectSubsIndex = subtitleStreamsList[selected]
                playurlprefs += "&SubtitleStreamIndex=%s" % selectSubsIndex
            else: # User backed out of selection
                playurlprefs += "&SubtitleStreamIndex=%s" % mediaSources[0].get('DefaultSubtitleStreamIndex', "")

        # Get number of channels for selected audio track
        audioChannels = audioStreamsChannelsList.get(selectAudioIndex, 0)
        if audioChannels > 2:
            playurlprefs += "&AudioBitrate=384000"
        else:
            playurlprefs += "&AudioBitrate=192000"

        return playurlprefs