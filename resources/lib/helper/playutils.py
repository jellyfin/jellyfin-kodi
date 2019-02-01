# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
from uuid import uuid4

import xbmc
import xbmcvfs

import api
import database
import client
import collections
import requests
from . import _, settings, window, dialog
from downloader import TheVoid
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


def set_properties(item, method, server_id=None):

    ''' Set all properties for playback detection.
    '''
    info = item.get('PlaybackInfo') or {}

    current = window('emby_play.json') or []
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

    window('emby_play.json', current)

class PlayUtils(object):


    def __init__(self, item, force_transcode=False, server_id=None, server=None, token=None):

        ''' Item will be updated with the property PlaybackInfo, which
            holds all the playback information.
        '''
        self.item = item
        self.item['PlaybackInfo'] = {}
        self.info = {
            'ServerId': server_id,
            'ServerAddress': server,
            'ForceTranscode': force_transcode,
            'Token': token or TheVoid('GetToken', {'ServerId': server_id}).get()
        }

    def get_sources(self, source_id=None):

        ''' Return sources based on the optional source_id or the device profile.
        '''
        params = {
            'ServerId': self.info['ServerId'],
            'Id': self.item['Id'],
            'Profile': self.get_device_profile()
        }
        info = TheVoid('GetPlaybackInfo', params).get()
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

            resp = dialog("select", _(33130), selection)

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

        path = self.direct_play(source)

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
            prop: embyfilename for ?? I thought it was to pass the real path to subtitle add-ons but it's not working?
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

        elif source['SupportsDirectStream']:

            LOG.info("--[ direct stream ]")
            self.direct_url(source)

        else:
            LOG.info("--[ transcode ]")
            self.transcode(source, audio, subtitle)

        self.info['AudioStreamIndex'] = self.info.get('AudioStreamIndex') or source.get('DefaultAudioStreamIndex')
        self.info['SubtitleStreamIndex'] = self.info.get('SubtitleStreamIndex') or source.get('DefaultSubtitleStreamIndex')
        self.item['PlaybackInfo'].update(self.info)

        API = api.API(self.item, self.info['ServerAddress'])
        window('embyfilename', value=API.get_file_path(source.get('Path')).encode('utf-8'))

    def live_stream(self, source):

        ''' Get live stream media info.
        '''
        params = {
            'ServerId': self.info['ServerId'],
            'Id': self.item['Id'],
            'Profile': self.get_device_profile(),
            'PlaySessionId': self.info['PlaySessionId'],
            'Token': source['OpenToken']
        }
        info = TheVoid('GetLiveStream', params).get()
        LOG.info(info)

        if info['MediaSource'].get('RequiresClosing'):
            self.info['LiveStreamId'] = source['LiveStreamId']

        return info['MediaSource']

    def transcode(self, source, audio=None, subtitle=None):

        if not 'TranscodingUrl' in source:
            raise Exception("use get_sources to get transcoding url")

        self.info['Method'] = "Transcode"

        if self.item['MediaType'] == 'Video':
            base, params = source['TranscodingUrl'].split('?')

            if settings('skipDialogTranscode') != "3" and source.get('MediaStreams'):
                url_parsed = params.split('&')

                for i in url_parsed:
                    if 'AudioStreamIndex' in i or 'AudioBitrate' in i or 'SubtitleStreamIndex' in i: # handle manually
                        url_parsed.remove(i)

                params = "%s%s" % ('&'.join(url_parsed), self.get_audio_subs(source, audio, subtitle))

            video_type = 'live' if source['Protocol'] == 'LiveTV' else 'master'
            base = base.replace('stream' if 'stream' in base else 'master', video_type, 1)
            self.info['Path'] = "%s/emby%s?%s" % (self.info['ServerAddress'], base, params)
            self.info['Path'] += "&maxWidth=%s&maxHeight=%s" % (self.get_resolution())
        else:
            self.info['Path'] = "%s/emby%s" % (self.info['ServerAddress'], source['TranscodingUrl'])

        return self.info['Path']

    def direct_play(self, source):

        API = api.API(self.item, self.info['ServerAddress'])
        self.info['Method'] = "DirectPlay"
        self.info['Path'] = API.get_file_path(source.get('Path'))

        return self.info['Path']

    def direct_url(self, source):

        self.info['Method'] = "DirectStream"

        if self.item['Type'] == "Audio":
            self.info['Path'] = ("%s/emby/Audio/%s/stream.%s?static=true&api_key=%s" %
                                (self.info['ServerAddress'], self.item['Id'],
                                 source.get('Container', "mp4").split(',')[0],
                                 self.info['Token']))
        else:
            self.info['Path'] = ("%s/emby/Videos/%s/stream?static=true&MediaSourceId=%s&api_key=%s" %
                                (self.info['ServerAddress'], self.item['Id'], source['Id'], self.info['Token']))

        return self.info['Path']

    def get_bitrate(self):

        ''' Get the video quality based on add-on settings.
            Max bit rate supported by server: 2147483 (max signed 32bit integer)
        '''
        bitrate = [664, 996, 1320, 2000, 3200,
                   4700, 6200, 7700, 9200, 10700,
                   12200, 13700, 15200, 16700, 18200,
                   20000, 25000, 30000, 35000, 40000,
                   100000, 1000000, 2147483]
        return bitrate[int(settings('videoBitrate') or 22)]

    def get_resolution(self):
        return int(xbmc.getInfoLabel('System.ScreenWidth')), int(xbmc.getInfoLabel('System.ScreenHeight'))

    def get_device_profile(self):

        ''' Get device profile based on the add-on settings.
        '''
        profile = {
            "Name": "Kodi",
            "MaxStreamingBitrate": self.get_bitrate() * 1000,
            "MusicStreamingTranscodingBitrate": 1280000,
            "TimelineOffsetSeconds": 5,
            "TranscodingProfiles": [
                {
                    "Type": "Audio"
                },
                {
                    "Container": "m3u8",
                    "Type": "Video",
                    "AudioCodec": "aac,mp3,ac3,opus,flac,vorbis",
                    "VideoCodec": "h264,mpeg4,mpeg2video",
                    "MaxAudioChannels": "6"
                },
                {
                    "Container": "jpeg",
                    "Type": "Photo"
                }
            ],
            "DirectPlayProfiles": [
                {
                    "Type": "Video"
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
        if settings('transcode_h265.bool'):
            profile['DirectPlayProfiles'][0]['VideoCodec'] = "h264,mpeg4,mpeg2video"
        else:
            profile['TranscodingProfiles'].insert(0, {
                "Container": "m3u8",
                "Type": "Video",
                "AudioCodec": "aac,mp3,ac3,opus,flac,vorbis",
                "VideoCodec": "h264,h265,hevc,mpeg4,mpeg2video",
                "MaxAudioChannels": "6"
            })

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

        ''' Try to download external subs locally so we can label them.
            Since Emby returns all possible tracks together, sort them.
            IsTextSubtitleStream if true, is available to download from server.
        '''
        if not settings('enableExternalSubs.bool') or not source['MediaStreams']:
            return

        subs = []
        mapping = {}
        kodi = 0

        for stream in source['MediaStreams']:

            if stream['Type'] == 'Subtitle' and stream['IsExternal']:
                index = stream['Index']

                if 'DeliveryUrl' in stream and stream['DeliveryUrl'].lower().startswith('/videos'):
                    url = "%s/emby%s" % (self.info['ServerAddress'], stream['DeliveryUrl'])
                else:
                    url = self.get_subtitles(source, stream, index)

                if url is None:
                    continue

                LOG.info("[ subtitles/%s ] %s", index, url)

                if 'Language' in stream:
                    filename = "Stream.%s.%s" % (stream['Language'].encode('utf-8'), stream['Codec'].encode('utf-8'))

                    try:
                        subs.append(self.download_external_subs(url, filename))
                    except Exception as error:
                        LOG.error(error)
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
        temp = xbmc.translatePath("special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

        if not xbmcvfs.exists(temp):
            xbmcvfs.mkdir(temp)

        path = os.path.join(temp, filename)

        try:
            response = requests.get(src, stream=True, verify=False)
            response.raise_for_status()
        except Exception as e:
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

            Since Emby returns all possible tracks together, sort them.
            IsTextSubtitleStream if true, is available to download from server.
        '''
        prefs = ""
        audio_streams = collections.OrderedDict()
        subs_streams = collections.OrderedDict()
        streams = source['MediaStreams']

        for stream in streams:

            index = stream['Index']
            stream_type = stream['Type']

            if stream_type == 'Audio':

                codec = stream['Codec']
                channel = stream.get('ChannelLayout', "")

                if 'Language' in stream:
                    track = "%s - %s - %s %s" % (index, stream['Language'], codec, channel)
                else:
                    track = "%s - %s %s" % (index, codec, channel)

                audio_streams[track] = index

            elif stream_type == 'Subtitle':

                if 'Language' in stream:
                    track = "%s - %s" % (index, stream['Language'])
                else:
                    track = "%s - %s" % (index, stream['Codec'])

                if stream['IsDefault']:
                    track = "%s - Default" % track
                if stream['IsForced']:
                    track = "%s - Forced" % track

                subs_streams[track] = index

        skip_dialog = int(settings('skipDialogTranscode') or 0)
        audio_selected = None

        if audio:
            audio_selected = audio

        elif skip_dialog in (0, 1):
            if len(audio_streams) > 1:

                selection = list(audio_streams.keys())
                resp = dialog("select", _(33013), selection)
                audio_selected = audio_streams[selection[resp]] if resp else source['DefaultAudioStreamIndex']
            else: # Only one choice
                audio_selected = audio_streams[next(iter(audio_streams))]
        else:
            audio_selected = source['DefaultAudioStreamIndex']

        self.info['AudioStreamIndex'] = audio_selected
        prefs += "&AudioStreamIndex=%s" % audio_selected
        prefs += "&AudioBitrate=384000" if streams[audio_selected].get('Channels', 0) > 2 else "&AudioBitrate=192000"

        if subtitle:

            index = subtitle
            server_settings = TheVoid('GetTranscodeOptions', {'ServerId': self.info['ServerId']}).get()
            stream = streams[index]

            if server_settings['EnableSubtitleExtraction'] and stream['SupportsExternalStream']:
                self.info['SubtitleUrl'] = self.get_subtitles(source, stream, index)
            else:
                prefs += "&SubtitleStreamIndex=%s" % index

            self.info['SubtitleStreamIndex'] = index

        elif skip_dialog in (0, 2) and len(subs_streams):

            selection = list(['No subtitles']) + list(subs_streams.keys())
            resp = dialog("select", _(33014), selection)

            if resp:
                index = subs_streams[selection[resp]] if resp > -1 else source.get('DefaultSubtitleStreamIndex')

                if index is not None:

                    server_settings = TheVoid('GetTranscodeOptions', {'ServerId': self.info['ServerId']}).get()
                    stream = streams[index]

                    if server_settings['EnableSubtitleExtraction'] and stream['SupportsExternalStream']:
                        self.info['SubtitleUrl'] = self.get_subtitles(source, stream, index)
                    else:
                        prefs += "&SubtitleStreamIndex=%s" % index

                self.info['SubtitleStreamIndex'] = index

        return prefs

    def get_subtitles(self, source, stream, index):

        if stream['IsTextSubtitleStream'] and 'DeliveryUrl' in stream and stream['DeliveryUrl'].lower().startswith('/videos'):
            url = "%s/emby%s" % (self.info['ServerAddress'], stream['DeliveryUrl'])
        else:
            url = ("%s/emby/Videos/%s/%s/Subtitles/%s/Stream.%s?api_key=%s" %
                  (self.info['ServerAddress'], self.item['Id'], source['Id'], index, stream['Codec'], self.info['Token']))

        return url
