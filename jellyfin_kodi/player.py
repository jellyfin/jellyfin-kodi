# -*- coding: utf-8 -*-
from __future__ import division, absolute_import, print_function, unicode_literals

#################################################################################################

import os

import xbmc
import xbmcvfs

from .objects.obj import Objects
from .helper import translate, api, window, settings, dialog, event, JSONRPC
from .jellyfin import Jellyfin
from .helper import LazyLogger
from .helper.utils import translate_path

#################################################################################################

LOG = LazyLogger(__name__)

#################################################################################################


class Player(xbmc.Player):

    played = {}
    up_next = False
    skip_segments = {}
    skip_prompted = set()
    skip_dialog = None

    def __init__(self):
        xbmc.Player.__init__(self)

    def get_playing_file(self):
        try:
            return self.getPlayingFile()
        except Exception as error:
            LOG.exception(error)

    def get_file_info(self, file):
        try:
            return self.played[file]
        except Exception as error:
            LOG.exception(error)

    def is_playing_file(self, file):
        return file in self.played

    def onPlayBackStarted(self):
        """We may need to wait for info to be set in kodi monitor.
        Accounts for scenario where Kodi starts playback and exits immediately.
        First, ensure previous playback terminated correctly in Jellyfin.
        """
        self.stop_playback()
        self.up_next = False
        count = 0
        monitor = xbmc.Monitor()

        try:
            current_file = self.getPlayingFile()
        except Exception:

            while count < 5:
                try:
                    current_file = self.getPlayingFile()
                    count = 0
                    break
                except Exception:
                    count += 1

                if monitor.waitForAbort(1):
                    return
            else:
                LOG.info("Cancel playback report")

                return

        items = window("jellyfin_play.json")
        item = None

        while not items:

            if monitor.waitForAbort(2):
                return

            items = window("jellyfin_play.json")
            count += 1

            if count == 20:
                LOG.info("Could not find jellyfin prop...")

                return

        for item in items:
            if item["Path"] == current_file:
                items.pop(items.index(item))

                break
        else:
            item = items.pop(0)

        window("jellyfin_play.json", items)

        self.set_item(current_file, item)
        data = {
            "QueueableMediaTypes": "Video,Audio",
            "CanSeek": True,
            "ItemId": item["Id"],
            "MediaSourceId": item["MediaSourceId"],
            "PlayMethod": item["PlayMethod"],
            "VolumeLevel": item["Volume"],
            "PositionTicks": int(item["CurrentPosition"] * 10000000),
            "IsPaused": item["Paused"],
            "IsMuted": item["Muted"],
            "PlaySessionId": item["PlaySessionId"],
            "AudioStreamIndex": item["AudioStreamIndex"],
            "SubtitleStreamIndex": item["SubtitleStreamIndex"],
        }
        try:
            item["Server"].jellyfin.session_playing(data)
        except Exception as e:
            LOG.warning("Failed to report session playing: %s", e)
        window("jellyfin.skip.%s.bool" % item["Id"], True)

        # Immediate skip check for segments starting at 0:00
        if settings("mediaSegmentsEnabled.bool"):
            try:
                self._fetch_skip_segments(item)
                current_pos = int(self.getTime())
                self.check_skip_segments(item, current_pos)
            except Exception:
                pass  # Player may not be ready yet

        if monitor.waitForAbort(2):
            return

        if item["PlayOption"] == "Addon":
            self.set_audio_subs(item["AudioStreamIndex"], item["SubtitleStreamIndex"])

    def set_item(self, file, item):
        """Set playback information."""
        try:
            item["Runtime"] = int(item["Runtime"])
        except (TypeError, ValueError):
            try:
                item["Runtime"] = int(self.getTotalTime())
                LOG.info("Runtime is missing, Kodi runtime: %s" % item["Runtime"])
            except Exception:
                item["Runtime"] = 0
                LOG.info("Runtime is missing, Using Zero")

        try:
            seektime = self.getTime()
        except Exception:  # at this point we should be playing and if not then bail out
            return

        result = JSONRPC("Application.GetProperties").execute(
            {"properties": ["volume", "muted"]}
        )
        result = result.get("result", {})
        volume = result.get("volume")
        muted = result.get("muted")

        item.update(
            {
                "File": file,
                "CurrentPosition": item.get("CurrentPosition") or int(seektime),
                "Muted": muted,
                "Volume": volume,
                "Server": Jellyfin(item["ServerId"]).get_client(),
                "Paused": False,
            }
        )

        self.played[file] = item
        LOG.info("-->[ play/%s ] %s", item["Id"], item)

    def set_audio_subs(self, audio=None, subtitle=None):
        if audio:
            audio = int(audio)
        if subtitle:
            subtitle = int(subtitle)

        """ Only for after playback started
        """
        LOG.info("Setting audio: %s subs: %s", audio, subtitle)
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            item = self.get_file_info(current_file)
            mapping = item["SubsMapping"]

            if audio and len(self.getAvailableAudioStreams()) > 1:
                self.setAudioStream(audio - 1)

            if subtitle is None or subtitle == -1:
                self.showSubtitles(False)

                return

            tracks = len(self.getAvailableAudioStreams())

            if mapping:
                for index in mapping:

                    if mapping[index] == subtitle:
                        self.setSubtitleStream(int(index))

                        break
                else:
                    self.setSubtitleStream(len(mapping) + subtitle - tracks - 1)
            else:
                self.setSubtitleStream(subtitle - tracks - 1)

    def detect_audio_subs(self, item):

        params = {
            "playerid": 1,
            "properties": ["currentsubtitle", "currentaudiostream", "subtitleenabled"],
        }
        result = JSONRPC("Player.GetProperties").execute(params)
        result = result.get("result")

        try:  # Audio tracks
            audio = result["currentaudiostream"]["index"]
        except (KeyError, TypeError):
            audio = 0

        try:  # Subtitles tracks
            subs = result["currentsubtitle"]["index"]
        except (KeyError, TypeError):
            subs = 0

        try:  # If subtitles are enabled
            subs_enabled = result["subtitleenabled"]
        except (KeyError, TypeError):
            subs_enabled = False

        item["AudioStreamIndex"] = audio + 1

        if not subs_enabled or not len(self.getAvailableSubtitleStreams()):
            item["SubtitleStreamIndex"] = None

            return

        mapping = item["SubsMapping"]
        tracks = len(self.getAvailableAudioStreams())

        if mapping:
            if str(subs) in mapping:
                item["SubtitleStreamIndex"] = mapping[str(subs)]
            else:
                item["SubtitleStreamIndex"] = subs - len(mapping) + tracks + 1
        else:
            item["SubtitleStreamIndex"] = subs + tracks + 1

    def next_up(self):

        item = self.get_file_info(self.get_playing_file())
        objects = Objects()

        if item["Type"] != "Episode" or not item.get("CurrentEpisode"):
            return

        next_items = item["Server"].jellyfin.get_adjacent_episodes(
            item["CurrentEpisode"]["tvshowid"], item["Id"]
        )

        for index, next_item in enumerate(next_items["Items"]):
            if next_item["Id"] == item["Id"]:

                try:
                    next_item = next_items["Items"][index + 1]
                except IndexError:
                    LOG.warning("No next up episode.")

                    return

                break
        server_address = item["Server"].auth.get_server_info(
            item["Server"].auth.server_id
        )["address"]
        API = api.API(next_item, server_address)
        data = objects.map(next_item, "UpNext")
        artwork = API.get_all_artwork(objects.map(next_item, "ArtworkParent"), True)
        data["art"] = {
            "tvshow.poster": artwork.get("Series.Primary"),
            "tvshow.fanart": None,
            "thumb": artwork.get("Primary"),
        }
        if artwork["Backdrop"]:
            data["art"]["tvshow.fanart"] = artwork["Backdrop"][0]

        next_info = {
            "play_info": {
                "ItemIds": [data["episodeid"]],
                "ServerId": item["ServerId"],
                "PlayCommand": "PlayNow",
            },
            "current_episode": item["CurrentEpisode"],
            "next_episode": data,
        }

        LOG.info("--[ next up ] %s", next_info)
        event("upnext_data", next_info, hexlify=True)

    def onPlayBackPaused(self):
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            self.get_file_info(current_file)["Paused"] = True
            self.report_playback()
            LOG.debug("-->[ paused ]")

    def onPlayBackResumed(self):
        current_file = self.get_playing_file()

        if self.is_playing_file(current_file):

            self.get_file_info(current_file)["Paused"] = False
            self.report_playback()
            LOG.debug("--<[ paused ]")

    def onPlayBackSeek(self, time, seek_offset):
        """Does not seem to work in Leia??"""
        if self.is_playing_file(self.get_playing_file()):

            self.report_playback()
            LOG.info("--[ seek ]")

            # Check skip segments immediately after seek
            if settings("mediaSegmentsEnabled.bool"):
                try:
                    current_file = self.get_playing_file()
                    item = self.get_file_info(current_file)
                    current_pos = int(self.getTime())
                    self.check_skip_segments(item, current_pos)
                except Exception:
                    pass

    def report_playback(self, report=True):
        """Report playback progress to jellyfin server.
        Check if the user seek.
        """
        current_file = self.get_playing_file()

        if not self.is_playing_file(current_file):
            return

        item = self.get_file_info(current_file)

        if window("jellyfin.external.bool"):
            return

        if settings("mediaSegmentsEnabled.bool"):
            self.check_skip_segments(item, item["CurrentPosition"])

        if not report:
            previous = item["CurrentPosition"]

            try:
                item["CurrentPosition"] = int(self.getTime())
            except Exception as e:
                # getTime() raises RuntimeError if nothing is playing
                LOG.debug("Failed to get playback position: %s", e)
                return

            if int(item["CurrentPosition"]) == 1:
                return

            try:
                played = (
                    float(item["CurrentPosition"] * 10000000)
                    / int(item["Runtime"])
                    * 100
                )
            except ZeroDivisionError:  # Runtime is 0.
                played = 0

            if played > 2.0 and not self.up_next:

                self.up_next = True
                self.next_up()

            if (item["CurrentPosition"] - previous) < 30:
                return

        result = JSONRPC("Application.GetProperties").execute(
            {"properties": ["volume", "muted"]}
        )
        result = result.get("result", {})
        item["Volume"] = result.get("volume")
        item["Muted"] = result.get("muted")
        item["CurrentPosition"] = int(self.getTime())
        self.detect_audio_subs(item)

        data = {
            "QueueableMediaTypes": "Video,Audio",
            "CanSeek": True,
            "ItemId": item["Id"],
            "MediaSourceId": item["MediaSourceId"],
            "PlayMethod": item["PlayMethod"],
            "VolumeLevel": item["Volume"],
            "PositionTicks": int(item["CurrentPosition"] * 10000000),
            "IsPaused": item["Paused"],
            "IsMuted": item["Muted"],
            "PlaySessionId": item["PlaySessionId"],
            "AudioStreamIndex": item["AudioStreamIndex"],
            "SubtitleStreamIndex": item["SubtitleStreamIndex"],
        }
        item["Server"].jellyfin.session_progress(data)

    def onPlayBackStopped(self):
        """Will be called when user stops playing a file."""
        window("jellyfin_play", clear=True)
        self.stop_playback()
        LOG.info("--<[ playback ]")

    def onPlayBackEnded(self):
        """Will be called when kodi stops playing a file."""
        self.stop_playback()
        LOG.info("--<<[ playback ]")

    def stop_playback(self):
        """Stop all playback. Check for external player for positionticks."""
        if not self.played:
            return

        LOG.info("Played info: %s", self.played)

        for file in self.played:
            item = self.get_file_info(file)

            window("jellyfin.skip.%s.bool" % item["Id"], True)

            if window("jellyfin.external.bool"):
                window("jellyfin.external", clear=True)

                if int(item["CurrentPosition"]) == 1:
                    item["CurrentPosition"] = int(item["Runtime"])

            data = {
                "ItemId": item["Id"],
                "MediaSourceId": item["MediaSourceId"],
                "PositionTicks": int(item["CurrentPosition"] * 10000000),
                "PlaySessionId": item["PlaySessionId"],
            }
            item["Server"].jellyfin.session_stop(data)

            if item.get("LiveStreamId"):

                LOG.info("<[ livestream/%s ]", item["LiveStreamId"])
                item["Server"].jellyfin.close_live_stream(item["LiveStreamId"])

            elif item["PlayMethod"] == "Transcode":

                LOG.info("<[ transcode/%s ]", item["Id"])
                item["Server"].jellyfin.close_transcode(
                    item["DeviceId"], item["PlaySessionId"]
                )

            path = translate_path(
                "special://profile/addon_data/plugin.video.jellyfin/temp/"
            )

            if xbmcvfs.exists(path):
                dirs, files = xbmcvfs.listdir(path)

                for file in files:
                    # Only delete the cached files for the previous play session
                    if item["Id"] in file:
                        xbmcvfs.delete(os.path.join(path, file))

            result = item["Server"].jellyfin.get_item(item["Id"]) or {}

            if "UserData" in result and result["UserData"]["Played"]:
                delete = False

                if result["Type"] == "Episode" and settings("deleteTV.bool"):
                    delete = True
                elif result["Type"] == "Movie" and settings("deleteMovies.bool"):
                    delete = True

                if not settings("offerDelete.bool"):
                    delete = False

                if delete:
                    LOG.info("Offer delete option")

                    if dialog(
                        "yesno", translate(30091), translate(33015), autoclose=120000
                    ):
                        item["Server"].jellyfin.delete_item(item["Id"])

            window("jellyfin.external_check", clear=True)

        self.played.clear()

    def _fetch_skip_segments(self, item):
        if not settings("mediaSegmentsEnabled.bool"):
            return

        item_id = item["Id"]
        self.skip_segments.pop(item_id, None)
        self.skip_prompted = set()

        if self.skip_dialog:
            try:
                self.skip_dialog.close()
            except Exception:
                pass
            self.skip_dialog = None

        segments = item["Server"].jellyfin.get_media_segments(item_id)
        if segments:
            segments = self._convert_media_segments(segments)

        if segments:
            self.skip_segments[item_id] = segments
            LOG.info("Loaded media segments for %s: %s", item_id, list(segments.keys()))

    def _convert_media_segments(self, response):
        if not response or "Items" not in response:
            return None

        type_map = {
            "Intro": "Introduction",
            "Outro": "Credits",
            "Recap": "Recap",
            "Preview": "Preview",
            "Commercial": "Commercial",
        }

        segments = {}
        for item in response["Items"]:
            seg_type = type_map.get(item.get("Type"))
            if seg_type:
                segments[seg_type] = {
                    "EpisodeId": item.get("ItemId"),
                    "Start": item.get("StartTicks", 0) / 10000000.0,
                    "End": item.get("EndTicks", 0) / 10000000.0,
                }
        return segments if segments else None

    def _process_segment(
        self, item_id, segment_type, segment, current_position, skip_mode
    ):
        """Check if current position is within segment bounds. Returns (start, end) tuple, None if outside bounds, or False if invalid."""
        start = segment.get("Start")
        end = segment.get("End")
        if start is None or end is None or end <= start:
            return False

        LOG.debug(
            "Skip check: pos=%.1f, %s start=%.1f end=%.1f, in_segment=%s",
            current_position,
            segment_type,
            start,
            end,
            start <= current_position <= end,
        )

        if not (start <= current_position <= end):
            return None

        return (start, end)

    def check_skip_segments(self, item, current_position):
        item_id = item["Id"]
        segments = self.skip_segments.get(item_id)
        if not segments:
            return

        for segment_type, segment in segments.items():
            skip_mode = self._get_segment_skip_mode(segment_type)
            if skip_mode == 0:  # Off
                continue

            bounds = self._process_segment(
                item_id, segment_type, segment, current_position, skip_mode
            )
            if not bounds:
                continue

            start, end = bounds
            segment_key = "%s:%s" % (item_id, segment_type)
            LOG.debug(
                "Skip check: IN WINDOW! segment_key=%s, already_prompted=%s",
                segment_key,
                segment_key in self.skip_prompted,
            )
            if segment_key in self.skip_prompted:
                continue

            self.skip_prompted.add(segment_key)
            LOG.debug(
                "Skip check: Triggering _handle_skip_segment for %s", segment_type
            )

            if segment_type == "Credits" and not self.up_next:
                self.up_next = True
                self.next_up()

            self._handle_skip_segment(segment_type, start, end, skip_mode)
            break

    def _get_segment_skip_mode(self, segment_type):
        """Get the skip mode for a segment type. Returns 0=Off, 1=Auto, 2=Button."""
        setting_map = {
            "Introduction": "skipIntroductionMode",
            "Credits": "skipCreditsMode",
            "Recap": "skipRecapMode",
            "Preview": "skipPreviewMode",
            "Commercial": "skipCommercialMode",
        }
        setting_key = setting_map.get(segment_type)
        if not setting_key:
            return 0
        return int(settings(setting_key) or 0)

    def _handle_skip_segment(self, segment_type, start, end, mode):
        LOG.debug(
            "_handle_skip_segment: type=%s, mode=%d, start=%.1f, end=%.1f",
            segment_type,
            mode,
            start,
            end,
        )

        if mode == 1:  # Auto skip
            self.seekTime(end)
            LOG.info("Auto-skipped %s to %.1f", segment_type, end)
            # Show notification
            message = "Skipped %s" % segment_type
            dialog(
                "notification",
                heading="Jellyfin",
                message=message,
                icon="{jellyfin}",
                time=3000,
            )

        elif mode == 2:  # Show skip button
            self._show_skip_button(segment_type, end - start, end)

    def _show_skip_button(self, segment_type, duration, end_time):
        LOG.debug(
            "_show_skip_button: type=%s, duration=%.1f, end_time=%.1f",
            segment_type,
            duration,
            end_time,
        )
        try:
            import xbmcaddon
            from .dialogs.skip import SkipDialog

            if self.skip_dialog:
                try:
                    self.skip_dialog.close()
                except Exception:
                    pass

            addon_path = xbmcaddon.Addon("plugin.video.jellyfin").getAddonInfo("path")
            LOG.debug("_show_skip_button: addon_path=%s", addon_path)

            self.skip_dialog = SkipDialog(
                "script-jellyfin-skip.xml",
                addon_path,
                "default",
                "1080i",
            )
            self.skip_dialog.set_skip_info(segment_type, duration)
            LOG.debug("_show_skip_button: calling show()")
            self.skip_dialog.show()
            LOG.debug("_show_skip_button: show() completed")

            self._skip_end_time = end_time
            self._monitor_skip_dialog()
        except Exception as e:
            LOG.error("_show_skip_button error: %s", e, exc_info=True)

    def _monitor_skip_dialog(self):
        """Monitor the skip dialog and handle user input or timeout."""
        LOG.debug("_monitor_skip_dialog: starting, end_time=%.1f", self._skip_end_time)
        monitor = xbmc.Monitor()

        # Monitor loop - check for user input or end of segment
        while self.skip_dialog and not monitor.abortRequested():
            # Check if user clicked skip
            if self.skip_dialog.is_skip():
                self.seekTime(self._skip_end_time)
                LOG.info("User skipped to %.1f", self._skip_end_time)
                break

            # Check if user cancelled
            if self.skip_dialog.is_cancel():
                LOG.debug("User cancelled skip dialog")
                break

            # Check if we've passed the segment end time
            try:
                current_pos = self.getTime()
                if current_pos >= self._skip_end_time:
                    LOG.debug(
                        "_monitor_skip_dialog: passed end_time %.1f, closing",
                        self._skip_end_time,
                    )
                    break
            except Exception:
                break

            if monitor.waitForAbort(0.2):
                break

        LOG.debug("_monitor_skip_dialog: exiting loop")
        if self.skip_dialog:
            try:
                self.skip_dialog.close()
            except Exception:
                pass
            self.skip_dialog = None
