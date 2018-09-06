# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import os
import xml.etree.ElementTree as etree

import xbmc

from . import _, indent, write_xml

#################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

#################################################################################################

def sources():

    ''' Create master lock compatible sources.
        Also add the kodi.emby.media source.
    '''
    path = xbmc.translatePath("special://profile/").decode('utf-8')
    file = os.path.join(path, 'sources.xml')

    try:
        xml = etree.parse(file).getroot()
    except Exception:

        xml = etree.Element('sources')
        video = etree.SubElement(xml, 'video')
        etree.SubElement(video, 'default', attrib={'pathversion': "1"})

    video = xml.find('video')
    count = 2

    for source in xml.findall('.//path'):
        if source.text == 'smb://':
            count -= 1

        if count == 0:
            break
    else:
        for i in range(0, count):
            source = etree.SubElement(video, 'source')
            etree.SubElement(source, 'name').text = "Emby"
            etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "smb://"
            etree.SubElement(source, 'allowsharing').text = "true"

    for source in xml.findall('.//path'):
        if source.text == 'http://kodi.emby.media':
            break
    else:
        source = etree.SubElement(video, 'source')
        etree.SubElement(source, 'name').text = "kodi.emby.media"
        etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.emby.media"
        etree.SubElement(source, 'allowsharing').text = "true"

    indent(xml)
    write_xml(etree.tostring(xml, 'UTF-8'), file)

def tvtunes_nfo(path, urls):

    ''' Create tvtunes.nfo
    '''
    try:
        xml = etree.parse(path).getroot()
    except Exception:
        xml = etree.Element('tvtunes')

    for elem in xml.getiterator('tvtunes'):
        for file in list(elem):
            elem.remove(file)

    for url in urls:
        etree.SubElement(xml, 'file').text = url

    indent(xml)
    write_xml(etree.tostring(xml, 'UTF-8'), path)




"""
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
import urllib
import unicodedata
import xml.etree.ElementTree as etree
from datetime import datetime
from uuid import uuid4


import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################




#################################################################################################
# Utility methods

def getScreensaver():
    # Get the current screensaver value
    result = JSONRPC('Settings.getSettingValue').execute({'setting': "screensaver.mode"})
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
            topath = "smb://%s:%s@%s/" % (user, password, server)
            path.find('.//to').text = topath.replace("\\", ";")
            break
    else:
        # Server not found, add it.
        path = etree.SubElement(root, 'path')
        etree.SubElement(path, 'from', attrib={'pathversion': "1"}).text = "smb://%s/" % server
        topath = "smb://%s:%s@%s/" % (user, password, server)
        etree.SubElement(path, 'to', attrib={'pathversion': "1"}).text = topath.replace("\\", ";")
        # Force Kodi to see the credentials without restarting
        xbmcvfs.exists(topath)

    # Add credentials
    settings('networkCreds', value=server)
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

def verify_advancedsettings():
    # Track the existance of <cleanonupdate>true</cleanonupdate>
    # incompatible with plugin paths
    log.info("verifying advanced settings")
    if settings('useDirectPaths') != "0": return

    path = xbmc.translatePath("special://userdata/").decode('utf-8')
    xmlpath = "%sadvancedsettings.xml" % path

    try:
        xmlparse = etree.parse(xmlpath)
    except: # Document is blank or missing
        return
    else:
        root = xmlparse.getroot()

    video = root.find('videolibrary')
    if video is not None:
        cleanonupdate = video.find('cleanonupdate')
        if cleanonupdate is not None and cleanonupdate.text == "true":
            log.warn("cleanonupdate disabled")
            video.remove(cleanonupdate)
            
            try:
                indent(root)
            except: pass
            etree.ElementTree(root).write(xmlpath)
            
            xbmcgui.Dialog().ok(heading=language(29999), line1=language(33097))
            xbmc.executebuiltin('RestartApp')
            return True
    return
"""
