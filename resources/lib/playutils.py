# -*- coding: utf-8 -*-

#################################################################################################

import collections
import logging
import requests
import os
import urllib

import xbmc
import xbmcgui
import xbmcvfs

import clientinfo
import downloadutils
import read_embyserver as embyserver
from utils import window, settings, language as lang, urllib_path, create_id

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################


class PlayUtils():
    
    play_session_id = None
    method = "DirectPlay"
    force_transcode = False


    def __init__(self, item, listitem, **kwargs):

        self.info = kwargs

        self.item = item
        self.listitem = listitem

        self.clientInfo = clientinfo.ClientInfo()
        self.emby = embyserver.Read_EmbyServer()

        self.server = window('emby_server%s' % window('emby_currUser'))
        self.play_session_id = str(create_id()).replace("-", "")

    def get_play_url(self, force_transcode=False):

        ''' New style to retrieve the best playback method based on sending
            the profile to the server. Based on capabilities the correct path is returned,
            including livestreams that need to be opened by the server
        '''

        self.force_transcode = force_transcode
        info = self.get_playback_info()
        url = False if info == False else None

        if info:
            url = info['Path'].encode('utf-8')
            window('emby_%s.play.json' % url, {

                'playmethod': self.method,
                'playsession_id': self.play_session_id,
                'mediasource_id': info.get('Id') or self.item['Id']
            })

            if 'RequiredHttpHeaders' in info and 'User-Agent' in info['RequiredHttpHeaders']:
                self.listitem.setProperty('User-Agent', info['RequiredHttpHeaders']['User-Agent'])

            log.info("playback info: %s", info)
            log.info("play method: %s play url: %s", self.method, url)

        return url

    def _is_media_selection(self):

        if self.item['MediaType'] != 'Video':
            log.debug("MediaType not video detected.")
            return False

        elif self.item['Type'] == 'TvChannel':
            log.debug("TvChannel detected.")
            return False

        elif len(self.item['MediaSources']) == 1 and self.item['MediaSources'][0]['Type'] == 'Placeholder':
            log.debug("Placeholder detected.")
            return False

        elif 'SourceType' in self.item and self.item['SourceType'] != 'Library':
            log.debug("SourceType not library detected.")
            return False

        return True

    def get_playback_info(self):

        # Get the playback info for the current item

        info = self.emby.get_playback_info(self.item['Id'], self.get_device_profile())
        media_sources = info['MediaSources']

        # Select the mediasource
        if not media_sources:
            log.error('No media sources found: %s', info)
            return

        selected_source = media_sources[0]

        if 'MediaSourceId' in self.info:
            for source in media_sources:
                if source['Id'] == self.info['MediaSourceId']:
                    selected_source = source
                    break

        elif not self._is_media_selection():
            log.info("Special media type detected. Skip source selection.")

        elif len(media_sources) > 1:
            # Offer choices
            sources = []
            for source in media_sources:
                sources.append(source.get('Name', "na"))

            resp = xbmcgui.Dialog().select("Select the source", sources)
            if resp > -1:
                selected_source = media_sources[resp]
            else:
                log.info("No media source selected.")
                return False

        return self.get_optimal_track(selected_source)

    def get_optimal_track(self, source):

        ''' Because we posted our deviceprofile to the server, only streams will be
            returned that can actually be played by this client so no need to check bitrates etc.
        '''

        # Log filename, used by other addons eg subtitles which require the file name
        window('embyfilename', value=self.get_direct_path(source))

        if (not self.force_transcode and (self.is_strm(source) or self.is_h265(source) or
            (source['SupportsDirectPlay'] and settings('playFromStream') == "false" and self.is_file_exists(source)))):
            # Do nothing, path is updated with our verification if applies.
            pass
        else:
            source['Path'] = self.get_http_path(source, True if not source['SupportsDirectStream'] else self.force_transcode)

        log.debug('get source: %s', source)
        return source

    def is_file_exists(self, source):

        path = self.get_direct_path(source)

        if xbmcvfs.exists(path): # or ":" not in path:
            log.info("Path exists.")

            self.method = "DirectPlay"
            source['Path'] = path

            return True

        log.info("Failed to find file.")
        return False

    def is_strm(self, source):

        if source['Container'] == "strm" or '.strm' in self.item['Path']:
            log.info('Strm detected.')

            self.method = "DirectPlay"
            source['Path'] = self.get_direct_path(source)

            return True
        
        return False

    def is_h265(self, source):

        if source['MediaStreams']:
            force_transcode = False

            for stream in source['MediaStreams']:
                if self._is_h265(stream) or self._is_high10(stream):
                    force_transcode = True
                    break

            if force_transcode:
                source['Path'] = self.get_http_path(source, True)
                return True

        return False

    @classmethod
    def _is_h265(cls, stream):

        if stream['Type'] == "Video" and stream['Codec'] in ("hevc", "h265"):
            if settings('transcode_h265') == "true":
                log.info("Force transcode h265/hevc detected.")
                return True

        return False

    @classmethod
    def _is_high10(cls, stream):

        if stream.get('Profile') == "High 10":
            if settings('transcodeHi10P') == "true":
                log.info("Force transcode hi10p detected.")
                return True

        return False

    def get_direct_path(self, source):

        path = source['Path']

        if 'VideoType' in source:
            if source['VideoType'] == "Dvd":
                path = "%s/VIDEO_TS/VIDEO_TS.IFO" % path
            elif source['VideoType'] == "BluRay":
                path = "%s/BDMV/index.bdmv" % path

        # Assign network protocol
        if path.startswith('\\\\'):
            path = path.replace('\\\\', "smb://", 1)
            path = path.replace('\\\\', "\\")
            path = path.replace('\\', "/")

        if "://" in path:
            # Protocol needs to be lowercase, otherwise weird things happen.
            protocol = path.split('://')[0]
            path = path.replace(protocol, protocol.lower())

        return path

    def get_http_path(self, source, transcode=False):
        
        if transcode and settings('ignoreTranscode') and source['MediaStreams']:
            # Specified by user should not be transcoded.
            ignore_codecs = settings('ignoreTranscode').split(',')

            for stream in source['MediaStreams']:
                if stream['Type'] == "Video" and stream['Codec'] in ignore_codecs:
                    log.info("Ignoring transcode for: %s", stream['Codec'])
                    transcode = False
                    break

        url = self.get_transcode_url(source) if transcode else self.get_direct_url(source)
        url = self._append_http_url(source, url)
        
        return url

    def get_direct_url(self, source):

        self.method = "DirectStream"

        if self.item['Type'] == "Audio":
            url = "%s/emby/Audio/%s/stream.%s?static=true" % (self.server, self.item['Id'], self.item['MediaSources'][0]['Container'])
        else:
            url = "%s/emby/Videos/%s/stream?static=true" % (self.server, self.item['Id'])

        # Append external subtitles
        if settings('enableExternalSubs') == "true":
            self.set_external_subs(source, url)

        return url

    def get_transcode_url(self, source):

        self.method = "Transcode"

        item_id = self.item['Id']
        url = urllib_path("%s/emby/Videos/%s/master.m3u8" % (self.server, item_id), {

            'VideoCodec': "h264",
            'AudioCodec': "ac3",
            'MaxAudioChannels': 6,
            'DeviceId': self.clientInfo.get_device_id(),
            'VideoBitrate': self.get_bitrate() * 1000
        })

        # Select audio and subtitles
        url += self.get_audio_subs(source)

        # Limit to 8 bit if user selected transcode Hi10P
        if settings('transcodeHi10P') == "true":
            url += "&MaxVideoBitDepth=8"

        # Adjust the video resolution
        url += "&maxWidth=%s&maxHeight=%s" % (self.get_resolution())

        return url

    def _append_http_url(self, source, url):

        url += "&MediaSourceId=%s" % source['Id']
        url += "&PlaySessionId=%s" % self.play_session_id
        url += "&api_key=%s" % downloadutils.DownloadUtils().get_token()

        return url

    def set_external_subs(self, source, play_url):

        subs = []
        mapping = {}

        item_id = self.item['Id']
        streams = source['MediaStreams']

        if not source['MediaStreams']:
            log.info("No media streams found.")
            return

        temp = xbmc.translatePath("special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

        ''' Since Emby returns all possible tracks together, sort them.
            IsTextSubtitleStream if true, is available to download from server.
        '''

        kodi_index = 0
        for stream in streams:

            if stream['Type'] == "Subtitle" and stream['IsExternal'] and stream['IsTextSubtitleStream']:
                index = stream['Index']

                url = self.server + stream['DeliveryUrl']

                if 'Language' in stream:
                    filename = "Stream.%s.%s" % (stream['Language'].encode('utf-8'), stream['Codec'])
                    try:
                        subs.append(self._download_external_subs(url, temp, filename))
                    except Exception as error:
                        log.warn(error)
                        subs.append(url)
                else:
                    subs.append(url)

                # Map external subtitles for player.py
                mapping[kodi_index] = index
                kodi_index += 1

        window('emby_%s.indexMapping.json' % play_url, value=mapping)
        self.listitem.setSubtitles(subs)

        return

    @classmethod
    def _download_external_subs(cls, src, dst, filename):

        if not xbmcvfs.exists(dst):
            xbmcvfs.mkdir(dst)

        path = os.path.join(dst, filename)

        try:
            response = requests.get(src, stream=True)
            response.raise_for_status()
        except Exception as e:
            raise
        else:
            response.encoding = 'utf-8'
            with open(path, 'wb') as f:
                f.write(response.content)
                del response

            return path

    def get_audio_subs(self, source):

        ''' For transcoding only
            Present the list of audio/subs to select from, before playback starts.
            Returns part of the url to append.
        '''

        prefs = ""
        streams = source['MediaStreams']

        audio_streams = collections.OrderedDict()
        subs_streams = collections.OrderedDict()

        if streams:

            ''' Since Emby returns all possible tracks together, sort them.
                IsTextSubtitleStream if true, is available to download from server.
            '''

            for stream in streams:
                index = stream['Index']
                stream_type = stream['Type']

                if stream_type == "Audio":
                    codec = stream['Codec']
                    channel = stream.get('ChannelLayout', "")

                    if 'Language' in stream:
                        track = "%s - %s - %s %s" % (index, stream['Language'], codec, channel)
                    else:
                        track = "%s - %s %s" % (index, codec, channel)

                    audio_streams[track] = index

                elif stream_type == "Subtitle":

                    if 'Language' in stream:
                        track = "%s - %s" % (index, stream['Language'])
                    else:
                        track = "%s - %s" % (index, stream['Codec'])

                    if stream['IsDefault']:
                        track = "%s - Default" % track
                    if stream['IsForced']:
                        track = "%s - Forced" % track

                    subs_streams[track] = index

            dialog = xbmcgui.Dialog()
            skip_dialog = int(settings('skipDialogTranscode') or 0)
            audio_selected = None

            if self.info.get('AudioStreamIndex'):
                audio_selected = self.info['AudioStreamIndex']

            elif skip_dialog in (0, 1):
                if len(audio_streams) > 1:
                    selection = list(audio_streams.keys())
                    resp = dialog.select(lang(33013), selection)
                    audio_selected = audio_streams[selection[resp]] if resp else source['DefaultAudioStreamIndex']
                else: # Only one choice
                    audio_selected = audio_streams[next(iter(audio_streams))]
            else:
                audio_selected = source['DefaultAudioStreamIndex']
            
            prefs += "&AudioStreamIndex=%s" % audio_selected
            prefs += "&AudioBitrate=384000" if streams[audio_selected].get('Channels', 0) > 2 else "&AudioBitrate=192000"

            if self.info.get('SubtitleStreamIndex'):
                index = self.info['SubtitleStreamIndex']

                if index:
                    server_settings = self.emby.get_server_transcoding_settings()
                    if server_settings['EnableSubtitleExtraction'] and streams[index]['SupportsExternalStream']:
                        self._get_subtitles(source, index)
                    else:
                        prefs += "&SubtitleStreamIndex=%s" % index

            elif skip_dialog in (0, 2) and len(subs_streams):
                selection = list(['No subtitles']) + list(subs_streams.keys())
                resp = dialog.select(lang(33014), selection)
                if resp:
                    index = subs_streams[selection[resp]] if resp > -1 else source.get('DefaultSubtitleStreamIndex')
                    if index is not None:
                        server_settings = self.emby.get_server_transcoding_settings()
                        if server_settings['EnableSubtitleExtraction'] and streams[index]['SupportsExternalStream']:
                            self._get_subtitles(source, index)
                        else:
                            prefs += "&SubtitleStreamIndex=%s" % index

        return prefs

    def _get_subtitles(self, source, index):

        url = [("%s/Videos/%s/%s/Subtitles/%s/Stream.srt"
                % (self.server, self.item['Id'], source['Id'], index))]

        log.info("Set up subtitles: %s %s", index, url)
        self.listitem.setSubtitles(url)

    def get_bitrate(self):

        ''' Get the addon video quality
            Max bit rate supported by server: 2147483 (max signed 32bit integer)
        '''

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
            '16': 25000,
            '17': 30000,
            '18': 35000,
            '16': 40000,
            '17': 100000,
            '18': 1000000
        }
        return bitrate.get(settings('videoBitrate'), 2147483)
    
    def get_device_profile(self):
        return {

            "Name": "Kodi",
            "MaxStreamingBitrate": self.get_bitrate() * 1000,
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,

            "Identification": {
                "ModelName": "Kodi",
                "Headers": [
                    {
                        "Name": "User-Agent",
                        "Value": "Kodi",
                        "Match": 2
                    }
                ]
            },

            "TranscodingProfiles": [
                {
                    "Container": "mp3",
                    "AudioCodec": "mp3",
                    "Type": 0
                },
                {
                    "Container": "ts",
                    "AudioCodec": "ac3",
                    "VideoCodec": "h264",
                    "Type": 1
                },
                {
                    "Container": "jpeg",
                    "Type": 2
                }
            ],

            "DirectPlayProfiles": [
                {
                    "Container": "",
                    "Type": 0
                },
                {
                    "Container": "",
                    "Type": 1
                },
                {
                    "Container": "",
                    "Type": 2
                }
            ],

            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],

            "SubtitleProfiles": [
                {
                    "Format": "srt",
                    "Method": 2
                },
                {
                    "Format": "sub",
                    "Method": 2
                },
                {
                    "Format": "srt",
                    "Method": 1
                },
                {
                    "Format": "ass",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "ssa",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "smi",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "dvdsub",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "pgs",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "pgssub",
                    "Method": 1,
                    "DidlMode": ""
                },
                {
                    "Format": "sub",
                    "Method": 1,
                    "DidlMode": ""
                }
            ]
        }

    def get_resolution(self):

        window = xbmcgui.Window()
        return window.getWidth(), window.getHeight()
