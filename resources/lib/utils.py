# -*- coding: utf-8 -*-

#################################################################################################

import cProfile
import inspect
import pstats
import sqlite3
import time
import unicodedata
import xml.etree.ElementTree as etree

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

#################################################################################################


def logMsg(title, msg, level=1):
    
    # Get the logLevel set in UserClient
    try:
        logLevel = int(window('emby_logLevel'))
    except ValueError:
        logLevel = 0
    
    if logLevel >= level:
        
        if logLevel == 2: # inspect.stack() is expensive
            try:
                xbmc.log("%s -> %s : %s" % (title, inspect.stack()[1][3], msg))
            except UnicodeEncodeError:
                xbmc.log("%s -> %s : %s" % (title, inspect.stack()[1][3], msg.encode('utf-8')))
        else:
            try:
                xbmc.log("%s -> %s" % (title, msg))
            except UnicodeEncodeError:
                xbmc.log("%s -> %s" % (title, msg.encode('utf-8')))

def window(property, value=None, clear=False, windowid=10000):
    # Get or set window property
    WINDOW = xbmcgui.Window(windowid)
    
    if clear:
        WINDOW.clearProperty(property)
    elif value is not None:
        WINDOW.setProperty(property, value)
    else:
        return WINDOW.getProperty(property)

def settings(setting, value=None):
    # Get or add addon setting
    addon = xbmcaddon.Addon(id='plugin.video.emby')
    
    if value is not None:
        addon.setSetting(setting, value)
    else:
        return addon.getSetting(setting)

def language(stringid):
    # Central string retrieval
    addon = xbmcaddon.Addon(id='plugin.video.emby')
    string = addon.getLocalizedString(stringid)

    return string

def kodiSQL(type="video"):
    
    if type == "emby":
        dbPath = xbmc.translatePath("special://database/emby.db").decode('utf-8')
    elif type == "music":
        dbPath = getKodiMusicDBPath()
    elif type == "texture":
        dbPath = xbmc.translatePath("special://database/Textures13.db").decode('utf-8')
    else:
        dbPath = getKodiVideoDBPath()
    
    connection = sqlite3.connect(dbPath)
    return connection

def getKodiVideoDBPath():

    kodibuild = xbmc.getInfoLabel('System.BuildVersion')[:2]
    dbVersion = {

        "13": 78,   # Gotham
        "14": 90,   # Helix
        "15": 93,   # Isengard
        "16": 99    # Jarvis
    }

    dbPath = xbmc.translatePath(
                    "special://database/MyVideos%s.db"
                    % dbVersion.get(kodibuild, "")).decode('utf-8')
    return dbPath

def getKodiMusicDBPath():

    kodibuild = xbmc.getInfoLabel('System.BuildVersion')[:2]
    dbVersion = {

        "13": 46,   # Gotham
        "14": 48,   # Helix
        "15": 52,   # Isengard
        "16": 56    # Jarvis
    }

    dbPath = xbmc.translatePath(
                    "special://database/MyMusic%s.db"
                    % dbVersion.get(kodibuild, "")).decode('utf-8')
    return dbPath

def reset():

    dialog = xbmcgui.Dialog()

    resp = dialog.yesno("Warning", "Are you sure you want to reset your local Kodi database?")
    if resp == 0:
        return

    # first stop any db sync
    window('emby_shouldStop', value="true")
    count = 10
    while window('emby_dbScan') == "true":
        logMsg("EMBY", "Sync is running, will retry: %s..." % count)
        count -= 1
        if count == 0:
            dialog.ok("Warning", "Could not stop the database from running. Try again.")
            return
        xbmc.sleep(1000)

    # Clean up the playlists
    path = xbmc.translatePath("special://profile/playlists/video/").decode('utf-8')
    dirs, files = xbmcvfs.listdir(path)
    for file in files:
        if file.startswith('Emby'):
            xbmcvfs.delete("%s%s" % (path, file))

    # Clean up the video nodes
    import shutil
    path = xbmc.translatePath("special://profile/library/video/").decode('utf-8')
    dirs, files = xbmcvfs.listdir(path)
    for dir in dirs:
        if dir.startswith('Emby'):
            shutil.rmtree("%s%s" % (path, dir))
    for file in files:
        if file.startswith('emby'):
            xbmcvfs.delete("%s%s" % (path, file))

    # Wipe the kodi databases
    logMsg("EMBY", "Resetting the Kodi video database.")
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

    if settings('disableMusic') != "true":
        logMsg("EMBY", "Resetting the Kodi music database.")
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
    logMsg("EMBY", "Resetting the Emby database.")
    connection = kodiSQL('emby')
    cursor = connection.cursor()
    cursor.execute('SELECT tbl_name FROM sqlite_master WHERE type="table"')
    rows = cursor.fetchall()
    for row in rows:
        tablename = row[0]
        if tablename != "version":
            cursor.execute("DELETE FROM " + tablename)
    connection.commit()
    cursor.close()
    
    # reset the install run flag  
    settings('SyncInstallRunDone', value="false")

    # Remove emby info
    resp = dialog.yesno("Warning", "Reset all Emby Addon settings?")
    if resp == 1:
        # Delete the settings
        addon = xbmcaddon.Addon()
        addondir = xbmc.translatePath(addon.getAddonInfo('profile')).decode('utf-8')
        dataPath = "%ssettings.xml" % addondir
        xbmcvfs.delete(dataPath)
        logMsg("EMBY", "Deleting: settings.xml", 1)

    dialog.ok(
        heading="Emby for Kodi",
        line1="Database reset has completed, Kodi will now restart to apply the changes.")
    xbmc.executebuiltin('RestartApp')

