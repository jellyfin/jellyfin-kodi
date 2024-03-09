# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os
import xml.etree.ElementTree as etree

from kodi_six import xbmc, xbmcvfs

from .utils import translate_path
from . import translate, dialog, settings, LazyLogger

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

    path = translate_path("special://profile/")
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

def verify_kodi_defaults():
    ''' Make sure we have the kodi default folder in place.
    '''

    source_base_path = translate_path("special://xbmc/system/library/video")
    dest_base_path = translate_path("special://profile/library/video")

    if not os.path.exists(source_base_path):
        LOG.error("XMLs source path `%s` not found.", source_base_path)
        return

    # Make sure the files exist in the local profile.
    for source_path, dirs, files in os.walk(source_base_path):
        relative_path = os.path.relpath(source_path, source_base_path)
        dest_path = os.path.join(dest_base_path, relative_path)

        if not os.path.exists(dest_path):
            os.mkdir(os.path.normpath(dest_path))

        for file_name in files:
            dest_file = os.path.join(dest_path, file_name)
            copy = False

            if not os.path.exists(dest_file):
                copy = True
            elif os.path.splitext(file_name)[1].lower() == '.xml':
                try:
                    etree.parse(dest_file)
                except etree.ParseError:
                    LOG.warning("Unable to parse `{}`, recovering from default.".format(dest_file))
                    copy = True

            if copy:
                source_file = os.path.join(source_path, file_name)
                LOG.debug("Copying `{}` -> `{}`".format(source_file, dest_file))
                xbmcvfs.copy(source_file, dest_file)

    # This code seems to enforce a fixed ordering.
    # Is it really desirable to force this on users?
    # The default (system wide) order is [10, 20, 30] in Kodi 19.
    for index, node in enumerate(['movies', 'tvshows', 'musicvideos']):
        file_name = os.path.join(dest_base_path, node, "index.xml")

        if xbmcvfs.exists(file_name):
            try:
                with xbmcvfs.File(file_name) as f:
                    b = f.read()
                    tree = etree.ElementTree(etree.fromstring(b))
            except etree.ParseError:
                LOG.error("Unable to parse `{}`".format(file_name))
                LOG.exception("We ensured the file was OK above, something is wrong!")
                tree = None

            if tree is not None:
                tree.getroot().set('order', str(17 + index))
                with xbmcvfs.File(file_name, 'w') as f:
                    f.write(etree.tostring(tree.getroot()))

    playlist_path = translate_path("special://profile/playlists/video")

    if not xbmcvfs.exists(playlist_path):
        xbmcvfs.mkdirs(playlist_path)
