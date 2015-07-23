# -*- coding: utf-8 -*-

#################################################################################################
# utils class
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

from ClientInformation import ClientInformation
import Utils as utils

###########################################################################

class PlayUtils():

    _shared_state = {}

    clientInfo = ClientInformation()
    
    addonName = clientInfo.getAddonName()
    addon = xbmcaddon.Addon()
    WINDOW = xbmcgui.Window(10000)

    audioPref = addon.getSetting('Audiopref')
    subsPref = addon.getSetting('Subspref')

    def __init__(self):
        self.__dict__ = self._shared_state

    def logMsg(self, msg, lvl=1):
        
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, int(lvl))

    def getPlayUrl(self, server, id, result):

        WINDOW = self.WINDOW
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)

        if self.isDirectPlay(result,True):
            # Try direct play
            playurl = self.directPlay(result)
            if playurl:
                self.logMsg("File is direct playing.", 1)
                WINDOW.setProperty("%splaymethod" % playurl.encode('utf-8'), "DirectPlay")

        elif self.isDirectStream(result):
            # Try direct stream
            playurl = self.directStream(result, server, id)
            if playurl:
                self.logMsg("File is direct streaming.", 1)
                WINDOW.setProperty("%splaymethod" % playurl, "DirectStream")

        elif self.isTranscoding(result):
            # Try transcoding
            playurl = self.transcoding(result, server, id)
            if playurl:
                self.logMsg("File is transcoding.", 1)
                WINDOW.setProperty("%splaymethod" % playurl, "Transcode")
        else:
            # Error
            return False

        return playurl.encode('utf-8')

    def isDirectPlay(self, result, dialog=False):
        # Requirements for Direct play:
        # FileSystem, Accessible path
        self.addon = xbmcaddon.Addon()
        
        playhttp = self.addon.getSetting('playFromStream')
        # User forcing to play via HTTP instead of SMB
        if playhttp == "true":
            self.logMsg("Can't direct play: Play from HTTP is enabled.", 1)
            return False

        canDirectPlay = result[u'MediaSources'][0][u'SupportsDirectPlay']
        # Make sure it's supported by server
        if not canDirectPlay:
            self.logMsg("Can't direct play: Server does not allow or support it.", 1)
            return False

        location = result[u'LocationType']
        # File needs to be "FileSystem"
        if u'FileSystem' in location:
            # Verify if path is accessible
            if self.fileExists(result):
                return True
            else:
                self.logMsg("Unable to direct play. Verify the following path is accessible by the device: %s. You might also need to add SMB credentials in the addon settings." % result[u'MediaSources'][0][u'Path'])
                if dialog:
                    # Let user know that direct play failed
                    dialog = xbmcgui.Dialog()
                    resp = dialog.select('Warning: Unable to direct play.', ['Play from HTTP', 'Play from HTTP and remember next time.'])
                    if resp == 1:
                        # Remember next time
                        self.addon.setSetting('playFromStream', "true")
                    elif resp < 0:
                        # User decided not to proceed.
                        self.logMsg("User cancelled HTTP selection dialog.", 1)
                        self.WINDOW.setProperty("playurlFalse", "true")
                        
                return False


    def directPlay(self, result):

        addon = self.addon
        try:
            try:
                playurl = result[u'MediaSources'][0][u'Path']
            except:
                playurl = result[u'Path']
        except: 
            self.logMsg("Direct play failed. Trying Direct stream.", 1)
            return False
        else:
            if u'VideoType' in result:
                # Specific format modification
                if u'Dvd' in result[u'VideoType']:
                    playurl = "%s/VIDEO_TS/VIDEO_TS.IFO" % playurl
                elif u'BluRay' in result[u'VideoType']:
                    playurl = "%s/BDMV/index.bdmv" % playurl

            # Network - SMB protocol
            if "\\\\" in playurl:
                smbuser = addon.getSetting('smbusername')
                smbpass = addon.getSetting('smbpassword')
                # Network share
                if smbuser:
                    playurl = playurl.replace("\\\\", "smb://%s:%s@" % (smbuser, smbpass))
                else:
                    playurl = playurl.replace("\\\\", "smb://")
                playurl = playurl.replace("\\", "/")
                
            if "apple.com" in playurl:
                USER_AGENT = "QuickTime/7.7.4"
                playurl += "?|User-Agent=%s" % USER_AGENT

            if ":" not in playurl:
                self.logMsg("Path seems invalid: %s" % playurl, 1)
                return False

            return playurl

    def isDirectStream(self, result):
        # Requirements for Direct stream:
        # FileSystem or Remote, BitRate, supported encoding
        canDirectStream = result[u'MediaSources'][0][u'SupportsDirectStream']
        # Make sure it's supported by server
        if not canDirectStream:
            return False

        location = result[u'LocationType']
        # File can be FileSystem or Remote, not Virtual
        if u'Virtual' in location:
            return False

        # Verify BitRate
        if not self.isNetworkQualitySufficient(result):
            return False

        return True
  
    def directStream(self, result, server, id, type = "Video"):
        
        try:
            if "ThemeVideo" in type:
                playurl ="%s/mediabrowser/Videos/%s/stream?static=true" % (server, id)

            elif "Video" in type:
                playurl = "%s/mediabrowser/Videos/%s/stream?static=true" % (server, id)
                # Verify audio and subtitles
                mediaSources = result[u'MediaSources']
                if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                    playurl = "%s&AudioStreamIndex=%s" % (playurl, mediaSources[0].get('DefaultAudioStreamIndex'))
                if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                    playurl = "%s&SubtitleStreamIndex=%s" % (playurl, mediaSources[0].get('DefaultSubtitleStreamIndex'))
            
            elif "Audio" in type:
                playurl = "%s/mediabrowser/Audio/%s/stream.mp3" % (server, id)
            
            return playurl
                
        except:
            self.logMsg("Direct stream failed. Trying transcoding.", 1)
            return False

    def isTranscoding(self, result):
        # Last resort, no requirements
        # BitRate
        canTranscode = result[u'MediaSources'][0][u'SupportsTranscoding']
        # Make sure it's supported by server
        if not canTranscode:
            return False

        location = result[u'LocationType']
        # File can be FileSystem or Remote, not Virtual
        if u'Virtual' in location:
            return False

        return True

    def transcoding(self, result, server, id):
        
        try:
            # Play transcoding
            deviceId = self.clientInfo.getMachineId()
            playurl = "%s/mediabrowser/Videos/%s/master.m3u8?mediaSourceId=%s" % (server, id, id)
            playurl = "%s&VideoCodec=h264&AudioCodec=aac,ac3&deviceId=%s&VideoBitrate=%s" % (playurl, deviceId, self.getVideoBitRate()*1000)

            mediaSources = result[u'MediaSources']
            prefs = self.audioSubsPref(mediaSources)
            
            playurl = "%s%s" % (playurl, prefs)
            self.logMsg("Playurl: %s" % playurl)
            
            return playurl

        except:
            self.logMsg("Transcoding failed.")
            return False
        
    # Works out if the network quality can play directly or if transcoding is needed
    def isNetworkQualitySufficient(self, result):
        
        settingsVideoBitRate = self.getVideoBitRate()
        settingsVideoBitRate = settingsVideoBitRate * 1000

        try:
            mediaSources = result[u'MediaSources']
            sourceBitRate = int(mediaSources[0][u'Bitrate'])
            
            if settingsVideoBitRate > sourceBitRate:
                return True
            else:
                return False
        except:
            return True
      
    def getVideoBitRate(self):
        # get the addon video quality
        videoQuality = self.addon.getSetting('videoBitRate')

        if (videoQuality == "0"):
            return 664
        elif (videoQuality == "1"):
           return 996
        elif (videoQuality == "2"):
           return 1320
        elif (videoQuality == "3"):
           return 2000
        elif (videoQuality == "4"):
           return 3200
        elif (videoQuality == "5"):
           return 4700
        elif (videoQuality == "6"):
           return 6200
        elif (videoQuality == "7"):
           return 7700
        elif (videoQuality == "8"):
           return 9200
        elif (videoQuality == "9"):
           return 10700
        elif (videoQuality == "10"):
           return 12200
        elif (videoQuality == "11"):
           return 13700
        elif (videoQuality == "12"):
           return 15200
        elif (videoQuality == "13"):
           return 16700
        elif (videoQuality == "14"):
           return 18200
        elif (videoQuality == "15"):
           return 20000
        elif (videoQuality == "16"):
           return 40000
        elif (videoQuality == "17"):
           return 100000
        elif (videoQuality == "18"):
           return 1000000
        else:
            return 2147483 # max bit rate supported by server (max signed 32bit integer)
            
    def fileExists(self, result):
        
        if u'Path' not in result:
            # File has no path in server
            return False

        # Convert Emby path to a path we can verify
        path = self.directPlay(result)
        if not path:
            return False

        try:
            pathexists = xbmcvfs.exists(path)
        except:
            pathexists = False

        # Verify the device has access to the direct path
        if pathexists:
            # Local or Network path
            self.logMsg("Path exists.", 2)
            return True
        elif "nfs:" in path.lower():
            # Give benefit of the doubt.
            self.logMsg("Can't verify path. Still try direct play.", 2)
            return True
        else:
            self.logMsg("Path is detected as follow: %s. Try direct streaming." % path, 2)
            return False

    def audioSubsPref(self, mediaSources):

        addon = xbmcaddon.Addon(id=self.addonId)

        defaultAudio = mediaSources[0][u'DefaultAudioStreamIndex']
        playurlprefs = "&AudioStreamIndex=%s" % defaultAudio

        codecs = [
            # Possible codecs
            u'und', u'ac3', u'dts', u'5.1', u'aac', u'mp3', u'dca'
        ]

        try:
            mediaStream = mediaSources[0].get('MediaStreams')
            audiotracks = {}
            substracks = {}
            defaultSubs = None

            for stream in mediaStream:
                # Since Emby returns all possible tracks together, have to sort them.
                if u'Audio' in stream[u'Type']:
                    if u'Language' in stream:
                        audiotracks[stream[u'Language']] = stream[u'Index']
                    else:
                        audiotracks[stream[u'Codec']] = stream[u'Index']

                if u'Subtitle' in stream[u'Type']:
                    if u'Language' in stream:
                        substracks[stream[u'Language']] = stream[u'Index']
                        if stream[u'IsDefault'] == True:
                            defaultSubs = stream[u'Language']
                    else:
                        substracks[stream[u'Codec']] = stream[u'Index']
                        if stream[u'IsDefault']:
                            defaultSubs = stream[u'Codec']

            self.logMsg("%s %s %s" % (defaultSubs, audiotracks, substracks), 1)
            
            if len(audiotracks) == 1 and len(substracks) == 0:
                # There's only one audio track and no subtitles
                playurlprefs = "&AudioStreamIndex=%s" % defaultAudio
                return playurlprefs

            codec_intrack = False
            for codec in codecs:
                for track in audiotracks:
                    if codec in track:
                        codec_intrack = True

            if self.audioPref in audiotracks:
                self.logMsg("Door 1", 2)
                # Audio pref is available
                playurlprefs = "&AudioStreamIndex=%s" % audiotracks[self.audioPref]

                if addon.getSetting('subsoverride') == "true":
                    # Subs are forced.
                    if self.subsPref in substracks:
                        self.logMsg("Door 1.1", 2)
                        playurlprefs = "%s&SubtitleStreamIndex=%s" % (playurlprefs, substracks[self.subsPref])
                    else:
                        # Use default subs
                        if defaultSubs != None:
                            self.logMsg("Door 1.2", 2)
                            playurlprefs = "%s&SubtitleStreamIndex=%s" % (playurlprefs, substracks[defaultSubs])

            elif (len(audiotracks) == 1) and not codec_intrack:
                self.logMsg("Door 2", 2)
                # 1. There's one audio track.
                # 2. The audio is defined as a language.
                # 3. Audio pref is not available, guaranteed.
                playurlprefs = "&AudioStreamIndex=%s" % defaultAudio

                if self.subsPref in substracks:
                    self.logMsg("Door 2.1", 2)
                    # Subs pref is available.
                    playurlprefs = "%s&SubtitleStreamIndex=%s" % (playurlprefs, substracks[self.subsPref])
                else:
                    # Use default subs
                    if defaultSubs != None:
                        self.logMsg("Door 2.2", 2)
                        playurlprefs = "%s&SubtitleStreamIndex=%s" % (playurlprefs, substracks[defaultSubs])

            elif len(audiotracks) == 1 and codec_intrack:
                self.logMsg("Door 3", 2)
                # 1. There one audio track.
                # 2. The audio is undefined or a codec.
                # 3. Audio track is mislabeled.
                playurlprefs = "&AudioStreamIndex=%s" % defaultAudio

                if self.subsPref in substracks:
                    # If the subtitle is available, only display
                    # if the setting is enabled.
                    if addon.getSetting('subsoverride') == "true":
                        # Subs are forced.
                        self.logMsg("Door 3.1", 2)
                        playurlprefs = "%s&SubtitleStreamIndex=%s" % (playurlprefs, substracks[self.subsPref])
                else:
                    # Use default subs
                    if defaultSubs != None:
                        self.logMsg("Door 3.2", 2)
                        playurlprefs = "%s&SubtitleStreamIndex=%s" % (playurlprefs, substracks[defaultSubs])

        except: pass

        return playurlprefs