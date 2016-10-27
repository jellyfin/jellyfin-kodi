# -*- coding: utf-8 -*-

#################################################################################################


import inspect
import json
import logging
import sqlite3
import StringIO
import os
import sys
import time
import unicodedata
import xml.etree.ElementTree as etree
from datetime import datetime

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################
# Main methods

def window(property_, value=None, clear=False, window_id=10000):
    # Get or set window property
    WINDOW = xbmcgui.Window(window_id)

    if clear:
        WINDOW.clearProperty(property_)
    elif value is not None:
        if ".json" in property_:
            value = json.dumps(value)
        WINDOW.setProperty(property_, value)
    else:
        result = WINDOW.getProperty(property_)
        if result and ".json" in property_:
            result = json.loads(result)
        return result

def settings(setting, value=None):
    # Get or add addon setting
    addon = xbmcaddon.Addon(id='plugin.video.emby')
    
    if value is not None:
        addon.setSetting(setting, value)
    else: # returns unicode object
        return addon.getSetting(setting) 

def language(string_id):
    # Central string retrieval - unicode
    return xbmcaddon.Addon(id='plugin.video.emby').getLocalizedString(string_id)

def dialog(type_, *args, **kwargs):

    d = xbmcgui.Dialog()

    if "icon" in kwargs:
        kwargs['icon'] = kwargs['icon'].replace("{emby}",
                                                "special://home/addons/plugin.video.emby/icon.png")
    if "heading" in kwargs:
        kwargs['heading'] = kwargs['heading'].replace("{emby}", language(29999))

    types = {
        'yesno': d.yesno,
        'ok': d.ok,
        'notification': d.notification,
        'input': d.input,
        'select': d.select,
        'numeric': d.numeric
    }
    return types[type_](*args, **kwargs)


class JSONRPC(object):

    id_ = 1
    jsonrpc = "2.0"

    def __init__(self, method, **kwargs):
        
        self.method = method

        for arg in kwargs: # id_(int), jsonrpc(str)
            self.arg = arg

    def _query(self):

        query = {
            
            'jsonrpc': self.jsonrpc,
            'id': self.id_,
            'method': self.method,
        }
        if self.params is not None:
            query['params'] = self.params

        return json.dumps(query)

    def execute(self, params=None):

        self.params = params
        return json.loads(xbmc.executeJSONRPC(self._query()))

#################################################################################################
# Database related methods

def should_stop():
    # Checkpoint during the syncing process
    if xbmc.Monitor().abortRequested():
        return True
    elif window('emby_shouldStop') == "true":
        return True
    else: # Keep going
        return False

def kodiSQL(media_type="video"):

    if media_type == "emby":
        dbPath = xbmc.translatePath("special://database/emby.db").decode('utf-8')
    elif media_type == "texture":
        dbPath = xbmc.translatePath("special://database/Textures13.db").decode('utf-8')
    elif media_type == "music":
        dbPath = getKodiMusicDBPath()
    else:
        dbPath = getKodiVideoDBPath()

    if settings('dblock') == "true":
        connection = sqlite3.connect(dbPath, isolation_level=None, timeout=20)
    else:
        connection = sqlite3.connect(dbPath, timeout=20)
    return connection

def getKodiVideoDBPath():

    dbVersion = {

        "13": 78,   # Gotham
        "14": 90,   # Helix
        "15": 93,   # Isengard
        "16": 99,   # Jarvis
        "17": 107   # Krypton
    }

    dbPath = xbmc.translatePath(
                "special://database/MyVideos%s.db"
                % dbVersion.get(xbmc.getInfoLabel('System.BuildVersion')[:2], "")).decode('utf-8')
    return dbPath

def getKodiMusicDBPath():

    dbVersion = {

        "13": 46,   # Gotham
        "14": 48,   # Helix
        "15": 52,   # Isengard
        "16": 56,   # Jarvis
        "17": 60    # Krypton
    }

    dbPath = xbmc.translatePath(
                "special://database/MyMusic%s.db"
                % dbVersion.get(xbmc.getInfoLabel('System.BuildVersion')[:2], "")).decode('utf-8')
    return dbPath

