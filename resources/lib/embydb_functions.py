# -*- coding: utf-8 -*-

#################################################################################################

import logging
from sqlite3 import OperationalError

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class Embydb_Functions():


    def __init__(self, embycursor):

        self.embycursor = embycursor


    def get_version(self, version=None):

        if version is not None:
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
                'name': row[1]
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

    def addView(self, embyid, name, mediatype, tagid):

        query = (
            '''
            INSERT INTO view(
                view_id, view_name, media_type, kodi_tagid)

            VALUES (?, ?, ?, ?)
            '''
        )
        self.embycursor.execute(query, (embyid, name, mediatype, tagid))

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

    def getItem_byWildId(self, embyid):

        query = ' '.join((

            "SELECT kodi_id, media_type",
            "FROM emby",
            "WHERE emby_id LIKE ?"
        ))
        self.embycursor.execute(query, (embyid+"%",))
        return self.embycursor.fetchall()

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

    def getItem_byKodiId(self, kodiid, mediatype):

        query = ' '.join((

            "SELECT emby_id, parent_id, media_folder",
            "FROM emby",
            "WHERE kodi_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (kodiid, mediatype,))
        return self.embycursor.fetchone()

    def getItem_byParentId(self, parentid, mediatype):

        query = ' '.join((

            "SELECT emby_id, kodi_id, kodi_fileid",
            "FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (parentid, mediatype,))
        return self.embycursor.fetchall()

    def getItemId_byParentId(self, parentid, mediatype):

        query = ' '.join((

            "SELECT emby_id, kodi_id",
            "FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (parentid, mediatype,))
        return self.embycursor.fetchall()

    def get_checksum(self, mediatype):

        query = ' '.join((

            "SELECT emby_id, checksum",
            "FROM emby",
            "WHERE emby_type = ?"
        ))
        self.embycursor.execute(query, (mediatype,))
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

    def addReference(self, embyid, kodiid, embytype, mediatype, fileid=None, pathid=None,
                        parentid=None, checksum=None, mediafolderid=None):
        query = (
            '''
            INSERT OR REPLACE INTO emby(
                emby_id, kodi_id, kodi_fileid, kodi_pathid, emby_type, media_type, parent_id,
                checksum, media_folder)

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            '''
        )
        self.embycursor.execute(query, (embyid, kodiid, fileid, pathid, embytype, mediatype,
            parentid, checksum, mediafolderid))

    def updateReference(self, embyid, checksum):

        query = "UPDATE emby SET checksum = ? WHERE emby_id = ?"
        self.embycursor.execute(query, (checksum, embyid))

    def updateParentId(self, embyid, parent_kodiid):
        
        query = "UPDATE emby SET parent_id = ? WHERE emby_id = ?"
        self.embycursor.execute(query, (parent_kodiid, embyid))

    def removeItems_byParentId(self, parent_kodiid, mediatype):

        query = ' '.join((

            "DELETE FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (parent_kodiid, mediatype,))

    def removeItem_byKodiId(self, kodiid, mediatype):

        query = ' '.join((

            "DELETE FROM emby",
            "WHERE kodi_id = ?",
            "AND media_type = ?"
        ))
        self.embycursor.execute(query, (kodiid, mediatype,))

    def removeItem(self, embyid):

        query = "DELETE FROM emby WHERE emby_id = ?"
        self.embycursor.execute(query, (embyid,))

    def removeWildItem(self, embyid):

        query = "DELETE FROM emby WHERE emby_id LIKE ?"
        self.embycursor.execute(query, (embyid+"%",))
        