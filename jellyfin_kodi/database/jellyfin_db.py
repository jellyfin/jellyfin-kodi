# -*- coding: utf-8 -*-

#################################################################################################

import logging

import queries as QU

##################################################################################################

LOG = logging.getLogger("JELLYFIN." + __name__)

##################################################################################################


class JellyfinDatabase():

    def __init__(self, cursor):
        self.cursor = cursor

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

        try:
            self.cursor.execute(QU.get_view_name, (item_id,))

            return self.cursor.fetchone()[0]
        except Exception as error:
            LOG.exception(error)
            return

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

    def get_views(self, *args):
        self.cursor.execute(QU.get_views, args)

        return self.cursor.fetchall()

    def get_views_by_media(self, *args):
        self.cursor.execute(QU.get_views_by_media, args)

        return self.cursor.fetchall()

    def get_items_by_media(self, *args):
        self.cursor.execute(QU.get_items_by_media, args)

        return self.cursor.fetchall()

    def remove_media_by_parent_id(self, *args):
        self.cursor.execute(QU.delete_media_by_parent_id, args)