def querySQL(query, args=None, cursor=None, conntype=None):

    result = None
    manualconn = False
    failed = False

    if cursor is None:
        if conntype is None:
            log.info("New connection type is missing.")
            return result
        else:
            manualconn = True
            connection = kodiSQL(conntype)
            cursor = connection.cursor()

    attempts = 0
    while attempts < 3:
        try:
            log.debug("Query: %s Args: %s" % (query, args))
            if args is None:
                result = cursor.execute(query)
            else:
                result = cursor.execute(query, args)
            break # Query successful, break out of while loop
        except sqlite3.OperationalError as e:
            if "database is locked" in e:
                log.warn("%s...Attempt: %s" % (e, attempts))
                attempts += 1
                xbmc.sleep(1000)
            else:
                log.error(e)
                if manualconn:
                    cursor.close()
                raise
        except sqlite3.Error as e:
            log.error(e)
            if manualconn:
                cursor.close()
            raise
    else:
        failed = True
        log.info("FAILED // Query: %s Args: %s" % (query, args))

    if manualconn:
        if failed:
            cursor.close()
        else:
            connection.commit()
            cursor.close()

    log.debug(result)
    return result

#################################################################################################
# Utility methods

def getScreensaver():
    # Get the current screensaver value
    result = JSONRPC('Settings.getSettingValues').execute({'setting': "screensaver.mode"})
    try:
        return result['result']['value']
    except KeyError:
        return ""

def setScreensaver(value):
    # Toggle the screensaver
    params = {
        'setting': "screensaver.mode",
        'value': value
    }
    result = JSONRPC('Settings.setSettingValue').execute(params)
    log.info("Toggling screensaver: %s %s" % (value, result))

def convertDate(date):
    try:
        date = datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
    except (ImportError, TypeError):
        # TypeError: attribute of type 'NoneType' is not callable
        # Known Kodi/python error
        date = datetime(*(time.strptime(date, "%Y-%m-%dT%H:%M:%SZ")[0:6]))

    return date

def normalize_nodes(text):
    # For video nodes
    text = text.replace(":", "")
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace("<", "")
    text = text.replace(">", "")
    text = text.replace("*", "")
    text = text.replace("?", "")
    text = text.replace('|', "")
    text = text.replace('(', "")
    text = text.replace(')', "")
    text = text.strip()
    # Remove dots from the last character as windows can not have directories
    # with dots at the end
    text = text.rstrip('.')
    text = unicodedata.normalize('NFKD', unicode(text, 'utf-8')).encode('ascii', 'ignore')

    return text

def normalize_string(text):
    # For theme media, do not modify unless
    # modified in TV Tunes
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

def indent(elem, level=0):
    # Prettify xml trees
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
          elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
          elem.tail = i
        for elem in elem:
          indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
          elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
          elem.tail = i

def catch_except(errors=(Exception, ), default_value=False):
    # Will wrap method with try/except and print parameters for easier debugging
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except errors as error:
                log.exception(error)
                log.error("function: %s \n args: %s \n kwargs: %s",
                          func.__name__, args, kwargs)
                return default_value

        return wrapper
    return decorator

def profiling(sortby="cumulative"):
    # Will print results to Kodi log
    def decorator(func):
        def wrapper(*args, **kwargs):
            import cProfile
            import pstats
            
            pr = cProfile.Profile()

            pr.enable()
            result = func(*args, **kwargs)
            pr.disable()

            s = StringIO.StringIO()
            ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
            ps.print_stats()
            log.info(s.getvalue())

            return result

        return wrapper
    return decorator

#################################################################################################
# Addon utilities

