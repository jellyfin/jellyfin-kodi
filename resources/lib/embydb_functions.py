# -*- coding: utf-8 -*-

#################################################################################################

import utils
import clientinfo

#################################################################################################


class Embydb_Functions():


    def __init__(self, embycursor):

        self.embycursor = embycursor

        self.clientInfo = clientinfo.ClientInfo()
        self.addonName = self.clientInfo.getAddonName()

    def logMsg(self, msg, lvl=1):

        className = self.__class__.__name__
        utils.logMsg("%s %s" % (self.addonName, className), msg, lvl)

    def getViews(self):

        embycursor = self.embycursor
        views = []

        query = ' '.join((

            "SELECT view_id",
            "FROM view"
        ))
        embycursor.execute(query)
        rows = embycursor.fetchall()
        for row in rows:
            views.append(row[0])
        
        return views

    def getView_byId(self, viewid):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT view_name, media_type, kodi_tagid",
            "FROM view",
            "WHERE view_id = ?"
        ))
        embycursor.execute(query, (viewid,))
        view = embycursor.fetchone()
        
        return view

    def getView_byType(self, mediatype):

        embycursor = self.embycursor
        views = []

        query = ' '.join((

            "SELECT view_id, view_name",
            "FROM view",
            "WHERE media_type = ?"
        ))
        embycursor.execute(query, (mediatype,))
        rows = embycursor.fetchall()
        for row in rows:
            views.append({

                'id': row[0],
                'name': row[1]
            })

        return views

    def getView_byName(self, tagname):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT view_id",
            "FROM view",
            "WHERE view_name = ?"
        ))
        embycursor.execute(query, (tagname,))
        try:
            view = embycursor.fetchone()[0]
        
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

    def getItem_byId(self, embyid):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT kodi_id, kodi_fileid, kodi_pathid, parent_id, media_type, emby_type",
            "FROM emby",
            "WHERE emby_id = ?"
        ))
        try:
            embycursor.execute(query, (embyid,))
            item = embycursor.fetchone()
            return item
        except: return None

    def getItem_byView(self, mediafolderid):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT kodi_id",
            "FROM emby",
            "WHERE media_folder = ?"
        ))
        embycursor.execute(query, (mediafolderid,))
        items = embycursor.fetchall()

        return items

    def getItem_byKodiId(self, kodiid, mediatype):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT emby_id, parent_id",
            "FROM emby",
            "WHERE kodi_id = ?",
            "AND media_type = ?"
        ))
        embycursor.execute(query, (kodiid, mediatype,))
        item = embycursor.fetchone()

        return item

    def getItem_byParentId(self, parentid, mediatype):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT emby_id, kodi_id, kodi_fileid",
            "FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        embycursor.execute(query, (parentid, mediatype,))
        items = embycursor.fetchall()

        return items

    def getItemId_byParentId(self, parentid, mediatype):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT emby_id, kodi_id",
            "FROM emby",
            "WHERE parent_id = ?",
            "AND media_type = ?"
        ))
        embycursor.execute(query, (parentid, mediatype,))
        items = embycursor.fetchall()

        return items

    def getChecksum(self, mediatype):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT emby_id, checksum",
            "FROM emby",
            "WHERE emby_type = ?"
        ))
        embycursor.execute(query, (mediatype,))
        items = embycursor.fetchall()

        return items

    def getMediaType_byId(self, embyid):

        embycursor = self.embycursor

        query = ' '.join((

            "SELECT emby_type",
            "FROM emby",
            "WHERE emby_id = ?"
        ))
        embycursor.execute(query, (embyid,))
        try:
            itemtype = embycursor.fetchone()[0]
        
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
        