# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os

import xbmc
import xbmcvfs

from helper import _, window, settings, dialog, JSONRPC
from emby import Emby

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Player(xbmc.Player):

    # Borg - multiple instances, shared state
    _shared_state = {}
    played = {}

    def __init__(self):

        self.__dict__ = self._shared_state
        xbmc.Player.__init__(self)

    def onPlayBackStarted(self):

        ''' We may need to wait for info to be set in kodi monitor.
            Accounts for scenario where Kodi starts playback and exits immediately.
        '''
        count = 0
        monitor = xbmc.Monitor()

        try:
            current_file = self.getPlayingFile()
        except Exception:

            while count < 5:
                try:
                    current_file = self.getPlayingFile()
                    count = 0
                    break
                except Exception:
                    count += 1

                if monitor.waitForAbort(1):
                    return
            else:
                LOG.info('Cancel playback report')

                return

        items = window('emby_play.json')
        item = None

        while not items:

            if monitor.waitForAbort(2):
                return

            items = window('emby_play.json')
            count += 1

            if count == 20:
                LOG.info("Could not find emby prop...")

                return

        for item in items:
            if item['Path'] == current_file.decode('utf-8'):
                items.pop(items.index(item))

                break
        else:
            item = items[0]
            items.pop(0)

        window('emby_play.json', items)

        self.set_item(current_file, item)
        data = {
            'QueueableMediaTypes': "Video,Audio",
            'CanSeek': True,
            'ItemId': item['Id'],
            'MediaSourceId': item['MediaSourceId'],
            'PlayMethod': item['PlayMethod'],
            'VolumeLevel': item['Volume'],
            'PositionTicks': int(item['CurrentPosition'] * 10000000),
            'IsPaused': item['Paused'],
            'IsMuted': item['Muted'],
            'PlaySessionId': item['PlaySessionId'],
            'AudioStreamIndex': item['AudioStreamIndex'],
            'SubtitleStreamIndex': item['SubtitleStreamIndex']
        }
        item['Server']['api'].session_playing(data)
        window('emby.skip.%s.bool' % item['Id'], True)

        if monitor.waitForAbort(2):
            return

        self.set_audio_subs(item['AudioStreamIndex'], item['SubtitleStreamIndex'])

    def set_item(self, file, item):

        ''' Set playback information.
        '''
        try:
            item['Runtime'] = int(item['Runtime'])
        except ValueError:
            try:
                item['Runtime'] = int(self.getTotalTime())
                LOG.info("Runtime is missing, Kodi runtime: %s" % item['Runtime'])
            except Exception:
                item['Runtime'] = 0
                LOG.info("Runtime is missing, Using Zero")

        try:
            seektime = self.getTime()
        except Exception: # at this point we should be playing and if not then bail out
            return

        result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        volume = result.get('volume')
        muted = result.get('muted')

        item.update({
            'File': file,
            'CurrentPosition': item.get('CurrentPosition') or int(seektime),
            'Muted': muted,
            'Volume': volume,
            'Server': Emby(item['ServerId']),
            'Paused': False
        })

        self.played[file] = item
        LOG.info("-->[ play/%s ] %s", item['Id'], item)

    def set_audio_subs(self, audio=None, subtitle=None):

        ''' Only for after playback started
        '''
        LOG.info("Setting audio: %s subs: %s", audio, subtitle)
        current_file = self.getPlayingFile()

        if current_file in self.played:

            item = self.played[current_file]
            mapping = item['SubsMapping']

            if audio and len(self.getAvailableAudioStreams()) > 1:
                self.setAudioStream(audio - 1)

            if subtitle is None:
                return

            tracks = len(self.getAvailableAudioStreams())

            if subtitle == -1:
                self.showSubtitles(False)

            elif mapping:
                for index in mapping:

                    if mapping[index] == subtitle:
                        self.setSubtitleStream(int(index))

                        break
                else:
                    self.setSubtitleStream(len(mapping) + subtitle - tracks - 1)
            else:
                self.setSubtitleStream(subtitle - tracks - 1)

    def detect_audio_subs(self, item):

        params = {
            'playerid': 1,
            'properties': ["currentsubtitle","currentaudiostream","subtitleenabled"]
        }
        result = JSONRPC('Player.GetProperties').execute(params)
        result = result.get('result')

        try: # Audio tracks
            audio = result['currentaudiostream']['index']
        except (KeyError, TypeError):
            audio = 0
        
        try: # Subtitles tracks
            subs = result['currentsubtitle']['index']
        except (KeyError, TypeError):
            subs = 0

        try: # If subtitles are enabled
            subs_enabled = result['subtitleenabled']
        except (KeyError, TypeError):
            subs_enabled = False

        item['AudioStreamIndex'] = audio + 1

        if not subs_enabled or not len(self.getAvailableSubtitleStreams()):
            item['SubtitleStreamIndex'] = None

            return

        mapping = item['SubsMapping']
        tracks = len(self.getAvailableAudioStreams())

        if mapping:
            if str(subs) in mapping:
                item['SubtitleStreamIndex'] = mapping[str(subs)]
            else:
                item['SubtitleStreamIndex'] = subs - len(mapping) + tracks + 1
        else:
            item['SubtitleStreamIndex'] = subs + tracks + 1

    def onPlayBackPaused(self):
        current_file = self.getPlayingFile()

        if current_file in self.played:

            self.played[current_file]['Paused'] = True
            self.report_playback()
            LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        current_file = self.getPlayingFile()

        if current_file in self.played:

            self.played[current_file]['Paused'] = False
            self.report_playback()
            LOG.debug("--<[ paused ]")

    def onPlayBackSeek(self, time, seekOffset):

        ''' Does not seem to work??
        '''
        current_file = self.getPlayingFile()

        if current_file in self.played:

            self.report_playback()
            LOG.debug("--[ seek ]")

    def report_playback(self, report=True):

        ''' Report playback progress to emby server.
            Check if the user seek.
        '''
        current_file = self.getPlayingFile()

        if current_file not in self.played:
            return

        item = self.played[current_file]

        if not report:

            previous = item['CurrentPosition']
            item['CurrentPosition'] = int(self.getTime())

            if (item['CurrentPosition'] - previous) < 30:

                return

        result = JSONRPC('Application.GetProperties').execute({'properties': ["volume", "muted"]})
        result = result.get('result', {})
        item['Volume'] = result.get('volume')
        item['Muted'] = result.get('muted')
        item['CurrentPosition'] = int(self.getTime())
        self.detect_audio_subs(item)

        data = {
            'QueueableMediaTypes': "Video,Audio",
            'CanSeek': True,
            'ItemId': item['Id'],
            'MediaSourceId': item['MediaSourceId'],
            'PlayMethod': item['PlayMethod'],
            'VolumeLevel': item['Volume'],
            'PositionTicks': int(item['CurrentPosition'] * 10000000),
            'IsPaused': item['Paused'],
            'IsMuted': item['Muted'],
            'PlaySessionId': item['PlaySessionId'],
            'AudioStreamIndex': item['AudioStreamIndex'],
            'SubtitleStreamIndex': item['SubtitleStreamIndex']
        }
        item['Server']['api'].session_progress(data)

    def onPlayBackStopped(self):
        
        ''' Will be called when user stops playing a file.
        '''
        window('emby_play', clear=True)
        self.stop_playback()
        LOG.debug("--<[ playback ]")

    def onPlayBackEnded(self):
        
        ''' Will be called when kodi stops playing a file.
        '''
        self.stop_playback()
        LOG.debug("--<<[ playback ]")

    def stop_playback(self):
        
        ''' Stop all playback. Check for external player for positionticks.
        '''
        if not self.played:
            return

        LOG.info("Played info: %s", self.played)

        for file in self.played:
            item = self.played[file]

            if item:
                window('emby.skip.%s.bool' % item['Id'], True)

                if item['CurrentPosition'] and item['Runtime']:

                    try:
                        if window('emby.external.bool'):
                            window('emby.external', clear=True)
                            raise ValueError

                        played = (item['CurrentPosition'] * 10000000) / int(item['Runtime'])
                    except ZeroDivisionError: # Runtime is 0.
                        played = 0
                    except ValueError:
                        played = 100
                        item['CurrentPosition'] = int(item['Runtime'])

                    marker = float(settings('markPlayed')) / 100
                    delete = False

                    if item['Type'] == 'Episode' and settings('deleteTV.bool'):
                        delete = True
                    elif item['Type'] == 'Movie' and settings('deleteMovies.bool'):
                        delete = True

                    if not settings('offerDelete.bool'):
                        delete = False

                    if played >= marker and delete:

                        if dialog("yesno", heading=_(30091), line1=_(33015), autoclose=120000):
                            item['Server']['api'].delete_item(item['Id'])

                data = {
                    'ItemId': item['Id'],
                    'MediaSourceId': item['MediaSourceId'],
                    'PositionTicks': int(item['CurrentPosition'] * 10000000),
                    'PlaySessionId': item['PlaySessionId']
                }
                item['Server']['api'].session_stop(data)

                if item.get('LiveStreamId'):
                    item['Server']['api'].close_live_stream(item['LiveStreamId'])

                elif item['PlayMethod'] == 'Transcode':

                    LOG.info("Transcoding for %s terminated.", item['Id'])
                    item['Server']['api'].close_transcode(item['DeviceId'])


                path = xbmc.translatePath("special://profile/addon_data/plugin.video.emby/temp/").decode('utf-8')

                if xbmcvfs.exists(path):
                    dirs, files = xbmcvfs.listdir(path)

                    for file in files:
                        xbmcvfs.delete(os.path.join(path, file.decode('utf-8')))

                window('emby.external_check', clear=True)

        self.played.clear()
