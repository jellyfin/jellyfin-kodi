# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

import os
import re
from sqlite3 import DatabaseError

##################################################################################################

from ...helper import LazyLogger, settings

from .kodi import Kodi
from . import queries as QU

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class Movies(Kodi):

    itemtype: int

    def __init__(self, cursor):

        self.cursor = cursor
        Kodi.__init__(self)
        try:
            self.cursor.execute(QU.get_videoversion_itemtype, [40400])
            self.itemtype = self.cursor.fetchone()[0]
        except (IndexError, DatabaseError, TypeError) as e:
            LOG.warning("Unable to fetch videoversion itemtype: %s", e)
            self.itemtype = 0

    def create_entry_unique_id(self):
        self.cursor.execute(QU.create_unique_id)

        return self.cursor.fetchone()[0] + 1

    def create_entry_rating(self):
        self.cursor.execute(QU.create_rating)

        return self.cursor.fetchone()[0] + 1

    def create_entry(self):
        self.cursor.execute(QU.create_movie)

        return self.cursor.fetchone()[0] + 1

    def get(self, *args):

        try:
            self.cursor.execute(QU.get_movie, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def add(self, *args):
        self.cursor.execute(QU.add_movie, args)

    def add_videoversion(self, *args):
        self.cursor.execute(QU.check_video_version)
        if self.cursor.fetchone()[0] == 1:
            self.cursor.execute(QU.add_video_version, args)

    def check_videoversion(self, *args):
        self.cursor.execute(QU.count_video_version, args)
        return self.cursor.fetchone()[0]

    def get_or_create_videoversiontype(self, name, filepath, extra=False):
        """Retrieve or create a video version type based on the Jellyfin version name or filename."""
        # If versions are disabled, always return the standard edition
        if settings("useVersions") != "true":
            return 40400

        # Change itemtype for extras. If other types added in the future, need to adjust.
        itemtype = self.itemtype + 1 if extra else self.itemtype

        # Get the filename without extension
        filename = os.path.splitext(os.path.basename(filepath))[0]

        # Remove Jellyfin-added suffixes--may need to add others
        test_name = re.sub(r"/(3D|DVD|Bluray)$", "", name)

        # If the Jellyfin version name matches the filename completely, a good version name
        # wasn't created automatically, so extract it, or set to Standard Edition
        if not extra and test_name == filename:
            # Check for ' - XXXX' at end of the name to use for version name
            match = re.search(r" - (.+)$", name)
            if match:
                name = match.group(1).strip()
            else:
                name = None

        # Set Standard Edition for empty names or DVD/Bluray folders
        if not name or filename.lower() in ("index", "video_ts"):
            return 40400

        # Remove */3D suffixes that Jellyfin adds (ie '.mvc/3D') as long as 3D in the name already
        if '3D' in name[:-2]:
            name = re.sub(r'\.(\w{3,4})/3D$', lambda m: ' ' + m.group(1).upper(), name)

        # Check if this version type already exists and return it
        self.cursor.execute(QU.get_video_version_type, (name, itemtype,))
        row = self.cursor.fetchone()
        if row:
            return row[0]

        # Create a new version type and return the id
        self.cursor.execute(QU.add_video_version_type, (name, 1, itemtype))
        return self.cursor.lastrowid

    def update(self, *args):
        self.cursor.execute(QU.update_movie, args)

    def delete(self, kodi_id, file_id):

        self.cursor.execute(QU.delete_movie, (kodi_id,))
        self.cursor.execute(QU.delete_file, (file_id,))
        self.cursor.execute(QU.check_video_version)
        if self.cursor.fetchone()[0] == 1:
            # Cleanup version types
            versions = self.get_videoversions(kodi_id)
            type_id = next((row[0] for row in versions if row[1] == file_id), None)
            self.cursor.execute(QU.delete_video_version, (file_id,))
            self.delete_unused_version_type(type_id)

            # Remove all other versions; Jellyfin creates a new base entry if other versions are left
            for row in versions:
                self.delete_video_version(row[1], row[0])

    def delete_video_version(self, file_id, type_id):
        """Remove video version file and cleanup version type if unused."""
        self.cursor.execute(QU.delete_file, (file_id,))
        self.cursor.execute(QU.delete_video_version, (file_id,))
        self.delete_unused_version_type(type_id)

    def delete_unused_version_type(self, type_id):
        """Delete video version type if no references exist, and its not a builtin type."""
        if type_id and type_id > 40800:
            self.cursor.execute(QU.count_video_version_type, (type_id,))
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute(QU.delete_video_version_type, (type_id,))

    def get_videoversions(self, kodi_id):
        self.cursor.execute(QU.get_video_versions, (kodi_id,))
        return [row for row in self.cursor.fetchall()]

    def get_rating_id(self, *args):

        try:
            self.cursor.execute(QU.get_rating, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return None

    def add_ratings(self, *args):
        """Add ratings, rating type and votes."""
        self.cursor.execute(QU.add_rating, args)

    def update_ratings(self, *args):
        """Update rating by rating_id."""
        self.cursor.execute(QU.update_rating, args)

    def get_unique_id(self, *args):

        try:
            self.cursor.execute(QU.get_unique_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def add_unique_id(self, *args):
        """Add the provider id, imdb, tvdb."""
        self.cursor.execute(QU.add_unique_id, args)

    def update_unique_id(self, *args):
        """Update the provider id, imdb, tvdb."""
        self.cursor.execute(QU.update_unique_id, args)

    def add_countries(self, countries, *args):

        for country in countries:
            self.cursor.execute(QU.update_country, (self.get_country(country),) + args)

    def add_country(self, *args):
        self.cursor.execute(QU.add_country, args)
        return self.cursor.lastrowid

    def get_country(self, *args):

        try:
            self.cursor.execute(QU.get_country, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return self.add_country(*args)

    def add_boxset(self, *args):
        self.cursor.execute(QU.add_set, args)
        return self.cursor.lastrowid

    def update_boxset(self, *args):
        self.cursor.execute(QU.update_set, args)

    def set_boxset(self, *args):
        self.cursor.execute(QU.update_movie_set, args)

    def remove_from_boxset(self, *args):
        self.cursor.execute(QU.delete_movie_set, args)

    def delete_boxset(self, *args):
        self.cursor.execute(QU.delete_set, args)

    def migrations(self):
        """
        Used to trigger required database migrations for new versions
        """
        self.cursor.execute(QU.get_version)
        version_id = self.cursor.fetchone()[0]
        changes = False

        # Will run every time Kodi starts, but will be fast enough on
        # subsequent runs to not be a meaningful delay
        if version_id >= 131:
            changes = self.omega_migration()

        return changes

    def omega_migration(self):
        """
        Adds a video version for all existing movies

        For Omega: video_version_id = 0
        For Piers: video_version_id = 1

        Migration from Nexus to Omega adds video version with id 0
        Migration from Nexus to Peirs adds video version with id 1
        Migration from Omega to Piers this does nothing and is handled by kodi itself
        """
        LOG.info("Starting migration for Omega database changes")
        # Tracks if this migration made any changes
        changes = False
        self.cursor.execute(QU.get_missing_versions)

        # Sets all existing movies without a version to standard version
        for entry in self.cursor.fetchall():
            self.add_videoversion(entry[0], entry[1], "movie", self.itemtype, 40400)
            changes = True

        LOG.info("Omega database migration is complete")
        return changes
