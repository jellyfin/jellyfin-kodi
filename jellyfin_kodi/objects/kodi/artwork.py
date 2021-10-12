# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

from ...helper import LazyLogger

from . import queries as QU

##################################################################################################

LOG = LazyLogger(__name__)

##################################################################################################


class Artwork(object):

    def __init__(self, cursor):

        self.cursor = cursor

    def update(self, image_url, kodi_id, media, image):

        ''' Update artwork in the video database.
            Delete current entry before updating with the new one.
        '''
        if not image_url or image == 'poster' and media in ('song', 'artist', 'album'):
            return

        try:
            self.cursor.execute(QU.get_art, (kodi_id, media, image,))
            url = self.cursor.fetchone()[0]
        except TypeError:

            LOG.debug("ADD to kodi_id %s art: %s", kodi_id, image_url)
            self.cursor.execute(QU.add_art, (kodi_id, media, image, image_url))
        else:
            if url != image_url:
                LOG.info("UPDATE to kodi_id %s art: %s", kodi_id, image_url)
                self.cursor.execute(QU.update_art, (image_url, kodi_id, media, image))

    def add(self, artwork, *args):

        ''' Add all artworks.
        '''
        KODI = {
            'Primary': ['thumb', 'poster'],
            'Banner': "banner",
            'Logo': "clearlogo",
            'Art': "clearart",
            'Thumb': "landscape",
            'Disc': "discart",
            'Backdrop': "fanart"
        }

        for art in KODI:

            if art == 'Backdrop':
                self.cursor.execute(QU.get_backdrops, args + ("fanart%",))

                if len(self.cursor.fetchall()) > len(artwork['Backdrop']):
                    self.cursor.execute(QU.delete_backdrops, args + ("fanart_",))

                for index, backdrop in enumerate(artwork['Backdrop']):

                    if index:
                        self.update(*(backdrop,) + args + ("%s%s" % ("fanart", index),))
                    else:
                        self.update(*(backdrop,) + args + ("fanart",))

            elif art == 'Primary':
                for kodi_image in KODI['Primary']:
                    self.update(*(artwork['Primary'],) + args + (kodi_image,))

            elif artwork.get(art):
                self.update(*(artwork[art],) + args + (KODI[art],))

    def delete(self, *args):

        ''' Delete artwork from kodi database
        '''
        self.cursor.execute(QU.delete_art, args)
