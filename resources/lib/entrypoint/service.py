# -*- coding: utf-8 -*-

#################################################################################################

import _strptime # Workaround for threads using datetime: _striptime is locked
import json
import logging
import sys
from datetime import datetime

import xbmc
import xbmcgui

import objects
import connect
import client
import library
import setup
import monitor
import requests
from views import Views, verify_kodi_defaults
from helper import _, window, settings, event, dialog, find, compare_version
from downloader import get_objects
from emby import Emby
from database import Database, emby_db, reset

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################


class Service(xbmc.Monitor):

    running = True
    library_thread = None
    monitor = None
    play_event = None
    warn = True
    settings = {'last_progress': datetime.today(), 'last_progress_report': datetime.today()}


    def __init__(self):

        window('emby_should_stop', clear=True)

        self.settings['addon_version'] = client.get_version()
        self.settings['profile'] = xbmc.translatePath('special://profile')
        self.settings['mode'] = settings('useDirectPaths')
        self.settings['log_level'] = settings('logLevel') or "1"
        self.settings['auth_check'] = True
        self.settings['enable_context'] = settings('enableContext.bool')
        self.settings['enable_context_transcode'] = settings('enableContextTranscode.bool')
        self.settings['kodi_companion'] = settings('kodiCompanion.bool')
        window('emby_logLevel', value=str(self.settings['log_level']))
        window('emby_kodiProfile', value=self.settings['profile'])
        settings('platformDetected', client.get_platform())

        if self.settings['enable_context']:
            window('emby_context.bool', True)
        if self.settings['enable_context_transcode']:
            window('emby_context_transcode.bool', True)

        LOG.warn("--->>>[ %s ]", client.get_addon_name())
        LOG.warn("Version: %s", client.get_version())
        LOG.warn("KODI Version: %s", xbmc.getInfoLabel('System.BuildVersion'))
        LOG.warn("Platform: %s", settings('platformDetected'))
        LOG.warn("Python Version: %s", sys.version)
        LOG.warn("Using dynamic paths: %s", settings('useDirectPaths') == "0")
        LOG.warn("Log Level: %s", self.settings['log_level'])

        self.check_version()
        verify_kodi_defaults()

        try:
            Views().get_nodes()
        except Exception as error:
            LOG.error(error)

        window('emby.connected.bool', True)
        self.check_update()
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
            if window('emby_online.bool'):

                if self.settings['profile'] != window('emby_kodiProfile'):
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

            if window('emby.restart.bool'):

                window('emby.restart', clear=True)
                dialog("notification", heading="{emby}", message=_(33193), icon="{emby}", time=1000, sound=False)

                raise Exception('RestartService')

            if self.waitForAbort(1):
                break

        self.shutdown()

        raise Exception("ExitService")

    def start_default(self):

        try:
            self.connect.register()
            setup.Setup()
        except Exception as error:
            LOG.error(error)

    def stop_default(self):

        window('emby_online', clear=True)
        Emby().close()

        if self.library_thread is not None:

            self.library_thread.stop_client()
            self.library_thread = None

    def check_version(self):

        ''' Check the database version to ensure we do not need to do a reset.
        '''
        with Database('emby') as embydb:

            version = emby_db.EmbyDatabase(embydb.cursor).get_version()
            LOG.info("---[ db/%s ]", version)

        if version and compare_version(version, "3.1.0") < 0:
            resp = dialog("yesno", heading=_('addon_name'), line1=_(33022))

            if not resp:

                LOG.warn("Database version is out of date! USER IGNORED!")
                dialog("ok", heading=_('addon_name'), line1=_(33023))

                raise Exception("User backed out of a required database reset")
            else:
                reset()

                raise Exception("Completed database reset")

    def check_update(self, forced=False):

        ''' Check for objects build version and compare.
            This pulls a dict that contains all the information for the build needed.
        '''
        LOG.info("--[ check updates/%s ]", objects.version)
        kodi = "DEV" if settings('devMode.bool') else xbmc.getInfoLabel('System.BuildVersion')

        try:
            versions = requests.get('http://kodi.emby.media/Public%20testing/Dependencies/databases.json').json()
            build = find(versions, kodi)

            if not build:
                raise Exception("build %s incompatible?!" % kodi)

            label, zipfile = build.split('-', 1)

            if label == 'DEV' and forced:
                LOG.info("--[ force/objects/%s ]", label)

            elif label == objects.version:
                LOG.info("--[ objects/%s ]", objects.version)

                return False

            get_objects(zipfile, label + '.zip')
            self.reload_objects()

            dialog("notification", heading="{emby}", message=_(33156), icon="{emby}")
            LOG.info("--[ new objects/%s ]", objects.version)

            try:
                if compare_version(self.settings['addon_version'], objects.embyversion) < 0:
                    dialog("ok", heading="{emby}", line1="%s %s" % (_(33160), objects.embyversion))
            except Exception:
                pass

        except Exception as error:
            LOG.exception(error)

        return True
    
    def onNotification(self, sender, method, data):

        ''' All notifications are sent via NotifyAll built-in or Kodi.
            Central hub.
        '''
        if sender.lower() not in ('plugin.video.emby', 'xbmc'):
            return

        if sender == 'plugin.video.emby':
            method = method.split('.')[1]

            if method not in ('ServerUnreachable', 'ServerShuttingDown', 'UserDataChanged', 'ServerConnect',
                              'LibraryChanged', 'ServerOnline', 'SyncLibrary', 'RepairLibrary', 'RemoveLibrary',
                              'EmbyConnect', 'SyncLibrarySelection', 'RepairLibrarySelection', 'AddServer',
                              'Unauthorized', 'UpdateServer', 'UserConfigurationUpdated', 'ServerRestarting',
                              'RemoveServer', 'AddLibrarySelection', 'CheckUpdate', 'RemoveLibrarySelection'):
                return

            data = json.loads(data)[0]
        else:
            if method not in ('System.OnQuit', 'System.OnSleep', 'System.OnWake'):
                return

            data = json.loads(data)

        LOG.debug("[ %s: %s ] %s", sender, method, json.dumps(data, indent=4))

        if method == 'ServerOnline':
            if data.get('ServerId') is None:

                window('emby_online.bool', True)
                self.settings['auth_check'] = True
                self.warn = True

                if settings('connectMsg.bool'):

                    users = [user for user in (settings('additionalUsers') or "").decode('utf-8').split(',') if user]
                    users.insert(0, settings('username').decode('utf-8'))
                    dialog("notification", heading="{emby}", message="%s %s" % (_(33000), ", ".join(users)),
                            icon="{emby}", time=1500, sound=False)

                if self.library_thread is None:

                    self.library_thread = library.Library(self)
                    self.library_thread.start()

        elif method in ('ServerUnreachable', 'ServerShuttingDown'):

            if self.warn or data.get('ServerId'):

                self.warn = data.get('ServerId') is not None
                dialog("notification", heading="{emby}", message=_(33146) if data.get('ServerId') is None else _(33149), icon=xbmcgui.NOTIFICATION_ERROR)

            if data.get('ServerId') is None:
                self.stop_default()

                if self.waitForAbort(120):
                    return
                
                self.start_default()

        elif method == 'Unauthorized':
            dialog("notification", heading="{emby}", message=_(33147) if data['ServerId'] is None else _(33148), icon=xbmcgui.NOTIFICATION_ERROR)

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
                dialog("notification", heading="{emby}", message=_(33006), icon="{emby}")

            self.stop_default()

            if self.waitForAbort(15):
                return
                
            self.start_default()

        elif method == 'ServerConnect':
            self.connect.register(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'EmbyConnect':
            self.connect.setup_login_connect()

        elif method == 'AddServer':

            self.connect.setup_manual_server()
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'RemoveServer':

            self.connect.remove_server(data['Id'])
            xbmc.executebuiltin("Container.Refresh")

        elif method == 'UpdateServer':

            dialog("ok", heading="{emby}", line1=_(33151))
            self.connect.setup_manual_server()

        elif method == 'UserDataChanged' and self.library_thread:
            if data.get('ServerId') or not window('emby_startup.bool'):
                return

            LOG.info("[ UserDataChanged ] %s", data)
            self.library_thread.userdata(data['UserDataList'])

        elif method == 'LibraryChanged' and self.library_thread:
            if data.get('ServerId') or not window('emby_startup.bool'):
                return

            LOG.info("[ LibraryChanged ] %s", data)
            self.library_thread.updated(data['ItemsUpdated'] + data['ItemsAdded'])
            self.library_thread.removed(data['ItemsRemoved'])

        elif method == 'System.OnQuit':
            window('emby_should_stop.bool', True)
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
            window('emby_should_stop.bool', True)

            if self.library_thread is not None:

                self.library_thread.stop_client()
                self.library_thread = None

            Emby.close_all()
            self.monitor.server = []
            self.monitor.sleep = True

        elif method == 'System.OnWake':

            if not self.monitor.sleep:
                LOG.warn("System.OnSleep was never called, skip System.OnWake")

                return

            LOG.info("--<[ sleep ]")
            xbmc.sleep(10000)# Allow network to wake up
            self.monitor.sleep = False
            window('emby_should_stop', clear=True)

            try:
                self.connect.register()
            except Exception as error:
                LOG.error(error)

        elif method == 'GUI.OnScreensaverDeactivated':

            LOG.info("--<[ screensaver ]")
            xbmc.sleep(5000)

            if self.library_thread is not None:
                self.library_thread.fast_sync()

        elif method == 'UserConfigurationUpdated':

            if data.get('ServerId') is None:
                Views().get_views()

        elif method == 'CheckUpdate':

            if not self.check_update(True):
                dialog("notification", heading="{emby}", message=_(21341), icon="{emby}", sound=False)
            else:
                dialog("notification", heading="{emby}", message=_(33181), icon="{emby}", sound=False)
                window('emby.restart.bool', True)

    def onSettingsChanged(self):

        ''' React to setting changes that impact window values.
        '''
        if window('emby_should_stop.bool'):
            return

        if settings('logLevel') != self.settings['log_level']:

            log_level = settings('logLevel')
            window('emby_logLevel', str(log_level))
            self.settings['logLevel'] = log_level
            LOG.warn("New log level: %s", log_level)

        if settings('enableContext.bool') != self.settings['enable_context']:

            window('emby_context', settings('enableContext'))
            self.settings['enable_context'] = settings('enableContext.bool')
            LOG.warn("New context setting: %s", self.settings['enable_context'])

        if settings('enableContextTranscode.bool') != self.settings['enable_context_transcode']:

            window('emby_context_transcode', settings('enableContextTranscode'))
            self.settings['enable_context_transcode'] = settings('enableContextTranscode.bool')
            LOG.warn("New context transcode setting: %s", self.settings['enable_context_transcode'])

        if settings('useDirectPaths') != self.settings['mode'] and self.library_thread.started:

            self.settings['mode'] = settings('useDirectPaths')
            LOG.warn("New playback mode setting: %s", self.settings['mode'])

            if not self.settings.get('mode_warn'):

                self.settings['mode_warn'] = True
                dialog("yesno", heading="{emby}", line1=_(33118))

        if settings('kodiCompanion.bool') != self.settings['kodi_companion']:
            self.settings['kodi_companion'] = settings('kodiCompanion.bool')

            if not self.settings['kodi_companion']:
                dialog("ok", heading="{emby}", line1=_(33138))

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

        LOG.warn("---[ objects reloaded ]")

    def shutdown(self):

        LOG.warn("---<[ EXITING ]")
        window('emby_should_stop.bool', True)

        properties = [ # TODO: review
            "emby_state", "emby_serverStatus", "emby_currUser",

            "emby_play", "emby_online", "emby.connected", "emby.resume", "emby_startup",
            "emby.external", "emby.external_check", "emby_deviceId", "emby_db_check", "emby_pathverified",
            "emby_sync"
        ]
        for prop in properties:
            window(prop, clear=True)

        Emby.close_all()

        if self.library_thread is not None:
            self.library_thread.stop_client()

        if self.monitor is not None:

            self.monitor.listener.stop()
            self.monitor.webservice.stop()

        LOG.warn("---<<<[ %s ]", client.get_addon_name())
