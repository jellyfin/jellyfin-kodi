# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import binascii
import json
import os
import sys
import re
import unicodedata
from uuid import uuid4
from distutils.version import LooseVersion

from dateutil import tz, parser
from six import text_type, string_types, iteritems, ensure_text, ensure_binary
from six.moves.urllib.parse import quote_plus

from kodi_six import xbmc, xbmcaddon, xbmcgui, xbmcvfs

from . import LazyLogger
from .translate import translate


#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


def addon_id():
    return "plugin.video.jellyfin"


def kodi_version():
    # Kodistubs returns empty string, causing Python 3 tests to choke on int()
    # TODO: Make Kodistubs version configurable for testing purposes
    if sys.version_info.major == 2:
        default_versionstring = "18"
    else:
        default_versionstring = "19.1 (19.1.0) Git:20210509-85e05228b4"

    version_string = xbmc.getInfoLabel('System.BuildVersion') or default_versionstring
    return int(version_string.split(' ', 1)[0].split('.', 1)[0])


def window(key, value=None, clear=False, window_id=10000):

    ''' Get or set window properties.
    '''
    window = xbmcgui.Window(window_id)

    if clear:

        LOG.debug("--[ window clear: %s ]", key)
        window.clearProperty(key.replace('.json', "").replace('.bool', ""))
    elif value is not None:
        if key.endswith('.json'):

            key = key.replace('.json', "")
            value = json.dumps(value)

        elif key.endswith('.bool'):

            key = key.replace('.bool', "")
            value = "true" if value else "false"

        window.setProperty(key, value)
    else:
        result = window.getProperty(key.replace('.json', "").replace('.bool', ""))

        if result:
            if key.endswith('.json'):
                result = json.loads(result)
            elif key.endswith('.bool'):
                result = result in ("true", "1")

        return result


def settings(setting, value=None):

    ''' Get or add add-on settings.
        getSetting returns unicode object.
    '''
    addon = xbmcaddon.Addon(addon_id())

    if value is not None:
        if setting.endswith('.bool'):

            setting = setting.replace('.bool', "")
            value = "true" if value else "false"

        addon.setSetting(setting, value)
    else:
        result = addon.getSetting(setting.replace('.bool', ""))

        if result and setting.endswith('.bool'):
            result = result in ("true", "1")

        return result


def create_id():
    return uuid4()


def compare_version(a, b):

    ''' -1 a is smaller
        1 a is larger
        0 equal
    '''
    a = LooseVersion(a)
    b = LooseVersion(b)

    if a < b:
        return -1

    if a > b:
        return 1

    return 0


def find(dict, item):

    ''' Find value in dictionary.
    '''
    if item in dict:
        return dict[item]

    for key, value in sorted(iteritems(dict), key=lambda kv: (kv[1], kv[0])):

        if re.match(key, item, re.I):
            return dict[key]


def event(method, data=None, sender=None, hexlify=False):

    ''' Data is a dictionary.
    '''
    data = data or {}
    sender = sender or "plugin.video.jellyfin"

    if hexlify:
        data = ensure_text(binascii.hexlify(ensure_binary(json.dumps(data))))

    data = '"[%s]"' % json.dumps(data).replace('"', '\\"')

    LOG.debug("---[ event: %s/%s ] %s", sender, method, data)

    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % (sender, method, data))


def dialog(dialog_type, *args, **kwargs):

    d = xbmcgui.Dialog()

    if "icon" in kwargs:
        kwargs['icon'] = kwargs['icon'].replace(
            "{jellyfin}",
            "special://home/addons/plugin.video.jellyfin/resources/icon.png"
        )
    if "heading" in kwargs:
        kwargs['heading'] = kwargs['heading'].replace("{jellyfin}", translate('addon_name'))

    if args:
        args = list(args)
        args[0] = args[0].replace("{jellyfin}", translate('addon_name'))

    types = {
        'yesno': d.yesno,
        'ok': d.ok,
        'notification': d.notification,
        'input': d.input,
        'select': d.select,
        'numeric': d.numeric,
        'multi': d.multiselect
    }
    return types[dialog_type](*args, **kwargs)


def should_stop():

    ''' Checkpoint during the sync process.
    '''
    if xbmc.Monitor().waitForAbort(0.00001):
        return True

    if window('jellyfin_should_stop.bool'):
        LOG.info("exiiiiitttinggg")
        return True

    return not window('jellyfin_online.bool')


