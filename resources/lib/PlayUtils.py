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
    addonId = clientInfo.getAddonId()
    addon = xbmcaddon.Addon(id=addonId)

    def __init__(self):
        self.__dict__ = self._shared_state

    def logMsg(self, msg, lvl=1):
        
        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), str(msg), int(lvl))

    def getPlayUrl(self, server, id, result):

        addon = self.addon
        WINDOW = xbmcgui.Window(10000)
        username = WINDOW.getProperty('currUser')
        server = WINDOW.getProperty('server%s' % username)

        if self.isDirectPlay(result):
            try:
                # Try direct play
                playurl = self.directPlay(result)
                if not playurl:
                    # Let user know that direct play failed
                    resp = xbmcgui.Dialog().select('Warning: Unable to direct play.', ['Play from HTTP', 'Play from HTTP and remember next time.'])
                    if resp > -1:
                        # Play from HTTP
                        playurl = self.directStream(result, server, id)
                        if resp == 1:
                            # Remember next time
                            addon.setSetting('playFromStream', "true")
                        if not playurl:
                            # Try transcoding
                            playurl = self.transcoding(result, server, id)
                            WINDOW.setProperty("transcoding%s" % id, "true")
                            self.logMsg("File is transcoding.", 1)
                            WINDOW.setProperty("%splaymethod" % playurl, "Transcode")
                        else:
                            self.logMsg("File is direct streaming.", 1)
                            WINDOW.setProperty("%splaymethod" % playurl, "DirectStream")
                    else:
                        # User decided not to proceed.
                        self.logMsg("Unable to direct play. Verify the following path is accessible by the device: %s. You might also need to add SMB credentials in the addon settings." % result[u'MediaSources'][0][u'Path'])
                        return False
                else:
                    self.logMsg("File is direct playing.", 1)
                    WINDOW.setProperty("%splaymethod" % playurl.encode('utf-8'), "DirectPlay")
            except:
                return False

        elif self.isDirectStream(result):
            try:
                # Try direct stream
                playurl = self.directStream(result, server, id)
                if not playurl:
                    # Try transcoding
                    playurl = self.transcoding(result, server, id)
                    WINDOW.setProperty("transcoding%s" % id, "true")
                    self.logMsg("File is transcoding.", 1)
                    WINDOW.setProperty("%splaymethod" % playurl, "Transcode")
                else:
                    self.logMsg("File is direct streaming.", 1)
                    WINDOW.setProperty("%splaymethod" % playurl, "DirectStream")
            except:
                return False

        elif self.isTranscoding(result):
            try:
                # Try transcoding
                playurl = self.transcoding(result, server, id)
                WINDOW.setProperty("transcoding%s" % id, "true")
                self.logMsg("File is transcoding.", 1)
                WINDOW.setProperty("%splaymethod" % playurl, "Transcode")
            except:
                return False

        return playurl.encode('utf-8')


    def isDirectPlay(self, result):
        # Requirements for Direct play:
        # FileSystem, Accessible path
        self.addon = xbmcaddon.Addon(id=self.addonId)
        
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
                self.logMsg("Can't direct play: Unable to locate the content.", 1)
                return False


    def directPlay(self, result):

        addon = self.addon

        try:
            # Item can be played directly
            playurl = result[u'MediaSources'][0][u'Path']

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
                USER_AGENT = 'QuickTime/7.7.4'
                playurl += "?|User-Agent=%s" % USER_AGENT

            return playurl

        except:
            self.logMsg("Direct play failed. Trying Direct stream.", 1)
            return False

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

    def directStream(self, result, server, id):
        
        try:
            # Play with Direct Stream
            playurl = "%s/mediabrowser/Videos/%s/stream?static=true" % (server, id)

            mediaSources = result[u'MediaSources']
            if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                playurl = "%s&AudioStreamIndex=%s" % (playurl, mediaSources[0].get('DefaultAudioStreamIndex'))
            if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                playurl = "%s&SubtitleStreamIndex=%s" % (playurl, mediaSources[0].get('DefaultSubtitleStreamIndex'))

            self.logMsg("Playurl: %s" % playurl)
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
            if mediaSources[0].get('DefaultAudioStreamIndex') != None:
                playurl = "%s&AudioStreamIndex=%s" % (playurl, mediaSources[0][u'DefaultAudioStreamIndex'])
            if mediaSources[0].get('DefaultSubtitleStreamIndex') != None:
                playurl = "%s&SubtitleStreamIndex=%s" % (playurl, mediaSources[0][u'DefaultSubtitleStreamIndex'])

            self.logMsg("Playurl: %s" % playurl)
            return playurl

        except:
            self.logMsg("Transcoding failed.")
            return False

        '''forceTranscodingCodecs = self.addon.getSetting('forceTranscodingCodecs')
        # check if we should force encoding due to the forceTranscodingCodecs setting
        if forceTranscodingCodecs:
            forceTranscodingCodecsSet = frozenset(forceTranscodingCodecs.lower().split(','))
            codecs = frozenset([mediaStream.get('Codec', None) for mediaStream in result.get('MediaStreams', [])])
            commonCodecs = forceTranscodingCodecsSet & codecs
            #xbmc.log("emby isDirectPlay MediaStreams codecs: %s forceTranscodingCodecs: %s, common: %s" % (codecs, forceTranscodingCodecsSet, commonCodecs))
            if commonCodecs:
                return False'''
        
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
        try:
            pathexists = xbmcvfs.exists(path)
        except:
            pathexists = False

        # Verify the device has access to the direct path
        if pathexists:
            # Local or Network path
            self.logMsg("Path exists.", 2)
            return True
        elif ":\\" not in path:
            # Give benefit of the doubt.
            self.logMsg("Can't verify path. Still try direct play.", 2)
            return True
        else:
            self.logMsg("Path is detected as follow: %s. Try direct streaming." % path, 2)
            return False