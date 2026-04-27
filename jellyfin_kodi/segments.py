from __future__ import division, absolute_import, print_function, unicode_literals

import threading
import xbmc
from .helper import LazyLogger, settings

LOG = LazyLogger(__name__)


class SegmentChecker(threading.Thread):
    stop_thread = False

    def __init__(self, player):
        self.player = player

        threading.Thread.__init__(self)

    def stop(self):
        self.stop_thread = True

    def run(self):
        LOG.info("--->[ segment checker ]")

        while not self.stop_thread:
            if self.player.isPlaying() and settings("mediaSegmentsEnabled.bool"):
                try:
                    current_file = self.player.get_playing_file()
                    item = self.player.get_file_info(current_file)
                    current_pos = int(self.player.getTime())
                    self.player.check_skip_segments(item, current_pos)

                except Exception as e:
                    LOG.exception("Error in segment checker loop: %s", e)

            xbmc.sleep(1000)

        LOG.info("---<[ segment checker ]")
