# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import binascii
import json
import threading

from kodi_six import xbmc

import connect
import downloader
import player
from client import get_device_id
from objects import PlaylistWorker, on_play, on_update, special_listener
from helper import translate, settings, window, dialog, api, JSONRPC
from helper.utils import JsonDebugPrinter
from jellyfin import Jellyfin
from webservice import WebService
from helper import LazyLogger

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


class Monitor(xbmc.Monitor):

    servers = []
    sleep = False

    def __init__(self):

        self.player = player.Player()
        self.device_id = get_device_id()
        self.listener = Listener(self)
        self.listener.start()
        self.webservice = WebService()
        self.webservice.start()
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

            if method not in ('GetItem', 'ReportProgressRequested', 'LoadServer', 'RandomItems', 'Recommended',
                              'GetServerAddress', 'GetPlaybackInfo', 'Browse', 'GetImages', 'GetToken',
                              'PlayPlaylist', 'Play', 'GetIntros', 'GetAdditionalParts', 'RefreshItem', 'Genres',
                              'FavoriteItem', 'DeleteItem', 'AddUser', 'GetSession', 'GetUsers', 'GetThemes',
                              'GetTheme', 'Playstate', 'GeneralCommand', 'GetTranscodeOptions', 'RecentlyAdded',
                              'BrowseSeason', 'LiveTV', 'GetLiveStream'):
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

        try:
            if not data.get('ServerId'):
                server = Jellyfin()
            else:
                if method != 'LoadServer' and data['ServerId'] not in self.servers:

                    try:
                        connect.Connect().register(data['ServerId'])
                        self.server_instance(data['ServerId'])
                    except Exception as error:

                        LOG.exception(error)
                        dialog("ok", "{jellyfin}", translate(33142))

                        return

                server = Jellyfin(data['ServerId'])
        except Exception as error:
            LOG.exception(error)
            server = Jellyfin()

        if method == 'GetItem':

            item = server.jellyfin.get_item(data['Id'])
            self.void_responder(data, item)

        elif method == 'GetAdditionalParts':

            item = server.jellyfin.get_additional_parts(data['Id'])
            self.void_responder(data, item)

        elif method == 'GetIntros':

            item = server.jellyfin.get_intros(data['Id'])
            self.void_responder(data, item)

        elif method == 'GetImages':

            item = server.jellyfin.get_images(data['Id'])
            self.void_responder(data, item)

        elif method == 'GetServerAddress':

            server_address = server.auth.get_server_info(server.auth.server_id)['address']
            self.void_responder(data, server_address)

        elif method == 'GetPlaybackInfo':

            sources = server.jellyfin.get_play_info(data['Id'], data['Profile'])
            self.void_responder(data, sources)

        elif method == 'GetLiveStream':

            sources = server.jellyfin.get_live_stream(data['Id'], data['PlaySessionId'], data['Token'], data['Profile'])
            self.void_responder(data, sources)

        elif method == 'GetToken':

            token = server.auth.jellyfin_token()
            self.void_responder(data, token)

        elif method == 'GetSession':

            session = server.jellyfin.get_device(self.device_id)
            self.void_responder(data, session)

        elif method == 'GetUsers':

            users = server.jellyfin.get_users()
            self.void_responder(data, users)

        elif method == 'GetTranscodeOptions':

            result = server.jellyfin.get_transcode_settings()
            self.void_responder(data, result)

        elif method == 'GetThemes':

            if data['Type'] == 'Video':
                theme = server.jellyfin.get_items_theme_video(data['Id'])
            else:
                theme = server.jellyfin.get_items_theme_song(data['Id'])

            self.void_responder(data, theme)

        elif method == 'GetTheme':

            theme = server.jellyfin.get_themes(data['Id'])
            self.void_responder(data, theme)

        elif method == 'Browse':

            result = downloader.get_filtered_section(data.get('Id'), data.get('Media'), data.get('Limit'),
                                                     data.get('Recursive'), data.get('Sort'), data.get('SortOrder'),
                                                     data.get('Filters'), data.get('Params'), data.get('ServerId'))
            self.void_responder(data, result)

        elif method == 'BrowseSeason':

            result = server.jellyfin.get_seasons(data['Id'])
            self.void_responder(data, result)

        elif method == 'LiveTV':

            result = server.jellyfin.get_channels()
            self.void_responder(data, result)

        elif method == 'RecentlyAdded':

            result = server.jellyfin.get_recently_added(data.get('Media'), data.get('Id'), data.get('Limit'))
            self.void_responder(data, result)

        elif method == 'Genres':

            result = server.jellyfin.get_genres(data.get('Id'))
            self.void_responder(data, result)

        elif method == 'Recommended':

            result = server.jellyfin.get_recommendation(data.get('Id'), data.get('Limit'))
            self.void_responder(data, result)

        elif method == 'RefreshItem':
            server.jellyfin.refresh_item(data['Id'])

        elif method == 'FavoriteItem':
            server.jellyfin.favorite(data['Id'], data['Favorite'])

        elif method == 'DeleteItem':
            server.jellyfin.delete_item(data['Id'])

        elif method == 'PlayPlaylist':

            server.jellyfin.post_session(server.config.data['app.session'], "Playing", {
                'PlayCommand': "PlayNow",
                'ItemIds': data['Id'],
                'StartPositionTicks': 0
            })

        elif method == 'Play':

            items = server.jellyfin.get_items(data['ItemIds'])

            PlaylistWorker(data.get('ServerId'), items, data['PlayCommand'] == 'PlayNow',
                           data.get('StartPositionTicks', 0), data.get('AudioStreamIndex'),
                           data.get('SubtitleStreamIndex')).start()

        elif method in ('ReportProgressRequested', 'Player.OnAVChange'):
            self.player.report_playback(data.get('Report', True))

        elif method == 'Playstate':
            self.playstate(data)

        elif method == 'GeneralCommand':
            self.general_commands(data)

        elif method == 'LoadServer':
            self.server_instance(data['ServerId'])

        elif method == 'AddUser':
            server.jellyfin.session_add_user(server.config.data['app.session'], data['Id'], data['Add'])
            self.additional_users(server)

        elif method == 'Player.OnPlay':
            on_play(data, server)

        elif method == 'VideoLibrary.OnUpdate':
            on_update(data, server)

    def void_responder(self, data, result):

        window('jellyfin_%s.json' % data['VoidName'], result)
        LOG.debug("--->[ nostromo/jellyfin_%s.json ] sent", data['VoidName'])

    def server_instance(self, server_id=None):

        server = Jellyfin(server_id)
        self.post_capabilities(server)

        if server_id is not None:
            self.servers.append(server_id)
        elif settings('additionalUsers'):

            users = settings('additionalUsers').split(',')
            all_users = server.jellyfin.get_users()

            for additional in users:
                for user in all_users:

                    if user['Name'].lower() in additional.lower():
                        server.jellyfin.session_add_user(server.config.data['app.session'], user['Id'], True)

            self.additional_users(server)

    def post_capabilities(self, server):
        LOG.info("--[ post capabilities/%s ]", server.auth.server_id)

        server.jellyfin.post_capabilities({
            'PlayableMediaTypes': "Audio,Video",
            'SupportsMediaControl': True,
            'SupportedCommands': (
                "MoveUp,MoveDown,MoveLeft,MoveRight,Select,"
                "Back,ToggleContextMenu,ToggleFullscreen,ToggleOsdMenu,"
                "GoHome,PageUp,NextLetter,GoToSearch,"
                "GoToSettings,PageDown,PreviousLetter,TakeScreenshot,"
                "VolumeUp,VolumeDown,ToggleMute,SendString,DisplayMessage,"
                "SetAudioStreamIndex,SetSubtitleStreamIndex,"
                "SetRepeatMode,"
                "Mute,Unmute,SetVolume,"
                "Play,Playstate,PlayNext,PlayMediaSource"
            ),
        })
        session = server.jellyfin.get_device(self.device_id)
        server.config.data['app.session'] = session[0]['Id']

    def additional_users(self, server):

        ''' Setup additional users images.
        '''
        for i in range(10):
            window('JellyfinAdditionalUserImage.%s' % i, clear=True)

        try:
            session = server.jellyfin.get_device(self.device_id)
        except Exception as error:
            LOG.exception(error)

            return

        for index, user in enumerate(session[0]['AdditionalUsers']):

            info = server.jellyfin.get_user(user['UserId'])
            image = api.API(info, server.config.data['auth.server']).get_user_artwork(user['UserId'])
            window('JellyfinAdditionalUserImage.%s' % index, image)
            window('JellyfinAdditionalUserPosition.%s' % user['UserId'], str(index))

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
