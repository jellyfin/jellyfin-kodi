# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os
import xml.etree.ElementTree as etree

from kodi_six import xbmc

from helper import LazyLogger

from . import translate, dialog, settings

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


def sources():

    ''' Create master lock compatible sources.
        Also add the kodi.jellyfin.media source.
    '''
    path = xbmc.translatePath("special://profile/")
    file = os.path.join(path, 'sources.xml')

    try:
        xml = etree.parse(file).getroot()
    except Exception:

        xml = etree.Element('sources')
        video = etree.SubElement(xml, 'video')
        files = etree.SubElement(xml, 'files')
        etree.SubElement(video, 'default', attrib={'pathversion': "1"})
        etree.SubElement(files, 'default', attrib={'pathversion': "1"})

    video = xml.find('video')
    count_http = 1
    count_smb = 1

    for source in xml.findall('.//path'):
        if source.text == 'smb://':
            count_smb -= 1
        elif source.text == 'http://':
            count_http -= 1

        if not count_http and not count_smb:
            break
    else:
        for protocol in ('smb://', 'http://'):
            if (protocol == 'smb://' and count_smb > 0) or (protocol == 'http://' and count_http > 0):

                source = etree.SubElement(video, 'source')
                etree.SubElement(source, 'name').text = "Jellyfin"
                etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = protocol
                etree.SubElement(source, 'allowsharing').text = "true"

    try:
        files = xml.find('files')

        if files is None:
            files = etree.SubElement(xml, 'files')

        for source in xml.findall('.//path'):
            # TODO get a repo url
            if source.text == 'http://kodi.jellyfin.media':
                break
        else:
            source = etree.SubElement(files, 'source')
            etree.SubElement(source, 'name').text = "kodi.jellyfin.media"
            etree.SubElement(source, 'path', attrib={'pathversion': "1"}).text = "http://kodi.jellyfin.media"
            etree.SubElement(source, 'allowsharing').text = "true"
    except Exception as error:
        LOG.exception(error)

    tree = etree.ElementTree(xml)
    tree.write(file)


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

    tree = etree.ElementTree(xml)
    tree.write(path)


def advanced_settings():

    ''' Track the existence of <cleanonupdate>true</cleanonupdate>
        It is incompatible with plugin paths.
    '''
    if settings('useDirectPaths') != "0":
        return

    path = xbmc.translatePath("special://profile/")
    file = os.path.join(path, 'advancedsettings.xml')

    try:
        xml = etree.parse(file).getroot()
    except Exception:
        return

    video = xml.find('videolibrary')

    if video is not None:
        cleanonupdate = video.find('cleanonupdate')

        if cleanonupdate is not None and cleanonupdate.text == "true":

            LOG.warning("cleanonupdate disabled")
            video.remove(cleanonupdate)

            tree = etree.ElementTree(xml)
            tree.write(path)

            dialog("ok", "{jellyfin}", translate(33097))
            xbmc.executebuiltin('RestartApp')

            return True
