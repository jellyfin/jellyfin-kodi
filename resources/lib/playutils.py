# -*- coding: utf-8 -*-

#################################################################################################

import xbmc
import xbmcgui
import xbmcvfs

import clientinfo
import utils

#################################################################################################


class PlayUtils():
    
    
    def __init__(self, item):

        self.item = item

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()

        self.userid = utils.window('emby_currUser')
        self.server = utils.window('emby_server%s' % self.userid)

    def logMsg(self, msg, lvl=1):

        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, self.className), msg, lvl)
    

    def getPlayUrl(self):

        log = self.logMsg
        window = utils.window

        item = self.item
        playurl = None
        
        if (item.get('Type') in ("Recording", "TvChannel") and
                item.get('MediaSources') and item['MediaSources'][0]['Protocol'] == "Http"):
            # Play LiveTV or recordings
            log("File protocol is http (livetv).", 1)
            playurl = "%s/emby/Videos/%s/live.m3u8?static=true" % (self.server, item['Id'])
            window('emby_%s.playmethod' % playurl, value="Transcode")

        elif item.get('MediaSources') and item['MediaSources'][0]['Protocol'] == "Http":
            # Only play as http, used for channels, or online hosting of content
            log("File protocol is http.", 1)
            playurl = self.httpPlay()
            window('emby_%s.playmethod' % playurl, value="DirectStream")

        elif self.isDirectPlay():

            log("File is direct playing.", 1)
            playurl = self.directPlay()
            playurl = playurl.encode('utf-8')
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="DirectPlay")

        elif self.isDirectStream():
            
            log("File is direct streaming.", 1)
            playurl = self.directStream()
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="DirectStream")

        elif self.isTranscoding():
            
            log("File is transcoding.", 1)
            playurl = self.transcoding()
            # Set playmethod property
            window('emby_%s.playmethod' % playurl, value="Transcode")

        return playurl

    def httpPlay(self):
        # Audio, Video, Photo
        item = self.item
        server = self.server

        itemid = item['Id']
        mediatype = item['MediaType']

        if mediatype == "Audio":
            playurl = "%s/emby/Audio/%s/stream" % (server, itemid)
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (server, itemid)

        return playurl

    def isDirectPlay(self):

        log = self.logMsg
        lang = utils.language
        settings = utils.settings
        dialog = xbmcgui.Dialog()

        item = self.item

        # Requirement: Filesystem, Accessible path
        if settings('playFromStream') == "true":
            # User forcing to play via HTTP
            log("Can't direct play, play from HTTP enabled.", 1)
            return False

        videotrack = item['MediaSources'][0]['Name']
        transcodeH265 = settings('transcodeH265')

        if transcodeH265 in ("1", "2", "3") and ("HEVC" in videotrack or "H265" in videotrack):
            # Avoid H265/HEVC depending on the resolution
            resolution = int(videotrack.split("P", 1)[0])
            res = {

                '1': 480,
                '2': 720,
                '3': 1080
            }
            log("Resolution is: %sP, transcode for resolution: %sP+"
                % (resolution, res[transcodeH265]), 1)
            if res[transcodeH265] <= resolution:
                return False

        canDirectPlay = item['MediaSources'][0]['SupportsDirectPlay']
        # Make sure direct play is supported by the server
        if not canDirectPlay:
            log("Can't direct play, server doesn't allow/support it.", 1)
            return False

        location = item['LocationType']
        if location == "FileSystem":
            # Verify the path
            if not self.fileExists():
                log("Unable to direct play.")
                try:
                    count = int(settings('failCount'))
                except ValueError:
                    count = 0
                log("Direct play failed: %s times." % count, 1)

                if count < 2:
                    # Let the user know that direct play failed
                    settings('failCount', value=str(count+1))
                    dialog.notification(
                                heading="Emby for Kodi",
                                message=lang(33011),
                                icon="special://home/addons/plugin.video.emby/icon.png",
                                sound=False)
                elif settings('playFromStream') != "true":
                    # Permanently set direct stream as true
                    settings('playFromStream', value="true")
                    settings('failCount', value="0")
                    dialog.notification(
                                heading="Emby for Kodi",
                                message=lang(33012),
                                icon="special://home/addons/plugin.video.emby/icon.png",
                                sound=False)
                return False

        return True

    def directPlay(self):

        item = self.item

        try:
            playurl = item['MediaSources'][0]['Path']
        except (IndexError, KeyError):
            playurl = item['Path']

        if item.get('VideoType'):
            # Specific format modification
            type = item['VideoType']

            if type == "Dvd":
                playurl = "%s/VIDEO_TS/VIDEO_TS.IFO" % playurl
            elif type == "BluRay":
                playurl = "%s/BDMV/index.bdmv" % playurl

        # Assign network protocol
        if playurl.startswith('\\\\'):
            playurl = playurl.replace("\\\\", "smb://")
            playurl = playurl.replace("\\", "/")

        if "apple.com" in playurl:
            USER_AGENT = "QuickTime/7.7.4"
            playurl += "?|User-Agent=%s" % USER_AGENT

        return playurl

    def fileExists(self):

        log = self.logMsg

        if 'Path' not in self.item:
            # File has no path defined in server
            return False

        # Convert path to direct play
        path = self.directPlay()
        log("Verifying path: %s" % path, 1)

        if xbmcvfs.exists(path):
            log("Path exists.", 1)
            return True

        elif ":" not in path:
            log("Can't verify path, assumed linux. Still try to direct play.", 1)
            return True

        else:
            log("Failed to find file.", 1)
            return False

    def isDirectStream(self):

        log = self.logMsg

        item = self.item

        videotrack = item['MediaSources'][0]['Name']
        transcodeH265 = utils.settings('transcodeH265')

        if transcodeH265 in ("1", "2", "3") and ("HEVC" in videotrack or "H265" in videotrack):
            # Avoid H265/HEVC depending on the resolution
            resolution = int(videotrack.split("P", 1)[0])
            res = {

                '1': 480,
                '2': 720,
                '3': 1080
            }
            log("Resolution is: %sP, transcode for resolution: %sP+"
                % (resolution, res[transcodeH265]), 1)
            if res[transcodeH265] <= resolution:
                return False

        # Requirement: BitRate, supported encoding
        canDirectStream = item['MediaSources'][0]['SupportsDirectStream']
        # Make sure the server supports it
        if not canDirectStream:
            return False

        # Verify the bitrate
        if not self.isNetworkSufficient():
            log("The network speed is insufficient to direct stream file.", 1)
            return False

        return True

    def directStream(self):

        item = self.item
        server = self.server

        itemid = item['Id']
        itemtype = item['Type']

        if 'Path' in item and item['Path'].endswith('.strm'):
            # Allow strm loading when direct streaming
            playurl = self.directPlay()
        elif itemtype == "Audio":
            playurl = "%s/emby/Audio/%s/stream.mp3" % (server, itemid)
        else:
            playurl = "%s/emby/Videos/%s/stream?static=true" % (server, itemid)

        return playurl

    def isNetworkSufficient(self):

        log = self.logMsg

        settings = self.getBitrate()*1000

        try:
            sourceBitrate = int(self.item['MediaSources'][0]['Bitrate'])
        except (KeyError, TypeError):
            log("Bitrate value is missing.", 1)
        else:
            log("The add-on settings bitrate is: %s, the video bitrate required is: %s"
                % (settings, sourceBitrate), 1)
            if settings < sourceBitrate:
                return False

        return True

    def isTranscoding(self):

        item = self.item

        canTranscode = item['MediaSources'][0]['SupportsTranscoding']
        # Make sure the server supports it
        if not canTranscode:
            return False

        return True

    def transcoding(self):

        item = self.item

        if 'Path' in item and item['Path'].endswith('.strm'):
            # Allow strm loading when transcoding
            playurl = self.directPlay()
        else:
            itemid = item['Id']
            deviceId = self.clientInfo.getDeviceId()
            playurl = (
                "%s/emby/Videos/%s/master.m3u8?MediaSourceId=%s"
                % (self.server, itemid, itemid)
            )
            playurl = (
                "%s&VideoCodec=h264&AudioCodec=ac3&MaxAudioChannels=6&deviceId=%s&VideoBitrate=%s"
                % (playurl, deviceId, self.getBitrate()*1000))

        return playurl

    def getBitrate(self):

        # get the addon video quality
        videoQuality = utils.settings('videoBitrate')
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

    def audioSubsPref(self, url, listitem):

        log = self.logMsg
        lang = utils.language
        dialog = xbmcgui.Dialog()
        # For transcoding only
        # Present the list of audio to select from
        audioStreamsList = {}
        audioStreams = []
        audioStreamsChannelsList = {}
        subtitleStreamsList = {}
        subtitleStreams = ['No subtitles']
        downloadableStreams = []
        selectAudioIndex = ""
        selectSubsIndex = ""
        playurlprefs = "%s" % url

        item = self.item
        try:
            mediasources = item['MediaSources'][0]
            mediastreams = mediasources['MediaStreams']
        except (TypeError, KeyError, IndexError):
            return

        for stream in mediastreams:
            # Since Emby returns all possible tracks together, have to sort them.
            index = stream['Index']
            type = stream['Type']

            if 'Audio' in type:
                codec = stream['Codec']
                channelLayout = stream.get('ChannelLayout', "")
               
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
                downloadable = stream['IsTextSubtitleStream']

                if default:
                    track = "%s - Default" % track
                if forced:
                    track = "%s - Forced" % track
                if downloadable:
                    downloadableStreams.append(index)

                subtitleStreamsList[track] = index
                subtitleStreams.append(track)


        if len(audioStreams) > 1:
            resp = dialog.select(lang(33013), audioStreams)
            if resp > -1:
                # User selected audio
                selected = audioStreams[resp]
                selectAudioIndex = audioStreamsList[selected]
                playurlprefs += "&AudioStreamIndex=%s" % selectAudioIndex
            else: # User backed out of selection
                playurlprefs += "&AudioStreamIndex=%s" % mediasources['DefaultAudioStreamIndex']
        else: # There's only one audiotrack.
            selectAudioIndex = audioStreamsList[audioStreams[0]]
            playurlprefs += "&AudioStreamIndex=%s" % selectAudioIndex

        if len(subtitleStreams) > 1:
            resp = dialog.select(lang(33014), subtitleStreams)
            if resp == 0:
                # User selected no subtitles
                pass
            elif resp > -1:
                # User selected subtitles
                selected = subtitleStreams[resp]
                selectSubsIndex = subtitleStreamsList[selected]

                # Load subtitles in the listitem if downloadable
                if selectSubsIndex in downloadableStreams:

                    itemid = item['Id']
                    url = [("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                        % (self.server, itemid, itemid, selectSubsIndex))]
                    log("Set up subtitles: %s %s" % (selectSubsIndex, url), 1)
                    listitem.setSubtitles(url)
                else:
                    # Burn subtitles
                    playurlprefs += "&SubtitleStreamIndex=%s" % selectSubsIndex

            else: # User backed out of selection
                playurlprefs += "&SubtitleStreamIndex=%s" % mediasources.get('DefaultSubtitleStreamIndex', "")

        # Get number of channels for selected audio track
        audioChannels = audioStreamsChannelsList.get(selectAudioIndex, 0)
        if audioChannels > 2:
            playurlprefs += "&AudioBitrate=384000"
        else:
            playurlprefs += "&AudioBitrate=192000"

        return playurlprefs