# -*- coding: utf-8 -*-

##################################################################################################

import logging

from kodi import Kodi
import queries as QU

##################################################################################################

LOG = logging.getLogger("EMBY."+__name__)

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

    def create_entry_set(self):
        self.cursor.execute(QU.create_set)

        return self.cursor.fetchone()[0] + 1

    def create_entry_country(self):
        self.cursor.execute(QU.create_country)

        return self.cursor.fetchone()[0] + 1

    def get(self, *args):

        try:
            self.cursor.execute(QU.get_movie, args)
            return self.cursor.fetchone()[0]
        except TypeError:
            return

    def add(self, *args):
        self.cursor.execute(QU.add_movie, args)

    def update(self, *args):
        self.cursor.execute(QU.update_movie, args)

    def delete(self, kodi_id, file_id):

        self.cursor.execute(QU.delete_movie, (kodi_id,))
        self.cursor.execute(QU.delete_file, (file_id,))

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

        country_id = self.create_entry_country()
        self.cursor.execute(QU.add_country, (country_id,) + args)

        return country_id

    def get_country(self, *args):

        try:
            self.cursor.execute(QU.get_country, args)

            return self.cursor.fetchone()[0]
        except TypeError:
            return self.add_country(*args)

    def add_boxset(self, *args):

        set_id = self.create_entry_set()
        self.cursor.execute(QU.add_set, (set_id,) + args)

        return set_id

    def update_boxset(self, *args):
        self.cursor.execute(QU.update_set, args)

    def set_boxset(self, *args):
        self.cursor.execute(QU.update_movie_set, args)

    def remove_from_boxset(self, *args):
        self.cursor.execute(QU.delete_movie_set, args)

    def delete_boxset(self, *args):
        self.cursor.execute(QU.delete_set, args)
