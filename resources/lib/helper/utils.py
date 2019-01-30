# -*- coding: utf-8 -*-

#################################################################################################

import binascii
import json
import logging
import os
import re
import unicodedata
import urllib
from uuid import uuid4

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import _
from dateutil import tz, parser

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################

def addon_id():
    return "plugin.video.emby"

def kodi_version():
    return xbmc.getInfoLabel('System.BuildVersion')[:2]

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
    a = a.split('.')
    b = b.split('.')

    for i in range(0, max(len(a), len(b)), 1):
        try:
            aVal = a[i]
        except IndexError:
            aVal = 0

        try:    
            bVal = b[i]
        except IndexError:
            bVal = 0

        if aVal < bVal:
            return -1

        if aVal > bVal:
            return 1

    return 0

def find(dict, item):

    ''' Find value in dictionary.
    '''
    if item in dict:
        return dict[item]

    for key,value in sorted(dict.iteritems(), key=lambda (k,v): (v,k)):

        if re.match(key, item, re.I):
            return dict[key]

def event(method, data=None, sender=None, hexlify=False):

    ''' Data is a dictionary.
    '''
    data = data or {}
    sender = sender or "plugin.video.emby"

    if hexlify:
        data = '\\"[\\"{0}\\"]\\"'.format(binascii.hexlify(json.dumps(data)))
    else:
        data = '"[%s]"' % json.dumps(data).replace('"', '\\"')

    xbmc.executebuiltin('NotifyAll(%s, %s, %s)' % (sender, method, data))
    LOG.debug("---[ event: %s/%s ] %s", sender, method, data)

def dialog(dialog_type, *args, **kwargs):

    d = xbmcgui.Dialog()

    if "icon" in kwargs:
        kwargs['icon'] = kwargs['icon'].replace("{emby}",
                                                "special://home/addons/plugin.video.emby/icon.png")
    if "heading" in kwargs:
        kwargs['heading'] = kwargs['heading'].replace("{emby}", _('addon_name'))

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

    if window('emby_should_stop.bool'):
        LOG.info("exiiiiitttinggg")
        return True

    if not window('emby_online.bool'):
        return True

    return False

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

    version = 1
    jsonrpc = "2.0"

    def __init__(self, method, **kwargs):
        
        self.method = method

        for arg in kwargs:
            self.arg = arg

    def _query(self):

        query = {
            'jsonrpc': self.jsonrpc,
            'id': self.version,
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
    if window('emby_pathverified.bool'):
        return True

    path = path if os.path.supports_unicode_filenames else path.encode('utf-8')

    if not xbmcvfs.exists(path):
        LOG.info("Could not find %s", path)

        if dialog("yesno", heading="{emby}", line1="%s %s. %s" % (_(33047), path, _(33048))):

            return False

    window('emby_pathverified.bool', True)

    return True

def values(item, keys):

    ''' Grab the values in the item for a list of keys {key},{key1}....
        If the key has no brackets, the key will be passed as is.
    '''
    return (item[key.replace('{', "").replace('}', "")] if type(key) == str and key.startswith('{') else key for key in keys)

def indent(elem, level=0):
    
    ''' Prettify xml docs.
    '''
    try:
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
              elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
              elem.tail = i
            for elem in elem:
              indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
              elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
              elem.tail = i
    except Exception:
        return

def write_xml(content, file):
    with open(file, 'w') as infile:

        content = content.replace("'", '"')
        content = content.replace('?>', ' standalone="yes" ?>', 1)
        infile.write(content)

def delete_folder(path=None):

    ''' Delete objects from kodi cache
    '''
    LOG.debug("--[ delete folder ]")
    delete_path = path is not None
    path = path or xbmc.translatePath('special://temp/emby').decode('utf-8')
    dirs, files = xbmcvfs.listdir(path)

    delete_recursive(path, dirs)

    for file in files:
        xbmcvfs.delete(os.path.join(path, file.decode('utf-8')))

    if delete_path:
        xbmcvfs.delete(path)
    
    LOG.info("DELETE %s", path)

def delete_recursive(path, dirs):

    ''' Delete files and dirs recursively.
    '''
    for directory in dirs:
        dirs2, files = xbmcvfs.listdir(os.path.join(path, directory.decode('utf-8')))

        for file in files:
            xbmcvfs.delete(os.path.join(path, directory.decode('utf-8'), file.decode('utf-8')))

        delete_recursive(os.path.join(path, directory.decode('utf-8')), dirs2)
        xbmcvfs.rmdir(os.path.join(path, directory.decode('utf-8')))

def unzip(path, dest, folder=None):

    ''' Unzip file. zipfile module seems to fail on android with badziperror.
    '''
    path = urllib.quote_plus(path)
    root = "zip://" + path + '/'
    
    if folder:

        xbmcvfs.mkdir(os.path.join(dest, folder))
        dest = os.path.join(dest, folder)
        root = get_zip_directory(root, folder)

    dirs, files = xbmcvfs.listdir(root)

    if dirs:
        unzip_recursive(root, dirs, dest)

    for file in files:
        unzip_file(os.path.join(root, file.decode('utf-8')), os.path.join(dest, file.decode('utf-8')))

    LOG.info("Unzipped %s", path)

def unzip_recursive(path, dirs, dest):

    for directory in dirs:

        dirs_dir = os.path.join(path, directory.decode('utf-8'))
        dest_dir = os.path.join(dest, directory.decode('utf-8'))
        xbmcvfs.mkdir(dest_dir)

        dirs2, files = xbmcvfs.listdir(dirs_dir)

        if dirs2:
            unzip_recursive(dirs_dir, dirs2, dest_dir)

        for file in files:
            unzip_file(os.path.join(dirs_dir, file.decode('utf-8')), os.path.join(dest_dir, file.decode('utf-8')))

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
        result = get_zip_directory(os.path.join(path, directory.decode('utf-8')), folder)
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
        copy_file(os.path.join(path, file.decode('utf-8')), os.path.join(dest, file.decode('utf-8')))

    LOG.info("Copied %s", path)

def copy_recursive(path, dirs, dest):

    for directory in dirs:

        dirs_dir = os.path.join(path, directory.decode('utf-8'))
        dest_dir = os.path.join(dest, directory.decode('utf-8'))
        xbmcvfs.mkdir(dest_dir)

        dirs2, files = xbmcvfs.listdir(dirs_dir)

        if dirs2:
            copy_recursive(dirs_dir, dirs2, dest_dir)

        for file in files:
            copy_file(os.path.join(dirs_dir, file.decode('utf-8')), os.path.join(dest_dir, file.decode('utf-8')))

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
    text = unicodedata.normalize('NFKD', unicode(text, 'utf-8')).encode('ascii', 'ignore')

    return text

def split_list(itemlist, size):
    
    ''' Split up list in pieces of size. Will generate a list of lists
    '''
    return [itemlist[i:i+size] for i in range(0, len(itemlist), size)]

def convert_to_local(date):

    ''' Convert the local datetime to local.
    '''
    try:
        date = parser.parse(date) if type(date) in (unicode, str) else date
        date = date.replace(tzinfo=tz.tzutc())
        date = date.astimezone(tz.tzlocal())

        return date.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as error:
        LOG.error(error)

        return str(date)