def get_screensaver():

    ''' Get the current screensaver value.
    '''
    result = JSONRPC('Settings.getSettingValue').execute({'setting': "screensaver.mode"})
    try:
        return result['result']['value']
    except KeyError:
        return ""


def set_screensaver(value):

    ''' Toggle the screensaver
    '''
    params = {
        'setting': "screensaver.mode",
        'value': value
    }
    result = JSONRPC('Settings.setSettingValue').execute(params)
    LOG.info("---[ screensaver/%s ] %s", value, result)


class JSONRPC(object):

    id = 1
    jsonrpc_version = "2.0"

    def __init__(self, method, **kwargs):

        self.method = method

        for arg in kwargs:
            self.arg = arg

    def _query(self):

        query = {
            'jsonrpc': self.jsonrpc_version,
            'id': self.id,
            'method': self.method,
        }
        if self.params is not None:
            query['params'] = self.params

        return json.dumps(query)

    def execute(self, params=None):

        self.params = params
        return json.loads(xbmc.executeJSONRPC(self._query()))


def validate(path):

    ''' Verify if path is accessible.
    '''
    if window('jellyfin_pathverified.bool'):
        return True

    if not xbmcvfs.exists(path):
        LOG.info("Could not find %s", path)

        if dialog("yesno", "{jellyfin}", "%s %s. %s" % (translate(33047), path, translate(33048))):

            return False

    window('jellyfin_pathverified.bool', True)

    return True


def validate_bluray_dir(path):

    ''' Verify if path/BDMV/ is accessible.
    '''

    path = path + '/BDMV/'

    if not xbmcvfs.exists(path):
        return False

    window('jellyfin_pathverified.bool', True)

    return True


def validate_dvd_dir(path):

    ''' Verify if path/VIDEO_TS/ is accessible.
    '''

    path = path + '/VIDEO_TS/'

    if not xbmcvfs.exists(path):
        return False

    window('jellyfin_pathverified.bool', True)

    return True


def values(item, keys):

    ''' Grab the values in the item for a list of keys {key},{key1}....
        If the key has no brackets, the key will be passed as is.
    '''
    return (item[key.replace('{', "").replace('}', "")] if isinstance(key, text_type) and key.startswith('{') else key for key in keys)


def delete_folder(path):

    ''' Delete objects from kodi cache
    '''
    LOG.debug("--[ delete folder ]")
    dirs, files = xbmcvfs.listdir(path)

    delete_recursive(path, dirs)

    for file in files:
        xbmcvfs.delete(os.path.join(path, file))

    xbmcvfs.delete(path)

    LOG.info("DELETE %s", path)


def delete_recursive(path, dirs):

    ''' Delete files and dirs recursively.
    '''
    for directory in dirs:
        dirs2, files = xbmcvfs.listdir(os.path.join(path, directory))

        for file in files:
            xbmcvfs.delete(os.path.join(path, directory, file))

        delete_recursive(os.path.join(path, directory), dirs2)
        xbmcvfs.rmdir(os.path.join(path, directory))


def unzip(path, dest, folder=None):

    ''' Unzip file. zipfile module seems to fail on android with badziperror.
    '''
    path = quote_plus(path)
    root = "zip://" + path + '/'

    if folder:

        xbmcvfs.mkdir(os.path.join(dest, folder))
        dest = os.path.join(dest, folder)
        root = get_zip_directory(root, folder)

    dirs, files = xbmcvfs.listdir(root)

    if dirs:
        unzip_recursive(root, dirs, dest)

    for file in files:
        unzip_file(os.path.join(root, file), os.path.join(dest, file))

    LOG.info("Unzipped %s", path)


def unzip_recursive(path, dirs, dest):

    for directory in dirs:

        dirs_dir = os.path.join(path, directory)
        dest_dir = os.path.join(dest, directory)
        xbmcvfs.mkdir(dest_dir)

        dirs2, files = xbmcvfs.listdir(dirs_dir)

        if dirs2:
            unzip_recursive(dirs_dir, dirs2, dest_dir)

        for file in files:
            unzip_file(os.path.join(dirs_dir, file), os.path.join(dest_dir, file))


def unzip_file(path, dest):

    ''' Unzip specific file. Path should start with zip://
    '''
    xbmcvfs.copy(path, dest)
    LOG.debug("unzip: %s to %s", path, dest)


