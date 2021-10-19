# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals


def test_import_main_module():
    import jellyfin_kodi  # noqa: F401


def test_import_client():
    import jellyfin_kodi.client  # noqa: F401


def test_import_connect():
    import jellyfin_kodi.connect  # noqa: F401


def test_import_database():
    import jellyfin_kodi.database
    import jellyfin_kodi.database.jellyfin_db
    import jellyfin_kodi.database.queries  # noqa: F401


def test_import_dialogs():
    import jellyfin_kodi.dialogs
    import jellyfin_kodi.dialogs.context
    import jellyfin_kodi.dialogs.loginmanual
    import jellyfin_kodi.dialogs.resume
    import jellyfin_kodi.dialogs.serverconnect
    import jellyfin_kodi.dialogs.servermanual
    import jellyfin_kodi.dialogs.usersconnect  # noqa: F401


def test_import_downloader():
    import jellyfin_kodi.downloader  # noqa: F401


def test_import_entrypoint():
    import jellyfin_kodi.entrypoint
    import jellyfin_kodi.entrypoint.context
    # import jellyfin_kodi.entrypoint.default  # FIXME: Messes with sys.argv
    import jellyfin_kodi.entrypoint.service  # noqa: F401


def test_import_full_sync():
    import jellyfin_kodi.full_sync  # noqa: F401


def test_import_helper():
    import jellyfin_kodi.helper
    import jellyfin_kodi.helper.api
    import jellyfin_kodi.helper.exceptions
    import jellyfin_kodi.helper.lazylogger
    import jellyfin_kodi.helper.loghandler
    import jellyfin_kodi.helper.playutils
    import jellyfin_kodi.helper.translate
    import jellyfin_kodi.helper.utils
    import jellyfin_kodi.helper.wrapper
    import jellyfin_kodi.helper.xmls  # noqa: F401


def test_import_jellyfin():
    import jellyfin_kodi.jellyfin
    import jellyfin_kodi.jellyfin.api
    import jellyfin_kodi.jellyfin.client
    import jellyfin_kodi.jellyfin.configuration
    import jellyfin_kodi.jellyfin.connection_manager
    import jellyfin_kodi.jellyfin.credentials
    import jellyfin_kodi.jellyfin.http
    import jellyfin_kodi.jellyfin.utils
    import jellyfin_kodi.jellyfin.ws_client  # noqa: F401


def test_import_library():
    import jellyfin_kodi.library  # noqa: F401


def test_import_monitor():
    import jellyfin_kodi.monitor  # noqa: F401


def test_import_objects():
    import jellyfin_kodi.objects
    import jellyfin_kodi.objects.actions
    import jellyfin_kodi.objects.kodi
    import jellyfin_kodi.objects.kodi.artwork
    import jellyfin_kodi.objects.kodi.kodi
    import jellyfin_kodi.objects.kodi.movies
    import jellyfin_kodi.objects.kodi.music
    import jellyfin_kodi.objects.kodi.musicvideos
    import jellyfin_kodi.objects.kodi.queries
    import jellyfin_kodi.objects.kodi.queries_music
    import jellyfin_kodi.objects.kodi.queries_texture
    import jellyfin_kodi.objects.kodi.tvshows
    import jellyfin_kodi.objects.movies
    import jellyfin_kodi.objects.music
    import jellyfin_kodi.objects.musicvideos
    import jellyfin_kodi.objects.obj
    import jellyfin_kodi.objects.tvshows
    import jellyfin_kodi.objects.utils  # noqa: F401


def test_import_player():
    import jellyfin_kodi.player  # noqa: F401


def test_import_views():
    import jellyfin_kodi.views  # noqa: F401
