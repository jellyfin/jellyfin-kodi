# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals
#################################################################################################

from . import queries as QU
from ..helper import LazyLogger

from ..jellyfin.utils import sqlite_namedtuple_factory

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class JellyfinDatabase():

    def __init__(self, cursor):
        self.cursor = cursor
        cursor.row_factory = sqlite_namedtuple_factory

    def get_item_by_id(self, *args):
        self.cursor.execute(QU.get_item, args)

        return self.cursor.fetchone()

    def add_reference(self, *args):
        self.cursor.execute(QU.add_reference, args)

    def update_reference(self, *args):
        self.cursor.execute(QU.update_reference, args)

    def update_parent_id(self, *args):

        ''' Parent_id is the parent Kodi id.
        '''
        self.cursor.execute(QU.update_parent, args)

    def get_item_id_by_parent_id(self, *args):
        self.cursor.execute(QU.get_item_id_by_parent, args)

        return self.cursor.fetchall()

    def get_item_by_parent_id(self, *args):
        self.cursor.execute(QU.get_item_by_parent, args)

        return self.cursor.fetchall()

    def get_item_by_media_folder(self, *args):
        self.cursor.execute(QU.get_item_by_media_folder, args)

        return self.cursor.fetchall()

    def get_item_by_wild_id(self, item_id):
        self.cursor.execute(QU.get_item_by_wild, (item_id + "%",))

        return self.cursor.fetchall()

    def get_checksum(self, *args):
        self.cursor.execute(QU.get_checksum, args)

        return self.cursor.fetchall()

    def get_item_by_kodi_id(self, *args):

        try:
            self.cursor.execute(QU.get_item_by_kodi, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_episode_kodi_parent_path_id(self, *args):

        try:
            self.cursor.execute(QU.get_episode_kodi_parent_path_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_full_item_by_kodi_id(self, *args):

        try:
            self.cursor.execute(QU.get_item_by_kodi, args)

            return self.cursor.fetchone()
        except TypeError:
            return

    def get_media_by_id(self, *args):

        try:
            self.cursor.execute(QU.get_media_by_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def get_media_by_parent_id(self, *args):
        self.cursor.execute(QU.get_media_by_parent_id, args)

        return self.cursor.fetchall()

    def remove_item(self, *args):
        self.cursor.execute(QU.delete_item, args)

    def remove_items_by_parent_id(self, *args):
        self.cursor.execute(QU.delete_item_by_parent, args)

    def remove_item_by_kodi_id(self, *args):
        self.cursor.execute(QU.delete_item_by_kodi, args)

    def remove_wild_item(self, item_id):
        self.cursor.execute(QU.delete_item_by_wild, (item_id + "%",))

    def get_view_name(self, item_id):

        self.cursor.execute(QU.get_view_name, (item_id,))

        return self.cursor.fetchone()[0]

    def get_view(self, *args):

        try:
            self.cursor.execute(QU.get_view, args)

            return self.cursor.fetchone()
        except TypeError:
            return

    def add_view(self, *args):
        self.cursor.execute(QU.add_view, args)

    def remove_view(self, *args):
        self.cursor.execute(QU.delete_view, args)

    def get_views(self):
        self.cursor.execute(QU.get_views)

        return self.cursor.fetchall()

    def get_views_by_media(self, *args):
        self.cursor.execute(QU.get_views_by_media, args)

        return self.cursor.fetchall()

    def get_items_by_media(self, *args):
        self.cursor.execute(QU.get_items_by_media, args)

        return self.cursor.fetchall()

    def remove_media_by_parent_id(self, *args):
        self.cursor.execute(QU.delete_media_by_parent_id, args)

    def get_version(self):
        self.cursor.execute(QU.get_version)

        return self.cursor.fetchone()

    def add_version(self, *args):
        '''
        We only ever want one value here, so erase the existing contents first
        '''
        self.cursor.execute(QU.delete_version)
        self.cursor.execute(QU.add_version, args)
