# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os
from uuid import uuid4

import requests
from kodi_six import xbmc, xbmcvfs

from .. import client
from .utils import translate_path

from . import translate, settings, window, dialog, api, LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)


class Transcode(object):
    Enabled = 0
    Audio = 1
    Subtitle = 2
    Disabled = 3
    MediaDefault = 4

#################################################################################################


def set_properties(item, method, server_id=None):

    ''' Set all properties for playback detection.
    '''
    info = item.get('PlaybackInfo') or {}

    current = window('jellyfin_play.json') or []
    current.append({
        'Type': item['Type'],
        'Id': item['Id'],
        'Path': info['Path'],
        'PlayMethod': method,
        'PlayOption': 'Addon' if info.get('PlaySessionId') else 'Native',
        'MediaSourceId': info.get('MediaSourceId', item['Id']),
        'Runtime': item.get('RunTimeTicks'),
        'PlaySessionId': info.get('PlaySessionId', str(uuid4()).replace("-", "")),
        'ServerId': server_id,
        'DeviceId': client.get_device_id(),
        'SubsMapping': info.get('Subtitles'),
        'AudioStreamIndex': info.get('AudioStreamIndex'),
        'SubtitleStreamIndex': info.get('SubtitleStreamIndex'),
        'CurrentPosition': info.get('CurrentPosition'),
        'CurrentEpisode': info.get('CurrentEpisode')
    })

    window('jellyfin_play.json', current)


