from __future__ import division, absolute_import, print_function, unicode_literals

from .movies import Movies
from .musicvideos import MusicVideos
from .tvshows import TVShows
from .music import Music
from .obj import Objects
from .actions import Actions
from .actions import PlaylistWorker
from .actions import on_play, on_update, special_listener
from . import utils

Objects().mapping()
