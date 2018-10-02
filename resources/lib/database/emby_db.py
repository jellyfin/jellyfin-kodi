# -*- coding: utf-8 -*-

#################################################################################################

import logging

import queries as QU

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

##################################################################################################


class EmbyDatabase():


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





    """
    def get_version(self, version=None):

        if version is not None:
            self.embycursor.execute("DELETE FROM version")
            query = "INSERT INTO version(idVersion) VALUES (?)"
            self.embycursor.execute(query, (version,))
        else:
            query = "SELECT idVersion FROM version"
            self.embycursor.execute(query)
            try:
                version = self.embycursor.fetchone()[0]
            except TypeError:
                pass

        return version

    def getViews(self):

        views = []

        query = ' '.join((

            "SELECT view_id",
            "FROM view"
        ))
        self.embycursor.execute(query)
        rows = self.embycursor.fetchall()
        for row in rows:
            views.append(row[0])
        
        return views

    def getView_embyId(self, item_id):
        # Returns ancestors using embyId
        url = "{server}/emby/Items/%s/Ancestors?UserId={UserId}&format=json" % item_id

        try:
            view_list = self.download(url)
        except Exception as error:
            log.info("Error getting views: " + str(error))
            view_list = []

        if view_list is None:
            view_list = []

        for view in view_list:

            if view['Type'] == "CollectionFolder":
                # Found view
                view_id = view['Id']
                break
        else: # No view found
            return [None, None]

        # Compare to view table in emby database
        query = ' '.join((

            "SELECT view_name",
            "FROM view",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (view_id,))
        try:
            view_name = self.embycursor.fetchone()[0]
        except TypeError:
            view_name = None

        return [view_name, view_id]

    def getView_byId(self, viewid):


        query = ' '.join((

            "SELECT view_name, media_type, kodi_tagid",
            "FROM view",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (viewid,))
        view = self.embycursor.fetchone()
        
        return view

    def getView_byType(self, mediatype):

        views = []

        query = ' '.join((

            "SELECT view_id, view_name",
            "FROM view",
            "WHERE media_type = ?"
        ))
        self.embycursor.execute(query, (mediatype,))
        rows = self.embycursor.fetchall()
        for row in rows:
            views.append({

                'id': row[0],
                'name': row[1],
                'mediatype': mediatype
            })

        if mediatype in ('tvshows', 'movies'):
            query = ' '.join((
                "SELECT view_id, view_name",
                "FROM view",
                "WHERE media_type = ?"
            ))

            self.embycursor.execute(query, ("mixed",))
            rows = self.embycursor.fetchall()
            for row in rows:
                views.append({

                    'id': row[0],
                    'name': row[1],
                    'mediatype': "mixed"
                })

        return views

    def getView_byName(self, tagname):

        query = ' '.join((

            "SELECT view_id",
            "FROM view",
            "WHERE view_name = ?"
        ))
        self.embycursor.execute(query, (tagname,))
        try:
            view = self.embycursor.fetchone()[0]
        
        except TypeError:
            view = None

        return view

    def addView(self, embyid, name, mediatype, tagid, group_series):

        query = (
            '''
            INSERT INTO view(
                view_id, view_name, media_type, kodi_tagid, group_series)

            VALUES (?, ?, ?, ?, ?)
            '''
        )
        self.embycursor.execute(query, (embyid, name, mediatype, tagid, group_series))

    def get_view_grouped_series(self, view_id):

        query = ' '.join((

            "SELECT group_series",
            "FROM view",
            "WHERE view_id = ?"
        ))
        try:
            self.embycursor.execute(query, (view_id,))
            return self.embycursor.fetchone()
        except: return False

    def update_view_grouped_series(self, view_id, group_series):

        query = ' '.join((

            "UPDATE view",
            "SET group_series = ?",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (group_series, view_id))

    def updateView(self, name, tagid, mediafolderid):

        query = ' '.join((

            "UPDATE view",
            "SET view_name = ?, kodi_tagid = ?",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (name, tagid, mediafolderid))

    def removeView(self, viewid):

        query = ' '.join((

            "DELETE FROM view",
            "WHERE view_id = ?"
        ))
        self.embycursor.execute(query, (viewid,))

    def getItem_byId(self, embyid):

        query = ' '.join((

            "SELECT kodi_id, kodi_fileid, kodi_pathid, parent_id, media_type, emby_type",
            "FROM emby",
            "WHERE emby_id = ?"
        ))
        try:
            self.embycursor.execute(query, (embyid,))
            item = self.embycursor.fetchone()
            return item
        except: return None

    def getItem_byView(self, mediafolderid):

        query = ' '.join((

            "SELECT kodi_id",
            "FROM emby",
            "WHERE media_folder = ?"
        ))
        self.embycursor.execute(query, (mediafolderid,))
        return self.embycursor.fetchall()

    def get_item_by_view(self, view_id):

        query = ' '.join((

            "SELECT emby_id",
            "FROM emby",
            "WHERE media_folder = ?"
        ))
        self.embycursor.execute(query, (view_id,))
        return self.embycursor.fetchall()


    def get_checksum_by_view(self, media_type, view_id):

        query = ' '.join((

            "SELECT emby_id, checksum",
            "FROM emby",
            "WHERE emby_type = ?",
            "AND media_folder = ?"
        ))
        self.embycursor.execute(query, (media_type, view_id,))
        return self.embycursor.fetchall()

    def getMediaType_byId(self, embyid):

        query = ' '.join((

            "SELECT emby_type",
            "FROM emby",
            "WHERE emby_id = ?"
        ))
        self.embycursor.execute(query, (embyid,))
        try:
            itemtype = self.embycursor.fetchone()[0]
        
        except TypeError:
            itemtype = None

        return itemtype

    def sortby_mediaType(self, itemids, unsorted=True):

        sorted_items = {}
        
        for itemid in itemids:
            
            mediatype = self.getMediaType_byId(itemid)
            if mediatype:
                sorted_items.setdefault(mediatype, []).append(itemid)
            elif unsorted:
                sorted_items.setdefault('Unsorted', []).append(itemid)

        return sorted_items

    """
        