class PlayUtils(object):

    def __init__(self, item, force_transcode=False, server_id=None, server=None, api_client=None):

        ''' Item will be updated with the property PlaybackInfo, which
            holds all the playback information.
        '''
        self.item = item
        self.item['PlaybackInfo'] = {}
        self.api_client = api_client
        self.info = {
            'ServerId': server_id,
            'ServerAddress': server,
            'ForceTranscode': force_transcode,
            'Token': api_client.config.data['auth.token']
        }

    def get_sources(self, source_id=None):

        ''' Return sources based on the optional source_id or the device profile.
        '''
        info = self.api_client.get_play_info(self.item['Id'], self.get_device_profile())
        LOG.info(info)
        self.info['PlaySessionId'] = info['PlaySessionId']
        sources = []

        if not info.get('MediaSources'):
            LOG.info("No MediaSources found.")

        elif source_id:
            for source in info:

                if source['Id'] == source_id:
                    sources.append(source)

                    break

        elif not self.is_selection(info) or len(info['MediaSources']) == 1:

            LOG.info("Skip source selection.")
            sources.append(info['MediaSources'][0])

        else:
            sources.extend([x for x in info['MediaSources']])

        return sources

    def select_source(self, sources, audio=None, subtitle=None):

        if len(sources) > 1:
            selection = []

            for source in sources:
                selection.append(source.get('Name', "na"))

            resp = dialog("select", translate(33130), selection)

            if resp > -1:
                source = sources[resp]
            else:
                LOG.info("No media source selected.")
                return False
        else:
            source = sources[0]

        self.get(source, audio, subtitle)

        return source

    def is_selection(self, sources):

        ''' Do not allow source selection for.
        '''
        if self.item['MediaType'] != 'Video':
            LOG.debug("MediaType is not a video.")

            return False

        elif self.item['Type'] == 'TvChannel':
            LOG.debug("TvChannel detected.")

            return False

        elif len(sources) == 1 and sources[0]['Type'] == 'Placeholder':
            LOG.debug("Placeholder detected.")

            return False

        elif 'SourceType' in self.item and self.item['SourceType'] != 'Library':
            LOG.debug("SourceType not from library.")

            return False

        return True

    def is_file_exists(self, source):

        self.direct_play(source)

        if xbmcvfs.exists(self.info['Path']):
            LOG.info("Path exists.")

            return True

        LOG.info("Failed to find file.")

        return False

    def is_strm(self, source):

        if source.get('Container') == 'strm' or self.item['Path'].endswith('.strm'):
            LOG.info("strm detected")

            return True

        return False

    def get(self, source, audio=None, subtitle=None):

        ''' The server returns sources based on the MaxStreamingBitrate value and other filters.
            prop: jellyfinfilename for ?? I thought it was to pass the real path to subtitle add-ons but it's not working?
        '''
        self.info['MediaSourceId'] = source['Id']

        if source.get('RequiresClosing'):

            ''' Server returning live tv stream for direct play is hardcoded with 127.0.0.1.
            '''
            self.info['LiveStreamId'] = source['LiveStreamId']
            source['SupportsDirectPlay'] = False
            source['Protocol'] = "LiveTV"

        if self.info['ForceTranscode']:

            source['SupportsDirectPlay'] = False
            source['SupportsDirectStream'] = False

        if source.get('Protocol') == 'Http' or source['SupportsDirectPlay'] and (self.is_strm(source) or not settings('playFromStream.bool') and self.is_file_exists(source)):

            LOG.info("--[ direct play ]")
            self.direct_play(source)

        elif source['SupportsDirectStream'] or source['SupportsDirectPlay']:

            LOG.info("--[ direct stream ]")
            self.direct_url(source)

        else:
            LOG.info("--[ transcode ]")
            self.transcode(source, audio, subtitle)

        self.info['AudioStreamIndex'] = self.info.get('AudioStreamIndex') or source.get('DefaultAudioStreamIndex')
        self.info['SubtitleStreamIndex'] = self.info.get('SubtitleStreamIndex') or source.get('DefaultSubtitleStreamIndex')
        self.item['PlaybackInfo'].update(self.info)

        API = api.API(self.item, self.info['ServerAddress'])
        window('jellyfinfilename', value=API.get_file_path(source.get('Path')))

    def live_stream(self, source):

        ''' Get live stream media info.
        '''
        info = self.api_client.get_live_stream(self.item['Id'], self.info['PlaySessionId'], source['OpenToken'], self.get_device_profile())
        LOG.info(info)

        if info['MediaSource'].get('RequiresClosing'):
            self.info['LiveStreamId'] = source['LiveStreamId']

        return info['MediaSource']

    def transcode(self, source, audio=None, subtitle=None):

        if 'TranscodingUrl' not in source:
            raise Exception("use get_sources to get transcoding url")

        self.info['Method'] = "Transcode"

        if self.item['MediaType'] == 'Video':
            base, params = source['TranscodingUrl'].split('?')
            url_parsed = params.split('&')
            manual_tracks = ''

            # manual bitrate
            url_parsed = [p for p in url_parsed if 'AudioBitrate' not in p and 'VideoBitrate' not in p]

            if settings('skipDialogTranscode') != Transcode.Enabled and source.get('MediaStreams'):
                # manual tracks
                url_parsed = [p for p in url_parsed if 'AudioStreamIndex' not in p and 'SubtitleStreamIndex' not in p]
                manual_tracks = self.get_audio_subs(source, audio, subtitle)

            audio_bitrate = self.get_transcoding_audio_bitrate()
            video_bitrate = self.get_max_bitrate() - audio_bitrate

            params = "%s%s" % ('&'.join(url_parsed), manual_tracks)
            params += "&VideoBitrate=%s&AudioBitrate=%s" % (video_bitrate, audio_bitrate)

            video_type = 'live' if source['Protocol'] == 'LiveTV' else 'master'
            base = base.replace('stream' if 'stream' in base else 'master', video_type, 1)
            self.info['Path'] = "%s%s?%s" % (self.info['ServerAddress'], base, params)
            self.info['Path'] += "&maxWidth=%s&maxHeight=%s" % (self.get_resolution())
        else:
            self.info['Path'] = "%s/%s" % (self.info['ServerAddress'], source['TranscodingUrl'])

        return self.info['Path']

    def direct_play(self, source):

        API = api.API(self.item, self.info['ServerAddress'])
        self.info['Method'] = "DirectPlay"
        self.info['Path'] = API.get_file_path(source.get('Path'))

        return self.info['Path']

    def direct_url(self, source):

        self.info['Method'] = "DirectStream"

        if self.item['Type'] == "Audio":
            self.info['Path'] = "%s/Audio/%s/stream.%s?static=true&api_key=%s" % (
                self.info['ServerAddress'],
                self.item['Id'],
                source.get('Container', "mp4").split(',')[0],
                self.info['Token']
            )
        else:
            self.info['Path'] = "%s/Videos/%s/stream?static=true&MediaSourceId=%s&api_key=%s" % (
                self.info['ServerAddress'],
                self.item['Id'],
                source['Id'],
                self.info['Token']
            )

        return self.info['Path']

    def get_max_bitrate(self):

        ''' Get the video quality based on add-on settings.
            Max bit rate supported by server: 2147483 (max signed 32bit integer)
        '''
        bitrate = [500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 6000,
                   7000, 8000, 9000, 10000, 12000, 14000, 16000, 18000,
                   20000, 25000, 30000, 35000, 40000, 100000, 1000000, 2147483]
        return bitrate[int(settings('maxBitrate') or 24)] * 1000

    def get_resolution(self):
        return int(xbmc.getInfoLabel('System.ScreenWidth')), int(xbmc.getInfoLabel('System.ScreenHeight'))

    def get_directplay_video_codec(self):
        codecs = ['h264', 'hevc', 'h265', 'mpeg4', 'mpeg2video', 'vc1', 'vp9', 'av1']

        if settings('transcode_h265.bool'):
            codecs.remove('hevc')
            codecs.remove('h265')

        if settings('transcode_mpeg2.bool'):
            codecs.remove('mpeg2video')

        if settings('transcode_vc1.bool'):
            codecs.remove('vc1')

        if settings('transcode_vp9.bool'):
            codecs.remove('vp9')

        if settings('transcode_av1.bool'):
            codecs.remove('av1')

        return ','.join(codecs)

    def get_transcoding_video_codec(self):
        codecs = ['h264', 'hevc', 'h265', 'mpeg4', 'mpeg2video', 'vc1']

        if settings('transcode_h265.bool'):
            codecs.remove('hevc')
            codecs.remove('h265')
        else:
            if settings('videoPreferredCodec') == 'H265/HEVC':
                codecs.insert(2, codecs.pop(codecs.index('h264')))

        if settings('transcode_mpeg2.bool'):
            codecs.remove('mpeg2video')

        if settings('transcode_vc1.bool'):
            codecs.remove('vc1')

        return ','.join(codecs)

    def get_transcoding_audio_codec(self):
        codecs = ['aac', 'mp3', 'ac3', 'opus', 'flac', 'vorbis']

        preferred = settings('audioPreferredCodec').lower()
        if preferred in codecs:
            codecs.insert(0, codecs.pop(codecs.index(preferred)))

        return ','.join(codecs)

    def get_transcoding_audio_bitrate(self):
        bitrate = [96, 128, 160, 192, 256, 320, 384]
        return bitrate[int(settings('audioBitrate') or 6)] * 1000

    def get_device_profile(self):

        ''' Get device profile based on the add-on settings.
        '''
        profile = {
            "Name": "Kodi",
            "MaxStaticBitrate": self.get_max_bitrate(),
            "MaxStreamingBitrate": self.get_max_bitrate(),
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,
            "TranscodingProfiles": [
                {
                    "Type": "Video",
                    "Container": "m3u8",
                    "AudioCodec": self.get_transcoding_audio_codec(),
                    "VideoCodec": self.get_transcoding_video_codec(),
                    "MaxAudioChannels": settings('audioMaxChannels')
                },
                {
                    "Type": "Audio"
                },
                {
                    "Type": "Photo",
                    "Container": "jpeg"
                }
            ],
            "DirectPlayProfiles": [
                {
                    "Type": "Video",
                    "VideoCodec": self.get_directplay_video_codec()
                },
                {
                    "Type": "Audio"
                },
                {
                    "Type": "Photo"
                }
            ],
            "ResponseProfiles": [],
            "ContainerProfiles": [],
            "CodecProfiles": [],
            "SubtitleProfiles": [
                {
                    "Format": "srt",
                    "Method": "External"
                },
                {
                    "Format": "srt",
                    "Method": "Embed"
                },
                {
                    "Format": "ass",
                    "Method": "External"
                },
                {
                    "Format": "ass",
                    "Method": "Embed"
                },
                {
                    "Format": "sub",
                    "Method": "Embed"
                },
                {
                    "Format": "sub",
                    "Method": "External"
                },
                {
                    "Format": "ssa",
                    "Method": "Embed"
                },
                {
                    "Format": "ssa",
                    "Method": "External"
                },
                {
                    "Format": "smi",
                    "Method": "Embed"
                },
                {
                    "Format": "smi",
                    "Method": "External"
                },
                {
                    "Format": "pgssub",
                    "Method": "Embed"
                },
                {
                    "Format": "pgssub",
                    "Method": "External"
                },
                {
                    "Format": "dvdsub",
                    "Method": "Embed"
                },
                {
                    "Format": "dvdsub",
                    "Method": "External"
                },
                {
                    "Format": "pgs",
                    "Method": "Embed"
                },
                {
                    "Format": "pgs",
                    "Method": "External"
                }
            ]
        }

        if settings('transcodeHi10P.bool'):
            profile['CodecProfiles'].append(
                {
                    'Type': 'Video',
                    'codec': 'h264',
                    'Conditions': [
                        {
                            'Condition': "LessThanEqual",
                            'Property': "VideoBitDepth",
                            'Value': "8"
                        }
                    ]
                }
            )

        if settings('transcode_h265_rext.bool'):
            profile['CodecProfiles'].append(
                {
                    'Type': 'Video',
                    'codec': 'h265,hevc',
                    'Conditions': [
                        {
                            'Condition': "EqualsAny",
                            'Property': "VideoProfile",
                            'Value': "main|main 10"
                        }
                    ]
                }
            )

        if self.info['ForceTranscode']:
            profile['DirectPlayProfiles'] = []

        if self.item['Type'] == 'TvChannel':
            profile['TranscodingProfiles'].insert(0, {
                "Container": "ts",
                "Type": "Video",
                "AudioCodec": "mp3,aac",
                "VideoCodec": "h264",
                "Context": "Streaming",
                "Protocol": "hls",
                "MaxAudioChannels": "2",
                "MinSegments": "1",
                "BreakOnNonKeyFrames": True
            })

        return profile

    def set_external_subs(self, source, listitem):

        ''' Try to download external subs locally, so we can label them.
            Since Jellyfin returns all possible tracks together, sort them.
            IsTextSubtitleStream if true, is available to download from server.
        '''
        if not settings('enableExternalSubs.bool') or not source['MediaStreams']:
            return

        subs = []
        mapping = {}
        kodi = 0

        server_settings = self.api_client.get_transcode_settings()

        for stream in source['MediaStreams']:
            if stream['SupportsExternalStream'] and stream['Type'] == 'Subtitle' and stream['DeliveryMethod'] == 'External':
                if not stream['IsExternal'] and not server_settings['EnableSubtitleExtraction']:
                    continue

                index = stream['Index']
                url = self.get_subtitles(source, stream, index)

                if url is None:
                    continue

                LOG.info("[ subtitles/%s ] %s", index, url)

                if 'Language' in stream:
                    filename = "%s.%s.%s" % (source['Id'], stream['Language'], stream['Codec'])

                    try:
                        subs.append(self.download_external_subs(url, filename))
                    except Exception as error:
                        LOG.exception(error)
                        subs.append(url)
                else:
                    subs.append(url)

                mapping[kodi] = index
                kodi += 1

        listitem.setSubtitles(subs)
        self.item['PlaybackInfo']['Subtitles'] = mapping

    @classmethod
    def download_external_subs(cls, src, filename):

        ''' Download external subtitles to temp folder
            to be able to have proper names to streams.
        '''
        temp = translate_path("special://profile/addon_data/plugin.video.jellyfin/temp/")

        if not xbmcvfs.exists(temp):
            xbmcvfs.mkdir(temp)

        path = os.path.join(temp, filename)

        try:
            response = requests.get(src, stream=True, verify=settings('sslverify.bool'))
            response.raise_for_status()
        except Exception as error:
            LOG.exception(error)
            raise
        else:
            response.encoding = 'utf-8'
            with open(path, 'wb') as f:
                f.write(response.content)
                del response

        return path

    def get_audio_subs(self, source, audio=None, subtitle=None):

        ''' For transcoding only
            Present the list of audio/subs to select from, before playback starts.

            Since Jellyfin returns all possible tracks together, sort them.
            IsTextSubtitleStream if true, is available to download from server.
        '''
        prefs = ""
        audio_streams = list()
        subs_streams = list()
        streams = source['MediaStreams']

        server_settings = self.api_client.get_transcode_settings()
        allow_burned_subs = settings('allowBurnedSubs.bool')

        for stream in streams:

            index = stream['Index']
            stream_type = stream['Type']

            if stream_type == 'Audio':

                audio_streams.append(index)

            elif stream_type == 'Subtitle':
                if stream['IsExternal']:
                    if not stream['SupportsExternalStream'] and not allow_burned_subs:
                        continue
                else:
                    avail_for_extraction = stream['SupportsExternalStream'] and server_settings['EnableSubtitleExtraction']
                    if not avail_for_extraction and not allow_burned_subs:
                        continue

                subs_streams.append(index)

        skip_dialog = int(settings('skipDialogTranscode') or 0)

        def get_track_title(track_index):
            return streams[track_index]['DisplayTitle'] or ("Track %s" % track_index)

        # Select audio stream
        audio_selected = None

        if skip_dialog == Transcode.MediaDefault:
            # NOTE: "DefaultAudioStreamIndex" is the default according to Jellyfin.
            #       The media's default is marked by the "IsDefault" value.
            for track_index in audio_streams:
                if streams[track_index]['IsDefault']:
                    audio = track_index
                    break

        # Compare to None in the off-chance the track index is 0.
        if audio is not None:
            audio_selected = audio

        elif skip_dialog in (Transcode.Enabled, Transcode.Audio):
            if len(audio_streams) > 1:
                selection = list(map(get_track_title, audio_streams))
                resp = dialog("select", translate(33013), selection)
                if resp > -1:
                    audio_selected = audio_streams[resp]
                else:
                    audio_selected = source['DefaultAudioStreamIndex']
            elif audio_streams:
                # Only one choice
                audio_selected = audio_streams[0]

        else:
            audio_selected = source['DefaultAudioStreamIndex']

        if audio_selected is not None:
            self.info['AudioStreamIndex'] = audio_selected
            prefs += "&AudioStreamIndex=%s" % audio_selected

        # Select audio stream
        subtitle_selected = None

        if skip_dialog == Transcode.MediaDefault:
            for track_index in subs_streams:
                if streams[track_index]['IsDefault']:
                    subtitle = track_index
                    break

        if subtitle is not None:
            subtitle_selected = subtitle

        elif skip_dialog in (Transcode.Enabled, Transcode.Subtitle) and subs_streams:
            selection = list(['No subtitles']) + list(map(get_track_title, subs_streams))
            resp = dialog("select", translate(33014), selection) - 1
            # Possible responses:
            # >=0  Subtitle track
            #  -1  No subtitles (Default)
            #  -2  Dialog was cancelled
            if resp > -1:
                track_index = subs_streams[resp]
                subtitle_selected = track_index

        if subtitle_selected is not None:
            server_settings = self.api_client.get_transcode_settings()
            stream = streams[track_index]
            if server_settings['EnableSubtitleExtraction'] and stream['SupportsExternalStream']:
                self.info['SubtitleUrl'] = self.get_subtitles(source, stream, subtitle_selected)
                self.info['SubtitleStreamIndex'] = subtitle_selected
            elif allow_burned_subs:
                prefs += "&SubtitleStreamIndex=%s" % subtitle_selected
                self.info['SubtitleStreamIndex'] = subtitle_selected

        return prefs

    def get_subtitles(self, source, stream, index):

        if stream['IsTextSubtitleStream'] and 'DeliveryUrl' in stream and stream['DeliveryUrl'].lower().startswith('/videos'):
            url = "%s%s" % (self.info['ServerAddress'], stream['DeliveryUrl'])
        else:
            url = "%s/Videos/%s/%s/Subtitles/%s/Stream.%s?api_key=%s" % (
                self.info['ServerAddress'],
                self.item['Id'],
                source['Id'],
                index,
                stream['Codec'],
                self.info['Token']
            )

        return url