def get_zip_directory(path, folder):

    dirs, files = xbmcvfs.listdir(path)

    if folder in dirs:
        return os.path.join(path, folder)

    for directory in dirs:
        result = get_zip_directory(os.path.join(path, directory), folder)
        if result:
            return result


def copytree(path, dest):

    ''' Copy folder content from one to another.
    '''
    dirs, files = xbmcvfs.listdir(path)

    if not xbmcvfs.exists(dest):
        xbmcvfs.mkdirs(dest)

    if dirs:
        copy_recursive(path, dirs, dest)

    for file in files:
        copy_file(os.path.join(path, file), os.path.join(dest, file))

    LOG.info("Copied %s", path)


def copy_recursive(path, dirs, dest):

    for directory in dirs:

        dirs_dir = os.path.join(path, directory)
        dest_dir = os.path.join(dest, directory)
        xbmcvfs.mkdir(dest_dir)

        dirs2, files = xbmcvfs.listdir(dirs_dir)

        if dirs2:
            copy_recursive(dirs_dir, dirs2, dest_dir)

        for file in files:
            copy_file(os.path.join(dirs_dir, file), os.path.join(dest_dir, file))


def copy_file(path, dest):

    ''' Copy specific file.
    '''
    if path.endswith('.pyo'):
        return

    xbmcvfs.copy(path, dest)
    LOG.debug("copy: %s to %s", path, dest)


def normalize_string(text):

    ''' For theme media, do not modify unless modified in TV Tunes.
        Remove dots from the last character as windows can not have directories
        with dots at the end
    '''
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.strip()

    text = text.rstrip('.')
    text = unicodedata.normalize('NFKD', text_type(text, 'utf-8')).encode('ascii', 'ignore')

    return text


def split_list(itemlist, size):

    ''' Split up list in pieces of size. Will generate a list of lists
    '''
    return [itemlist[i:i + size] for i in range(0, len(itemlist), size)]


def convert_to_local(date, timezone=tz.tzlocal()):

    ''' Convert the local datetime to local.
    '''
    try:
        date = parser.parse(date) if isinstance(date, string_types) else date
        date = date.replace(tzinfo=tz.tzutc())
        date = date.astimezone(timezone)
        # Bad metadata defaults to date 1-1-1.  Catch it and don't throw errors
        if date.year < 1900:
            # FIXME(py2): strftime don't like dates below 1900
            return "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
                date.year,
                date.month,
                date.day,
                date.hour,
                date.minute,
                date.second,
            )
        else:
            return date.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as error:
        LOG.exception('Item date: {} --- {}'.format(str(date), error))

        return str(date)


def has_attribute(obj, name):
    try:
        object.__getattribute__(obj, name)
        return True
    except AttributeError:
        return False


def set_addon_mode():

    ''' Setup playback mode. If native mode selected, check network credentials.
    '''
    value = dialog("yesno",
                   translate('playback_mode'),
                   translate(33035),
                   nolabel=translate('addon_mode'),
                   yeslabel=translate('native_mode'))

    settings('useDirectPaths', value="1" if value else "0")

    if value:
        dialog("ok", "{jellyfin}", translate(33145))

    LOG.info("Add-on playback: %s", settings('useDirectPaths') == "0")


class JsonDebugPrinter(object):

    ''' Helper class to defer converting data to JSON until it is needed.
    See: https://github.com/jellyfin/jellyfin-kodi/pull/193
    '''

    def __init__(self, data):
        self.data = data

    def __str__(self):
        return json.dumps(self.data, indent=4)


def get_filesystem_encoding():
    enc = sys.getfilesystemencoding()

    if not enc:
        enc = sys.getdefaultencoding()

    if not enc or enc == 'ascii':
        enc = 'utf-8'

    return enc


def find_library(server, item):
    from ..database import get_sync

    sync = get_sync()
    whitelist = [x.replace('Mixed:', "") for x in sync['Whitelist']]
    ancestors = server.jellyfin.get_ancestors(item['Id'])
    for ancestor in ancestors:
        if ancestor['Id'] in whitelist:
            return ancestor

    LOG.error('No ancestor found, not syncing item with ID: {}'.format(item['Id']))
    return {}


def translate_path(path):
    '''
    Use new library location for translate path starting in Kodi 19
    '''
    version = kodi_version()

    if version > 18:
        return xbmcvfs.translatePath(path)
    else:
        return xbmc.translatePath(path)
