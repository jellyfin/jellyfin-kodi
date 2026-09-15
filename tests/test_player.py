from unittest.mock import Mock

import jellyfin_kodi.player as player_module
from jellyfin_kodi.helper import playutils as playutils_module


def test_audio_stream_indexes_are_stored_for_playback(monkeypatch):
    # Validate that KodiAudioStreamIndexes is set, given the
    # Audio streams in the source file
    api_client = Mock()
    api_client.config.data = {"auth.token": ""}

    item = {
        "Id": "item",
        "Type": "Movie",
        "MediaType": "Video",
    }
    source = {
        "Id": "source",
        "Path": "movie",
        "SupportsDirectPlay": False,
        "SupportsDirectStream": True,
        "MediaStreams": [
            {"Index": 0, "Type": "Subtitle"},
            {"Index": 1, "Type": "Subtitle"},
            {"Index": 2, "Type": "Video"},
            {"Index": 3, "Type": "Audio"},
            {"Index": 4, "Type": "Audio"},
        ],
        "DefaultAudioStreamIndex": 4,
        "DefaultSubtitleStreamIndex": None,
    }

    windows = {}

    def fake_window(name, value=None, **kwargs):
        if name == "jellyfin_play.json":
            if value is None:
                return windows.get(name)
            windows[name] = value
            return None
        else:
            return None

    monkeypatch.setattr(playutils_module, "window", fake_window)
    monkeypatch.setattr(playutils_module.client, "get_device_id", lambda: "device")

    class Api:
        def get_file_path(self, _):
            return "movie"

    monkeypatch.setattr(
        playutils_module.api,
        "API",
        lambda *_args, **_kwargs: Api(),
    )

    play_utils = playutils_module.PlayUtils(
        item,
        server="http://server",
        api_client=api_client,
    )
    play_utils.info["Path"] = "movie"
    play_utils.direct_url = lambda _source: None

    play_utils.get(source)
    playutils_module.set_properties(item, "DirectStream", "server")

    playback_item = fake_window("jellyfin_play.json")[0]
    assert playback_item["KodiAudioStreamIndexes"] == [3, 4]


def test_detect_audio_stream_maps_kodi_ordinal_to_jellyfin_index(monkeypatch):
    # Kodi reports audio stream ordinals
    # Jellyfin uses MediaStream indexes.
    player = object.__new__(player_module.Player)
    item = {
        "KodiAudioStreamIndexes": [3, 4],
        "SubsMapping": {},
    }

    class JSONRPC:
        def __init__(self, _):
            pass

        def execute(self, _):
            return {
                "result": {
                    "currentaudiostream": {"index": 1},
                    "currentsubtitle": {},
                    "subtitleenabled": False,
                }
            }

    monkeypatch.setattr(player_module, "JSONRPC", JSONRPC)

    player.detect_audio_subs(item)

    assert item["AudioStreamIndex"] == 4


def test_set_audio_stream_maps_jellyfin_index_to_kodi_ordinal():
    # Jellyfin uses MediaStream indexes
    # Kodi expects audio ordinals.
    player = object.__new__(player_module.Player)
    item = {
        "KodiAudioStreamIndexes": [3, 4],
        "SubsMapping": {},
    }

    player.get_playing_file = lambda: "movie"
    player.get_file_info = lambda _: item
    player.is_playing_file = lambda _: True
    player.getAvailableAudioStreams = lambda: [{}, {}]
    player.setAudioStream = Mock()

    player.set_audio_subs(audio=4)

    player.setAudioStream.assert_called_once_with(1)


def test_playback_started_preserves_requested_audio_stream(monkeypatch):
    # Kodi may not report the current audio stream
    # immediately after playback starts. Preserve
    # the requested stream while detecting it.
    player = object.__new__(player_module.Player)

    server = Mock()
    item = {
        "Id": "item",
        "Path": "movie",
        "PlayOption": "Addon",
        "KodiAudioStreamIndexes": [3, 4],
        "SubsMapping": {},
        "AudioStreamIndex": 4,
        "SubtitleStreamIndex": None,
        "MediaSourceId": "source",
        "PlayMethod": "DirectPlay",
        "Volume": 100,
        "CurrentPosition": 0,
        "Paused": False,
        "Muted": False,
        "PlaySessionId": "session",
        "Server": server,
    }

    player.stop_playback = Mock()
    player._reset_state = Mock()
    player.getPlayingFile = Mock(return_value="movie")
    player.set_item = Mock()
    player.set_audio_subs = Mock()
    player.getAvailableSubtitleStreams = lambda: []

    monitor = Mock()
    monitor.waitForAbort.return_value = False
    monkeypatch.setattr(player_module.xbmc, "Monitor", Mock(return_value=monitor))
    monkeypatch.setattr(player_module, "settings", Mock(return_value=False))

    class JSONRPC:
        def __init__(self, _):
            pass

        def execute(self, _):
            return {
                "result": {
                    "currentaudiostream": {},
                    "currentsubtitle": {},
                    "subtitleenabled": True,
                }
            }

    monkeypatch.setattr(player_module, "JSONRPC", JSONRPC)

    def fake_window(name, value=None, **kwargs):
        if name == "jellyfin_play.json" and value is None:
            return [item]
        return None

    monkeypatch.setattr(player_module, "window", fake_window)

    player.onPlayBackStarted()

    assert item["AudioStreamIndex"] == 4
    player.set_audio_subs.assert_called_once_with(4, None)
