# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import binascii
import json
import threading

from kodi_six import xbmc

import player
from client import get_device_id
from objects import PlaylistWorker, on_play, on_update, special_listener
from helper import settings, dialog, JSONRPC
from helper.utils import JsonDebugPrinter
from jellyfin import Jellyfin
from helper import LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


class Monitor(xbmc.Monitor):
    sleep = False

    def __init__(self):

        self.player = player.Player()
        self.device_id = get_device_id()
        self.listener = Listener(self)
        self.listener.start()
        xbmc.Monitor.__init__(self)

    def onScanStarted(self, library):
        LOG.info("-->[ kodi scan/%s ]", library)

    def onScanFinished(self, library):
        LOG.info("--<[ kodi scan/%s ]", library)

    def onNotification(self, sender, method, data):

        if sender.lower() not in ('plugin.video.jellyfin', 'xbmc', 'upnextprovider.signal'):
            return

        if sender == 'plugin.video.jellyfin':
            method = method.split('.')[1]

            if method not in ('ReportProgressRequested', 'LoadServer', 'AddUser', 'PlayPlaylist', 'Play', 'Playstate', 'GeneralCommand'):
                return

            data = json.loads(data)[0]

        elif sender.startswith('upnextprovider'):
            LOG.info('Attempting to play the next episode via upnext')
            method = method.split('.', 1)[1]

            if method not in ('plugin.video.jellyfin_play_action',):
                LOG.info('Received invalid upnext method: %s', method)
                return

            data = json.loads(data)
            method = "Play"

            if data:
                data = json.loads(binascii.unhexlify(data[0]))
        else:
            if method not in ('Player.OnPlay', 'VideoLibrary.OnUpdate', 'Player.OnAVChange'):

                ''' We have to clear the playlist if it was stopped before it has been played completely.
                    Otherwise the next played item will be added the previous queue.
                '''
                if method == "Player.OnStop":
                    xbmc.sleep(3000)  # let's wait for the player so we don't clear the canceled playlist by mistake.

                    if xbmc.getCondVisibility("!Player.HasMedia + !Window.IsVisible(busydialog)"):

                        xbmc.executebuiltin("Playlist.Clear")
                        LOG.info("[ playlist ] cleared")

                return

            data = json.loads(data)

        LOG.debug("[ %s: %s ] %s", sender, method, JsonDebugPrinter(data))

        if self.sleep:
            LOG.info("System.OnSleep detected, ignore monitor request.")

            return

        server = Jellyfin(data.get('ServerId')).get_client()

        if method == 'Play':

            items = server.jellyfin.get_items(data['ItemIds'])

            PlaylistWorker(data.get('ServerId'), items, data['PlayCommand'] == 'PlayNow',
                           data.get('StartPositionTicks', 0), data.get('AudioStreamIndex'),
                           data.get('SubtitleStreamIndex')).start()

        # TODO no clue if this is called by anything
        elif method == 'PlayPlaylist':

            server.jellyfin.post_session(server.config.data['app.session'], "Playing", {
                'PlayCommand': "PlayNow",
                'ItemIds': data['Id'],
                'StartPositionTicks': 0
            })

        elif method in ('ReportProgressRequested', 'Player.OnAVChange'):
            self.player.report_playback(data.get('Report', True))

        elif method == 'Playstate':
            self.playstate(data)

        elif method == 'GeneralCommand':
            self.general_commands(data)

        elif method == 'LoadServer':
            Jellyfin(data['ServerId']).get_client().register_client()

        elif method == 'AddUser':
            server.jellyfin.session_add_user(server.config.data['app.session'], data['Id'], data['Add'])
            Jellyfin.additional_users(server, self.device_id)

        elif method == 'Player.OnPlay':
            on_play(data, server)

        elif method == 'VideoLibrary.OnUpdate':
            on_update(data, server)

    def playstate(self, data):

        ''' Jellyfin playstate updates.
        '''
        command = data['Command']
        actions = {
            'Stop': self.player.stop,
            'Unpause': self.player.pause,
            'Pause': self.player.pause,
            'PlayPause': self.player.pause,
            'NextTrack': self.player.playnext,
            'PreviousTrack': self.player.playprevious
        }
        if command == 'Seek':

            if self.player.isPlaying():

                seektime = data['SeekPositionTicks'] / 10000000.0
                self.player.seekTime(seektime)
                LOG.info("[ seek/%s ]", seektime)

        elif command in actions:

            actions[command]()
            LOG.info("[ command/%s ]", command)

    def general_commands(self, data):

        ''' General commands from Jellyfin to control the Kodi interface.
        '''
        command = data['Name']
        args = data['Arguments']

        if command in ('Mute', 'Unmute', 'SetVolume',
                       'SetSubtitleStreamIndex', 'SetAudioStreamIndex', 'SetRepeatMode'):

            if command == 'Mute':
                xbmc.executebuiltin('Mute')
            elif command == 'Unmute':
                xbmc.executebuiltin('Mute')
            elif command == 'SetVolume':
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % args['Volume'])
            elif command == 'SetRepeatMode':
                xbmc.executebuiltin('xbmc.PlayerControl(%s)' % args['RepeatMode'])
            elif command == 'SetAudioStreamIndex':
                self.player.set_audio_subs(args['Index'])
            elif command == 'SetSubtitleStreamIndex':
                self.player.set_audio_subs(None, args['Index'])

            # Kodi needs a bit of time to update it's current status
            xbmc.sleep(500)
            self.player.report_playback()

        elif command == 'DisplayMessage':
            dialog("notification", heading=args['Header'], message=args['Text'],
                   icon="{jellyfin}", time=int(settings('displayMessage')) * 1000)

        elif command == 'SendString':
            JSONRPC('Input.SendText').execute({'text': args['String'], 'done': False})

        elif command == 'GoHome':
            JSONRPC('GUI.ActivateWindow').execute({'window': "home"})

        elif command == 'Guide':
            JSONRPC('GUI.ActivateWindow').execute({'window': "tvguide"})

        elif command in ('MoveUp', 'MoveDown', 'MoveRight', 'MoveLeft'):
            actions = {
                'MoveUp': "Input.Up",
                'MoveDown': "Input.Down",
                'MoveRight': "Input.Right",
                'MoveLeft': "Input.Left"
            }
            JSONRPC(actions[command]).execute()

        else:
            builtin = {
                'ToggleFullscreen': 'Action(FullScreen)',
                'ToggleOsdMenu': 'Action(OSD)',
                'ToggleContextMenu': 'Action(ContextMenu)',
                'Select': 'Action(Select)',
                'Back': 'Action(back)',
                'PageUp': 'Action(PageUp)',
                'NextLetter': 'Action(NextLetter)',
                'GoToSearch': 'VideoLibrary.Search',
                'GoToSettings': 'ActivateWindow(Settings)',
                'PageDown': 'Action(PageDown)',
                'PreviousLetter': 'Action(PrevLetter)',
                'TakeScreenshot': 'TakeScreenshot',
                'ToggleMute': 'Mute',
                'VolumeUp': 'Action(VolumeUp)',
                'VolumeDown': 'Action(VolumeDown)',
            }
            if command in builtin:
                xbmc.executebuiltin(builtin[command])


class Listener(threading.Thread):

    stop_thread = False

    def __init__(self, monitor):
        self.monitor = monitor

        threading.Thread.__init__(self)

    def run(self):

        ''' Detect the resume dialog for widgets.
            Detect external players.
        '''
        LOG.info("--->[ listener ]")

        while not self.stop_thread:
            special_listener()

            if self.monitor.waitForAbort(0.5):
                # Abort was requested while waiting. We should exit
                break

        LOG.info("---<[ listener ]")

    def stop(self):
        self.stop_thread = True