def reset():

    dialog = xbmcgui.Dialog()

    if not dialog.yesno(language(29999), language(33074)):
        return

    # first stop any db sync
    window('emby_online', value="reset")
    window('emby_shouldStop', value="true")
    count = 10
    while window('emby_dbScan') == "true":
        log.info("Sync is running, will retry: %s..." % count)
        count -= 1
        if count == 0:
            dialog.ok(language(29999), language(33085))
            return
        xbmc.sleep(1000)

    # Clean up the playlists
    deletePlaylists()

    # Clean up the video nodes
    deleteNodes()

    # Wipe the kodi databases
    log.warn("Resetting the Kodi video database.")
    connection = kodiSQL('video')
    cursor = connection.cursor()
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tablename = row[0]
        if tablename != "version":
            cursor.execute("DELETE FROM " + tablename)
    connection.commit()
    cursor.close()

    if settings('enableMusic') == "true":
        log.warn("Resetting the Kodi music database.")
        connection = kodiSQL('music')
        cursor = connection.cursor()
        cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
        rows = cursor.fetchall()
        for row in rows:
            tablename = row[0]
            if tablename != "version":
                cursor.execute("DELETE FROM " + tablename)
        connection.commit()
        cursor.close()

    # Wipe the emby database
    log.warn("Resetting the Emby database.")
    connection = kodiSQL('emby')
    cursor = connection.cursor()
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tablename = row[0]
        if tablename != "version":
            cursor.execute("DELETE FROM " + tablename)
    cursor.execute('DROP table IF EXISTS emby')
    cursor.execute('DROP table IF EXISTS view')
    cursor.execute("DROP table IF EXISTS version")
    connection.commit()
    cursor.close()

    # Offer to wipe cached thumbnails
    if dialog.yesno(language(29999), language(33086)):
        log.warn("Resetting all cached artwork")
        # Remove all existing textures first
        import artwork
        artwork.Artwork().delete_cache()

    # reset the install run flag
    settings('SyncInstallRunDone', value="false")

    # Remove emby info
    resp = dialog.yesno(language(29999), language(33087))
    if resp:
        import connectmanager
        # Delete the settings
        addon = xbmcaddon.Addon()
        addondir = xbmc.translatePath(
                   "special://profile/addon_data/plugin.video.emby/").decode('utf-8')
        dataPath = "%ssettings.xml" % addondir
        xbmcvfs.delete(dataPath)
        connectmanager.ConnectManager().clear_data()

    dialog.ok(heading=language(29999), line1=language(33088))
    xbmc.executebuiltin('RestartApp')
    return xbmcplugin.setResolvedUrl(int(sys.argv[1]), False, xbmcgui.ListItem())

def sourcesXML():
    # To make Master lock compatible
    path = xbmc.translatePath("special://profile/").decode('utf-8')
    xmlpath = "%ssources.xml" % path

    try:
        xmlparse = etree.parse(xmlpath)
    except: # Document is blank or missing
        root = etree.Element('sources')
    else:
        root = xmlparse.getroot()


    video = root.find('video')
    if video is None:
        video = etree.SubElement(root, 'video')
        etree.SubElement(video, 'default', attrib={'pathversion': "1"})

    # Add elements
    count = 2
    for source in root.findall('.//path'):
        if source.text == "smb://":
            count -= 1

        if count == 0:
            # sources already set
            break
    else:
        # Missing smb:// occurences, re-add.
        for i in range(0, count):
            source = etree.SubElement(video, 'source')
            etree.SubElement(source, 'name').text = "Emby"
            etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "smb://"
            etree.SubElement(source, 'allowsharing').text = "true"
    # Prettify and write to file
    try:
        indent(root)
    except: pass
    etree.ElementTree(root).write(xmlpath)

