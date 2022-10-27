# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import json
import sys
from datetime import datetime

# Workaround for threads using datetime: _striptime is locked
import _strptime  # noqa:F401
from kodi_six import xbmc, xbmcgui
from six.moves import reload_module as reload

from .. import objects
from .. import connect
from .. import client
from .. import library
from .. import monitor
from ..views import Views
from ..helper import translate, window, settings, event, dialog, set_addon_mode, LazyLogger
from ..helper.utils import JsonDebugPrinter, translate_path
from ..helper.xmls import verify_kodi_defaults
from ..jellyfin import Jellyfin

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


class Service(xbmc.Monitor):

    running = True
    library_thread = None
    monitor = None
    play_event = None
    warn = True
    settings = {'last_progress': datetime.today(), 'last_progress_report': datetime.today()}

    def __init__(self):

        window('jellyfin_should_stop', clear=True)

        self.settings['addon_version'] = client.get_version()
        self.settings['profile'] = translate_path('special://profile')
        self.settings['mode'] = settings('useDirectPaths')
        self.settings['log_level'] = settings('logLevel') or "1"
        self.settings['auth_check'] = True
        self.settings['enable_context'] = settings('enableContext.bool')
        self.settings['enable_context_transcode'] = settings('enableContextTranscode.bool')
        self.settings['kodi_companion'] = settings('kodiCompanion.bool')
        window('jellyfin_kodiProfile', value=self.settings['profile'])
        settings('platformDetected', client.get_platform())

        if self.settings['enable_context']:
            window('jellyfin_context.bool', True)
        if self.settings['enable_context_transcode']:
            window('jellyfin_context_transcode.bool', True)

        LOG.info("--->>>[ %s ]", client.get_addon_name())
        LOG.info("Version: %s", client.get_version())
        LOG.info("KODI Version: %s", xbmc.getInfoLabel('System.BuildVersion'))
        LOG.info("Platform: %s", settings('platformDetected'))
        LOG.info("Python Version: %s", sys.version)
        LOG.info("Using dynamic paths: %s", settings('useDirectPaths') == "0")
        LOG.info("Log Level: %s", self.settings['log_level'])

        verify_kodi_defaults()

        window('jellyfin.connected.bool', True)
        settings('groupedSets.bool', objects.utils.get_grouped_set())
        xbmc.Monitor.__init__(self)

    def service(self):

        ''' Keeps the service monitor going.
            Exit on Kodi shutdown or profile switch.

            if profile switch happens more than once,
            Threads depending on abortRequest will not trigger.
        '''
        self.monitor = monitor.Monitor()
        player = self.monitor.player
        self.connect = connect.Connect()
        self.start_default()

        self.settings['mode'] = settings('useDirectPaths')

        while self.running:
            if window('jellyfin_online.bool'):

                if self.settings['profile'] != window('jellyfin_kodiProfile'):
                    LOG.info("[ profile switch ] %s", self.settings['profile'])

                    break

                if player.isPlaying() and player.is_playing_file(player.get_playing_file()):
                    difference = datetime.today() - self.settings['last_progress']

                    if difference.seconds > 10:
                        self.settings['last_progress'] = datetime.today()

                        update = (datetime.today() - self.settings['last_progress_report']).seconds > 250
                        event('ReportProgressRequested', {'Report': update})

                        if update:
                            self.settings['last_progress_report'] = datetime.today()

            if window('jellyfin.restart.bool'):

                window('jellyfin.restart', clear=True)
                dialog("notification", heading="{jellyfin}", message=translate(33193), icon="{jellyfin}", time=1000, sound=False)

                raise Exception('RestartService')

            if self.waitForAbort(1):
                break

        self.shutdown()

        raise Exception("ExitService")

    def start_default(self):

        try:
            self.connect.register()
            if not settings('SyncInstallRunDone.bool'):
                set_addon_mode()
        except Exception as error:
            LOG.exception(error)

    def stop_default(self):

        window('jellyfin_online', clear=True)
        Jellyfin().close()

        if self.library_thread is not None:

            self.library_thread.stop_client()
            self.library_thread = None

    def onNotification(self, sender, method, data):

        ''' All notifications are sent via NotifyAll built-in or Kodi.
            Central hub.
        '''
        if sender.lower() not in ('plugin.video.jellyfin', 'xbmc'):
            return

        if sender == 'plugin.video.jellyfin':
            method = method.split('.')[1]

            if method not in ('ServerUnreachable', 'ServerShuttingDown', 'UserDataChanged', 'ServerConnect',
                              'LibraryChanged', 'ServerOnline', 'SyncLibrary', 'RepairLibrary', 'RemoveLibrary',
                              'SyncLibrarySelection', 'RepairLibrarySelection', 'AddServer',
                              'Unauthorized', 'UserConfigurationUpdated', 'ServerRestarting',
                              'RemoveServer', 'UpdatePassword', 'AddLibrarySelection', 'RemoveLibrarySelection'):
                return

            data = json.loads(data)[0]
        else:
            if method not in ('System.OnQuit', 'System.OnSleep', 'System.OnWake'):
                return

            data = json.loads(data)

        LOG.debug("[ %s: %s ] %s", sender, method, JsonDebugPrinter(data))

        if method == 'ServerOnline':
            if data.get('ServerId') is None:

                window('jellyfin_online.bool', True)
                self.settings['auth_check'] = True
                self.warn = True

                if settings('connectMsg.bool'):

                    users = [user for user in (settings('additionalUsers') or "").split(',') if user]
                    users.insert(0, settings('username'))
                    dialog("notification", heading="{jellyfin}", message="%s %s" % (translate(33000), ", ".join(users)),
                           icon="{jellyfin}", time=1500, sound=False)

                if self.library_thread is None:

                    self.library_thread = library.Library(self)
                    self.library_thread.start()

        elif method in ('ServerUnreachable', 'ServerShuttingDown'):

            if self.warn or data.get('ServerId'):

                self.warn = data.get('ServerId') is not None
                dialog("notification", heading="{jellyfin}", message=translate(33146) if data.get('ServerId') is None else translate(33149), icon=xbmcgui.NOTIFICATION_ERROR)

            if data.get('ServerId') is None:
                self.stop_default()

                if self.waitForAbort(120):
                    return

                self.start_default()

        elif method == 'Unauthorized':
            dialog("notification", heading="{jellyfin}", message=translate(33147) if data['ServerId'] is None else translate(33148), icon=xbmcgui.NOTIFICATION_ERROR)

            if data.get('ServerId') is None and self.settings['auth_check']:

                self.settings['auth_check'] = False
                self.stop_default()

                if self.waitForAbort(5):
                    return

                self.start_default()

        elif method == 'ServerRestarting':
            if data.get('ServerId'):
                return

            if settings('restartMsg.bool'):
                dialog("notification", heading="{jellyfin}", message=translate(33006), icon="{jellyfin}")

            self.stop_default()

            if self.waitForAbort(15):
                return

            self.start_default()

        elif method == 'ServerConnect':
            self.connect.register(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'AddServer':

            self.connect.setup_manual_server()
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'RemoveServer':

            self.connect.remove_server(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'UpdatePassword':
            self.connect.setup_login_manual()
        elif method == 'UserDataChanged' and self.library_thread:
            if data.get('ServerId') or not window('jellyfin_startup.bool'):
                return

            LOG.info("[ UserDataChanged ] %s", data)
            self.library_thread.userdata(data['UserDataList'])

        elif method == 'LibraryChanged' and self.library_thread:
            if data.get('ServerId') or not window('jellyfin_startup.bool'):
                return

            LOG.info("[ LibraryChanged ] %s", data)
            self.library_thread.updated(data['ItemsUpdated'] + data['ItemsAdded'])
            self.library_thread.removed(data['ItemsRemoved'])

        elif method == 'System.OnQuit':
            window('jellyfin_should_stop.bool', True)
            self.running = False

        elif method in ('SyncLibrarySelection', 'RepairLibrarySelection', 'AddLibrarySelection', 'RemoveLibrarySelection'):
            self.library_thread.select_libraries(method)

        elif method == 'SyncLibrary':
            if not data.get('Id'):
                return

            self.library_thread.add_library(data['Id'], data.get('Update', False))
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'RepairLibrary':
            if not data.get('Id'):
                return

            libraries = data['Id'].split(',')

            for lib in libraries:

                if not self.library_thread.remove_library(lib):
                    return

            self.library_thread.add_library(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'RemoveLibrary':
            libraries = data['Id'].split(',')

            for lib in libraries:

                if not self.library_thread.remove_library(lib):
                    return

            xbmc.executebuiltin("Container.Refresh")

        elif method == 'System.OnSleep':

            LOG.info("-->[ sleep ]")
            window('jellyfin_should_stop.bool', True)

            if self.library_thread is not None:

                self.library_thread.stop_client()
                self.library_thread = None

            Jellyfin.close_all()
            self.monitor.server = []
            self.monitor.sleep = True

        elif method == 'System.OnWake':

            if not self.monitor.sleep:
                LOG.warning("System.OnSleep was never called, skip System.OnWake")

                return

            LOG.info("--<[ sleep ]")
            xbmc.sleep(10000)  # Allow network to wake up
            self.monitor.sleep = False
            window('jellyfin_should_stop', clear=True)

            try:
                self.connect.register()
            except Exception as error:
                LOG.exception(error)

        elif method == 'GUI.OnScreensaverDeactivated':

            LOG.info("--<[ screensaver ]")
            xbmc.sleep(5000)

            if self.library_thread is not None:
                self.library_thread.fast_sync()

        elif method == 'UserConfigurationUpdated' and data.get('ServerId') is None:
            Views().get_views()

    def onSettingsChanged(self):

        ''' React to setting changes that impact window values.
        '''
        if window('jellyfin_should_stop.bool'):
            return

        if settings('logLevel') != self.settings['log_level']:

            log_level = settings('logLevel')
            self.settings['logLevel'] = log_level
            LOG.info("New log level: %s", log_level)

        if settings('enableContext.bool') != self.settings['enable_context']:

            window('jellyfin_context', settings('enableContext'))
            self.settings['enable_context'] = settings('enableContext.bool')
            LOG.info("New context setting: %s", self.settings['enable_context'])

        if settings('enableContextTranscode.bool') != self.settings['enable_context_transcode']:

            window('jellyfin_context_transcode', settings('enableContextTranscode'))
            self.settings['enable_context_transcode'] = settings('enableContextTranscode.bool')
            LOG.info("New context transcode setting: %s", self.settings['enable_context_transcode'])

        if settings('useDirectPaths') != self.settings['mode'] and self.library_thread.started:

            self.settings['mode'] = settings('useDirectPaths')
            LOG.info("New playback mode setting: %s", self.settings['mode'])

            if not self.settings.get('mode_warn'):

                self.settings['mode_warn'] = True
                dialog("yesno", "{jellyfin}", translate(33118))

        if settings('kodiCompanion.bool') != self.settings['kodi_companion']:
            self.settings['kodi_companion'] = settings('kodiCompanion.bool')

            if not self.settings['kodi_companion']:
                dialog("ok", "{jellyfin}", translate(33138))

    def reload_objects(self):

        ''' Reload objects which depends on the patch module.
            This allows to see the changes in code without restarting the python interpreter.
        '''
        reload_modules = ['objects.movies', 'objects.musicvideos', 'objects.tvshows',
                          'objects.music', 'objects.obj', 'objects.actions', 'objects.kodi.kodi',
                          'objects.kodi.movies', 'objects.kodi.musicvideos', 'objects.kodi.tvshows',
                          'objects.kodi.music', 'objects.kodi.artwork', 'objects.kodi.queries',
                          'objects.kodi.queries_music', 'objects.kodi.queries_texture']

        for mod in reload_modules:
            del sys.modules[mod]

        reload(objects.kodi)
        reload(objects)
        reload(library)
        reload(monitor)

        objects.obj.Objects().mapping()

        LOG.info("---[ objects reloaded ]")

    def shutdown(self):

        LOG.info("---<[ EXITING ]")
        window('jellyfin_should_stop.bool', True)

        properties = [  # TODO: review
            "jellyfin_state", "jellyfin_serverStatus", "jellyfin_currUser",

            "jellyfin_play", "jellyfin_online", "jellyfin.connected", "jellyfin_startup",
            "jellyfin.external", "jellyfin.external_check", "jellyfin_deviceId", "jellyfin_db_check", "jellyfin_pathverified",
            "jellyfin_sync"
        ]
        for prop in properties:
            window(prop, clear=True)

        Jellyfin.close_all()

        if self.library_thread is not None:
            self.library_thread.stop_client()

        if self.monitor is not None:

            self.monitor.listener.stop()

        LOG.info("---<<<[ %s ]", client.get_addon_name())