def startProfiling():
    
    pr = cProfile.Profile()
    pr.enable()
    
    return pr

def stopProfiling(pr, profileName):
    
    pr.disable()
    ps = pstats.Stats(pr)
    
    profiles = xbmc.translatePath("%sprofiles/"
                % xbmcaddon.Addon().getAddonInfo('profile')).decode('utf-8')

    if not xbmcvfs.exists(profiles):
        # Create the profiles folder
        xbmcvfs.mkdir(profiles)

    timestamp = time.strftime("%Y-%m-%d %H-%M-%S")
    profile = "%s%s_profile_(%s).tab" % (profiles, profileName, timestamp)
    
    f = open(profile, 'wb')
    f.write("NumbCalls\tTotalTime\tCumulativeTime\tFunctionName\tFileName\r\n")
    for (key, value) in ps.stats.items():
        (filename, count, func_name) = key
        (ccalls, ncalls, total_time, cumulative_time, callers) = value
        try:
            f.write(
                "%s\t%s\t%s\t%s\t%s\r\n"
                % (ncalls, "{:10.4f}".format(total_time),
                    "{:10.4f}".format(cumulative_time), func_name, filename))
        except ValueError:
            f.write(
                "%s\t%s\t%s\t%s\t%s\r\n"
                % (ncalls, "{0}".format(total_time),
                    "{0}".format(cumulative_time), func_name, filename))
    f.close()

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
    for i in range(1, 3):

            for source in root.findall('.//path'):
                if source.text == "smb://embydummy/dummypath%s/" % i:
                    # Already there, skip
                    break
            else:
                source = etree.SubElement(video, 'source')
                etree.SubElement(source, 'name').text = "Emby"
                etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = (

                    "smb://embydummy/dummypath%s/" % i
                )
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
        option = dialog.select("Modify/Remove network credentials", ["Modify", "Remove"])

        if option < 0:
            # User cancelled dialog
            return

        elif option == 1:
            # User selected remove
            iterator = root.getiterator('passwords')

            for paths in iterator:
                for path in paths:
                    if path.find('.//from').text == "smb://%s/" % credentials:
                        paths.remove(path)
                        logMsg("EMBY", "Successfully removed credentials for: %s"
                                % credentials, 1)
                        etree.ElementTree(root).write(xmlpath)
                        break
            else:
                logMsg("EMBY", "Failed to find saved server: %s in passwords.xml" % credentials, 1)
            
            settings('networkCreds', value="")
            xbmcgui.Dialog().notification(
                                heading="Emby for Kodi",
                                message="%s removed from passwords.xml!" % credentials,
                                icon="special://home/addons/plugin.video.emby/icon.png",
                                time=1000,
                                sound=False)
            return

        elif option == 0:
            # User selected to modify
            server = dialog.input("Modify the computer name or ip address", credentials)
            if not server:
                return
    else:
        # No credentials added
        dialog.ok(
            heading="Network credentials",
            line1= (
                "Input the server name or IP address as indicated in your emby library paths. "
                'For example, the server name: \\\\SERVER-PC\\path\\ is "SERVER-PC".'))
        server = dialog.input("Enter the server name or IP address", settings('ipaddress'))
        if not server:
            return

    # Network username
    user = dialog.input("Enter the network username")
    if not user:
        return
    # Network password
    password = dialog.input(
                        heading="Enter the network password",
                        option=xbmcgui.ALPHANUM_HIDE_INPUT)
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
    logMsg("EMBY", "Added server: %s to passwords.xml" % server, 1)
    # Prettify and write to file
    try:
        indent(root)
    except: pass
    etree.ElementTree(root).write(xmlpath)
    
    dialog.notification(
            heading="Emby for Kodi",
            message="%s added to passwords.xml!" % server,
            icon="special://home/addons/plugin.video.emby/icon.png",
            time=1000,
            sound=False)

def playlistXSP(mediatype, tagname, viewtype="", delete=False):
    # Tagname is in unicode - actions: add or delete
    tagname = tagname.encode('utf-8')
    cleantagname = normalize_nodes(tagname)
    path = xbmc.translatePath("special://profile/playlists/video/").decode('utf-8')
    if viewtype == "mixed":
        plname = "%s - %s" % (tagname, mediatype)
        xsppath = "%sEmby %s - %s.xsp" % (path, cleantagname, mediatype)
    else:
        plname = tagname
        xsppath = "%sEmby %s.xsp" % (path, cleantagname)

    # Create the playlist directory
    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)

    # Only add the playlist if it doesn't already exists
    if xbmcvfs.exists(xsppath):

        if delete:
            xbmcvfs.delete(xsppath)
            logMsg("EMBY", "Successfully removed playlist: %s." % tagname, 1)
        
        return

    # Using write process since there's no guarantee the xml declaration works with etree
    itemtypes = {
        'homevideos': "movies"
    }
    f = open(xsppath, 'w')
    f.write(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>\n'
        '<smartplaylist type="%s">\n\t'
            '<name>Emby %s</name>\n\t'
            '<match>all</match>\n\t'
            '<rule field="tag" operator="is">\n\t\t'
                '<value>%s</value>\n\t'
            '</rule>'
        % (itemtypes.get(mediatype, mediatype), plname, tagname))
    f.close()
    logMsg("EMBY", "Successfully added playlist: %s" % tagname)