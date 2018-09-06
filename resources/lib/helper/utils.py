# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
import re
import unicodedata
from uuid import uuid4

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

from . import _

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
        window.clearProperty(key)
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

def find(dict, item):

    ''' Find value in dictionary.
    '''
    if item in dict:
        return dict[item]

    for key,value in sorted(dict.iteritems(), key=lambda (k,v): (v,k)):
        if re.match(key, item):
            return dict[key]

def event(method, data=None):

    ''' Data is a dictionary.
    '''
    data = data or {}
    xbmc.executebuiltin('NotifyAll(plugin.video.emby, %s, "[%s]")' % (method, json.dumps(data).replace('"', '\\"')))
    LOG.debug("---[ event: %s ] %s", method, data)

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
    if xbmc.Monitor().abortRequested():
        return True

    if window('emby_should_stop.bool'):
        LOG.info("exiiiiitttinggg")
        return True

    if not window('emby_online.bool'):
        return True

    return False

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
        if dialog(type_="yesno",
                  heading="{emby}",
                  line1="%s %s. %s" % (_(33047), path, _(33048))):

            return False

    window('emby_pathverified', "true")

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

def delete_build():

    ''' Delete objects from kodi cache
    '''
    LOG.debug("--[ delete objects ]")
    path = xbmc.translatePath('special://temp/emby/').decode('utf-8')
    dirs, files = xbmcvfs.listdir(path)

    delete_recursive(path, dirs)

    for file in files:
        xbmcvfs.delete(os.path.join(path, file.decode('utf-8')))

def delete_recursive(path, dirs):

    ''' Delete files and dirs recursively.
    '''
    for directory in dirs:

        dirs2, files = xbmcvfs.listdir(os.path.join(path, directory.decode('utf-8')))

        for file in files:
            xbmcvfs.delete(os.path.join(path, directory.decode('utf-8'), file.decode('utf-8')))

        delete_recursive(os.path.join(path, directory.decode('utf-8')), dirs2)
        xbmcvfs.rmdir(os.path.join(path, directory.decode('utf-8')))

def normalize_string(text):

    ''' For theme media, do not modify unless
        modified in TV Tunes.
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
    # Remove dots from the last character as windows can not have directories
    # with dots at the end
    text = text.rstrip('.')
    text = unicodedata.normalize('NFKD', unicode(text, 'utf-8')).encode('ascii', 'ignore')

    return text
