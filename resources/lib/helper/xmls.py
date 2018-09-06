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
