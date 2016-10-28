# -*- coding: utf-8 -*-

##################################################################################################

import logging

import xbmc

import api
import artwork

#################################################################################################

log = logging.getLogger("EMBY."+__name__)

#################################################################################################

class Kodidb_Functions(object):

    kodiversion = int(xbmc.getInfoLabel("System.BuildVersion")[:2])
    

    def __init__(self, cursor):

        self.cursor = cursor
        self.artwork = artwork.Artwork()

    def createTag(self, name):
        # This will create and return the tag_id
        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            query = ' '.join((

                "SELECT tag_id",
                "FROM tag",
                "WHERE name = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                tag_id = self.cursor.fetchone()[0]

            except TypeError:
                self.cursor.execute("select coalesce(max(tag_id),0) from tag")
                tag_id = self.cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(tag_id, name) values(?, ?)"
                self.cursor.execute(query, (tag_id, name))
                log.debug("Create tag_id: %s name: %s", tag_id, name)
        else:
            # Kodi Helix
            query = ' '.join((

                "SELECT idTag",
                "FROM tag",
                "WHERE strTag = ?",
                "COLLATE NOCASE"
            ))
            self.cursor.execute(query, (name,))
            try:
                tag_id = self.cursor.fetchone()[0]

            except TypeError:
                self.cursor.execute("select coalesce(max(idTag),0) from tag")
                tag_id = self.cursor.fetchone()[0] + 1

                query = "INSERT INTO tag(idTag, strTag) values(?, ?)"
                self.cursor.execute(query, (tag_id, name))
                log.debug("Create idTag: %s name: %s", tag_id, name)

        return tag_id

    def updateTag(self, oldtag, newtag, kodiid, mediatype):
        # TODO: Move to video nodes eventually
        log.debug("Updating: %s with %s for %s: %s", oldtag, newtag, mediatype, kodiid)

        if self.kodiversion in (15, 16, 17):
            # Kodi Isengard, Jarvis, Krypton
            try:
                query = ' '.join((

                    "UPDATE tag_link",
                    "SET tag_id = ?",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM tag_link",
                    "WHERE media_id = ?",
                    "AND media_type = ?",
                    "AND tag_id = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, oldtag,))
        else:
            # Kodi Helix
            try:
                query = ' '.join((

                    "UPDATE taglinks",
                    "SET idTag = ?",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (newtag, kodiid, mediatype, oldtag,))
            except Exception:
                # The new tag we are going to apply already exists for this item
                # delete current tag instead
                query = ' '.join((

                    "DELETE FROM taglinks",
                    "WHERE idMedia = ?",
                    "AND media_type = ?",
                    "AND idTag = ?"
                ))
                self.cursor.execute(query, (kodiid, mediatype, oldtag,))