def passwordsXML():

    # To add network credentials
    path = xbmc.translatePath("special://userdata/").decode('utf-8')
    xmlpath = "%spasswords.xml" % path

    try:
        xmlparse = etree.parse(xmlpath)
    except: # Document is blank or missing
        root = etree.Element('passwords')
    else:
        root = xmlparse.getroot()

    dialog = xbmcgui.Dialog()
    credentials = settings('networkCreds')
    if credentials:
        # Present user with options
        option = dialog.select(language(33075), [language(33076), language(33077)])

        if option < 0:
            # User cancelled dialog
            return

        elif option == 1:
            # User selected remove
            for paths in root.getiterator('passwords'):
                for path in paths:
                    if path.find('.//from').text == "smb://%s/" % credentials:
                        paths.remove(path)
                        log.info("Successfully removed credentials for: %s" % credentials)
                        etree.ElementTree(root).write(xmlpath)
                        break
            else:
                log.info("Failed to find saved server: %s in passwords.xml" % credentials)

            settings('networkCreds', value="")
            xbmcgui.Dialog().notification(
                                heading=language(29999),
                                message="%s %s" % (language(33078), credentials),
                                icon="special://home/addons/plugin.video.emby/icon.png",
                                time=1000,
                                sound=False)
            return

        elif option == 0:
            # User selected to modify
            server = dialog.input(language(33083), credentials)
            if not server:
                return
    else:
        # No credentials added
        dialog.ok(heading=language(29999), line1=language(33082))
        server = dialog.input(language(33084))
        if not server:
            return

    # Network username
    user = dialog.input(language(33079))
    if not user:
        return
    # Network password
    password = dialog.input(heading=language(33080), option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if not password:
        return

    # Add elements
    for path in root.findall('.//path'):
        if path.find('.//from').text.lower() == "smb://%s/" % server.lower():
            # Found the server, rewrite credentials
            path.find('.//to').text = "smb://%s:%s@%s/" % (user, password, server)
            break
    else:
        # Server not found, add it.
        path = etree.SubElement(root, 'path')
        etree.SubElement(path, 'from', attrib={'pathversion': "1"}).text = "smb://%s/" % server
        topath = "smb://%s:%s@%s/" % (user, password, server)
        etree.SubElement(path, 'to', attrib={'pathversion': "1"}).text = topath
        # Force Kodi to see the credentials without restarting
        xbmcvfs.exists(topath)

    # Add credentials
    settings('networkCreds', value="%s" % server)
    log.info("Added server: %s to passwords.xml" % server)
    # Prettify and write to file
    try:
        indent(root)
    except: pass
    etree.ElementTree(root).write(xmlpath)

    dialog.notification(
            heading=language(29999),
            message="%s %s" % (language(33081), server),
            icon="special://home/addons/plugin.video.emby/icon.png",
            time=1000,
            sound=False)

def playlistXSP(mediatype, tagname, viewid, viewtype="", delete=False):
    # Tagname is in unicode - actions: add or delete
    tagname = tagname.encode('utf-8')

    path = xbmc.translatePath("special://profile/playlists/video/").decode('utf-8')
    if viewtype == "mixed":
        plname = "%s - %s" % (tagname, mediatype)
        xsppath = "%sEmby %s - %s.xsp" % (path, viewid, mediatype)
    else:
        plname = tagname
        xsppath = "%sEmby %s.xsp" % (path, viewid)

    # Create the playlist directory
    if not xbmcvfs.exists(path):
        log.info("Creating directory: %s" % path)
        xbmcvfs.mkdirs(path)

    # Only add the playlist if it doesn't already exists
    if xbmcvfs.exists(xsppath):

        if delete:
            xbmcvfs.delete(xsppath)
            log.info("Successfully removed playlist: %s." % tagname)

        return

    # Using write process since there's no guarantee the xml declaration works with etree
    itemtypes = {
        'homevideos': "movies"
    }
    log.info("Writing playlist file to: %s" % xsppath)
    try:
        f = xbmcvfs.File(xsppath, 'w')
    except:
        log.info("Failed to create playlist: %s" % xsppath)
        return
    else:
        f.write(
            '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
            '<smartplaylist type="%s">\n\t'
                '<name>Emby %s</name>\n\t'
                '<match>all</match>\n\t'
                '<rule field="tag" operator="is">\n\t\t'
                    '<value>%s</value>\n\t'
                '</rule>'
            '</smartplaylist>'
            % (itemtypes.get(mediatype, mediatype), plname, tagname))
        f.close()
    log.info("Successfully added playlist: %s" % tagname)

def deletePlaylists():

    # Clean up the playlists
    path = xbmc.translatePath("special://profile/playlists/video/").decode('utf-8')
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        if file.decode('utf-8').startswith('Emby'):
            xbmcvfs.delete("%s%s" % (path, file))

def deleteNodes():

    # Clean up video nodes
    import shutil
    path = xbmc.translatePath("special://profile/library/video/").decode('utf-8')
    dirs, files = xbmcvfs.listdir(path)
    for dir in dirs:
        if dir.decode('utf-8').startswith('Emby'):
            try:
                shutil.rmtree("%s%s" % (path, dir.decode('utf-8')))
            except:
                log.warn("Failed to delete directory: %s" % dir.decode('utf-8'))
    for file in files:
        if file.decode('utf-8').startswith('emby'):
            try:
                xbmcvfs.delete("%s%s" % (path, file.decode('utf-8')))
            except:
                log.warn("Failed to delete file: %s" % file.decode('utf-8'))