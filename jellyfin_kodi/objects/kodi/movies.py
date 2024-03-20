# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

##################################################################################################

from ...helper import LazyLogger

from .kodi import Kodi
from . import queries as QU

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class Movies(Kodi):

    def __init__(self, cursor):

        self.cursor = cursor
        Kodi.__init__(self)

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

    def update(self, *args):
        self.cursor.execute(QU.update_movie, args)

    def delete(self, kodi_id, file_id):

        self.cursor.execute(QU.delete_movie, (kodi_id,))
        self.cursor.execute(QU.delete_file, (file_id,))
        self.cursor.execute(QU.check_video_version)
        if self.cursor.fetchone()[0] == 1:
            self.cursor.execute(QU.delete_video_version, (file_id,))

    def get_rating_id(self, *args):

        try:
            self.cursor.execute(QU.get_rating, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return None

    def add_ratings(self, *args):

        ''' Add ratings, rating type and votes.
        '''
        self.cursor.execute(QU.add_rating, args)

    def update_ratings(self, *args):

        ''' Update rating by rating_id.
        '''
        self.cursor.execute(QU.update_rating, args)

    def get_unique_id(self, *args):

        try:
            self.cursor.execute(QU.get_unique_id, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def add_unique_id(self, *args):

        ''' Add the provider id, imdb, tvdb.
        '''
        self.cursor.execute(QU.add_unique_id, args)

    def update_unique_id(self, *args):

        ''' Update the provider id, imdb, tvdb.
        '''
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
        '''
        Used to trigger required database migrations for new versions
        '''
        self.cursor.execute(QU.get_version)
        version_id = self.cursor.fetchone()[0]
        changes = False

        # Will run every time Kodi starts, but will be fast enough on
        # subsequent runs to not be a meaningful delay
        if version_id >= 131:
            changes = self.omega_migration()

        return changes

    def omega_migration(self):
        '''
        Adds a video version for all existing movies
        '''
        LOG.info('Starting migration for Omega database changes')
        # Tracks if this migration made any changes
        changes = False
        self.cursor.execute(QU.get_missing_versions)

        # Sets all existing movies without a version to standard version
        for entry in self.cursor.fetchall():
            self.add_videoversion(entry[0], entry[1], "movie", "0", 40400)
            changes = True

        LOG.info('Omega database migration is complete')
        return changes
