# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os
import xml.etree.ElementTree as etree

from kodi_six import xbmc, xbmcvfs

from helper import LazyLogger

from . import translate, dialog, settings

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


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

    path = xbmcvfs.translatePath("special://profile/")
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
            tree.write(file)

            dialog("ok", "{jellyfin}", translate(33097))
            xbmc.executebuiltin('RestartApp')

            return True
