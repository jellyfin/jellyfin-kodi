import pytest

from jellyfin_kodi.helper import playutils
from jellyfin_kodi.helper.playutils import PlayUtils


@pytest.fixture
def play_utils():
    class ApiClient:
        class config:
            data = {"auth.token": ""}

    yield PlayUtils({}, api_client=ApiClient)


class PatchedSettings:
    # TODO: move settings helper to separate file
    settings = {}

    def __init__(self):
        self.clear()

    @classmethod
    def __call__(cls, setting: str, value=None):
        if value is None:
            result = cls.settings[setting.replace(".bool", "")]

            if result and setting.endswith(".bool"):
                result = result in ("true", "1", True)

            return result

        if setting.endswith(".bool"):
            setting = setting.replace(".bool", "")
            value = bool(value)
        cls.settings[setting] = value
        return None

    @classmethod
    def clear(cls):
        cls.settings.clear()
        # TODO: read defaults from settings.xml
        cls.settings.setdefault("transcode_h265", False)
        cls.settings.setdefault("videoPreferredCodec", "H264/AVC")
        cls.settings.setdefault("transcode_mpeg2", False)
        cls.settings.setdefault("transcode_vc1", False)
        cls.settings.setdefault("audioPreferredCodec", "AAC")
        cls.settings.setdefault("transcode_vp9", False)
        cls.settings.setdefault("transcode_av1", False)


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch):
    patched = PatchedSettings()
    monkeypatch.setattr(playutils, "settings", patched)


@pytest.mark.parametrize(
    "transcode_h265, transcode_av1, preferred_codec, expected_result",
    [
        (False, True, "AV1", "av1,h264,hevc,mpeg4,mpeg2video,vc1"),
        (False, False, "AV1", "av1,h264,hevc,mpeg4,mpeg2video,vc1"),
        (True, True, "AV1", "av1,h264,mpeg4,mpeg2video,vc1"),
        (True, False, "AV1", "av1,h264,mpeg4,mpeg2video,vc1"),
        (False, True, "H265/HEVC", "hevc,h264,mpeg4,mpeg2video,vc1"),
        (False, False, "H265/HEVC", "hevc,h264,mpeg4,mpeg2video,vc1,av1"),
        (True, True, "H265/HEVC", "hevc,h264,mpeg4,mpeg2video,vc1"),
        (True, False, "H265/HEVC", "hevc,h264,mpeg4,mpeg2video,vc1,av1"),
        (False, True, "H264/AVC", "h264,hevc,mpeg4,mpeg2video,vc1"),
        (False, False, "H264/AVC", "h264,hevc,mpeg4,mpeg2video,vc1,av1"),
        (True, True, "H264/AVC", "h264,mpeg4,mpeg2video,vc1"),
        (True, False, "H264/AVC", "h264,mpeg4,mpeg2video,vc1,av1"),
    ],
)
def test_get_transcoding_video_codec_settings(
    play_utils, transcode_h265, transcode_av1, preferred_codec, expected_result
):
    playutils.settings("transcode_h265", transcode_h265)
    playutils.settings("transcode_av1", transcode_av1)
    playutils.settings("videoPreferredCodec", preferred_codec)

    result = play_utils.get_transcoding_video_codec()
    assert result == expected_result


@pytest.mark.parametrize(
    "transcode_mpeg2, transcode_vc1, expected_result",
    [
        (False, False, "h264,hevc,mpeg4,mpeg2video,vc1,av1"),
        (True, False, "h264,hevc,mpeg4,vc1,av1"),
        (False, True, "h264,hevc,mpeg4,mpeg2video,av1"),
        (True, True, "h264,hevc,mpeg4,av1"),
    ],
)
def test_get_transcoding_video_codec_transcode_options(
    play_utils, transcode_mpeg2, transcode_vc1, expected_result
):
    playutils.settings("transcode_mpeg2", transcode_mpeg2)
    playutils.settings("transcode_vc1", transcode_vc1)
    result = play_utils.get_transcoding_video_codec()
    assert result == expected_result


@pytest.mark.parametrize(
    "preferred_codec, expected_first, expected_second",
    [
        ("H265/HEVC", "hevc", "h264"),
        ("H264/AVC", "h264", "hevc"),
    ],
)
def test_get_transcoding_video_codec_order(
    play_utils, preferred_codec, expected_first, expected_second
):
    playutils.settings("videoPreferredCodec", preferred_codec)
    result = play_utils.get_transcoding_video_codec().split(",")
    assert result[0] == expected_first, result
    assert result[1] == expected_second, result


@pytest.mark.parametrize(
    "preferred_codec, transcode_h265, transcode_av1",
    [
        ("H265/HEVC", True, True),
        ("H265/HEVC", True, False),
        ("H265/HEVC", False, True),
        ("H265/HEVC", False, False),
        ("H264/AVC", True, True),
        ("H264/AVC", True, False),
        ("H264/AVC", False, True),
        ("H264/AVC", False, False),
        ("AV1", True, True),
        ("AV1", True, False),
        ("AV1", False, True),
        ("AV1", False, False),
    ],
)
def test_get_transcoding_video_codec_no_duplicates(
    play_utils, preferred_codec, transcode_h265, transcode_av1
):
    playutils.settings("videoPreferredCodec", preferred_codec)
    playutils.settings("transcode_h265", transcode_h265)
    playutils.settings("transcode_av1", transcode_av1)
    result = play_utils.get_transcoding_video_codec().split(",")
    assert len(result) == len(set(result))


@pytest.mark.parametrize(
    "transcode_h265, preferred_codec, transcode_mpeg2, transcode_vc1, transcode_av1, expected_result",
    [
        (True, "H264/AVC", True, True, True, "h264,mpeg4"),
        (False, "H265/HEVC", False, False, False, "hevc,h264,mpeg4,mpeg2video,vc1,av1"),
    ],
)
def test_get_transcoding_video_codec_combined_settings(
    play_utils,
    transcode_h265,
    preferred_codec,
    transcode_mpeg2,
    transcode_vc1,
    transcode_av1,
    expected_result,
):
    playutils.settings("transcode_h265", transcode_h265)
    playutils.settings("videoPreferredCodec", preferred_codec)
    playutils.settings("transcode_mpeg2", transcode_mpeg2)
    playutils.settings("transcode_vc1", transcode_vc1)
    playutils.settings("transcode_av1", transcode_av1)

    result = play_utils.get_transcoding_video_codec()
    assert result == expected_result


@pytest.mark.parametrize(
    "transcode_h265, expected_result",
    [
        (False, "h264,hevc,mpeg4,mpeg2video,vc1,vp9,av1"),
        (True, "h264,mpeg4,mpeg2video,vc1,vp9,av1"),
    ],
)
def test_get_directplay_video_codec(play_utils, transcode_h265, expected_result):
    playutils.settings("transcode_h265", transcode_h265)
    result = play_utils.get_directplay_video_codec()
    assert result == expected_result


@pytest.mark.parametrize(
    "transcode_mpeg2, transcode_vc1, expected_result",
    [
        (False, False, "h264,hevc,mpeg4,mpeg2video,vc1,vp9,av1"),
        (True, False, "h264,hevc,mpeg4,vc1,vp9,av1"),
        (False, True, "h264,hevc,mpeg4,mpeg2video,vp9,av1"),
        (True, True, "h264,hevc,mpeg4,vp9,av1"),
    ],
)
def test_get_directplay_video_codec_transcode_options(
    play_utils, transcode_mpeg2, transcode_vc1, expected_result
):
    playutils.settings("transcode_mpeg2", transcode_mpeg2)
    playutils.settings("transcode_vc1", transcode_vc1)
    result = play_utils.get_directplay_video_codec()
    assert result == expected_result


def test_get_directplay_video_codec_no_duplicates(play_utils):
    result = play_utils.get_directplay_video_codec().split()
    assert len(result) == len(set(result))


@pytest.mark.parametrize(
    "transcode_h265, transcode_mpeg2, transcode_vc1, transcode_vp9, transcode_av1, expected_result",
    [
        (True, True, True, True, True, "h264,mpeg4"),
        (False, False, False, False, False, "h264,hevc,mpeg4,mpeg2video,vc1,vp9,av1"),
    ],
)
def test_get_directplay_video_codec_combined_settings(
    play_utils,
    transcode_h265,
    transcode_mpeg2,
    transcode_vc1,
    transcode_vp9,
    transcode_av1,
    expected_result,
):
    playutils.settings("transcode_h265", transcode_h265)
    playutils.settings("transcode_mpeg2", transcode_mpeg2)
    playutils.settings("transcode_vc1", transcode_vc1)
    playutils.settings("transcode_vp9", transcode_vp9)
    playutils.settings("transcode_av1", transcode_av1)
    result = play_utils.get_directplay_video_codec()
    assert result == expected_result


@pytest.mark.parametrize(
    "preferred_codec, expected_result",
    [
        ("", "aac,mp3,ac3,opus,flac,vorbis"),
        ("AAC", "aac,mp3,ac3,opus,flac,vorbis"),
        ("MP3", "mp3,aac,ac3,opus,flac,vorbis"),
        ("AC3", "ac3,aac,mp3,opus,flac,vorbis"),
        ("OPUS", "opus,aac,mp3,ac3,flac,vorbis"),
        ("FLAC", "flac,aac,mp3,ac3,opus,vorbis"),
        ("VORBIS", "vorbis,aac,mp3,ac3,opus,flac"),
        ("UNKNOWN", "aac,mp3,ac3,opus,flac,vorbis"),
    ],
)
def test_get_transcoding_audio_codec(play_utils, preferred_codec, expected_result):
    playutils.settings("audioPreferredCodec", preferred_codec)
    result = play_utils.get_transcoding_audio_codec()
    assert result == expected_result


def test_get_transcoding_audio_codec_case_insensitive(play_utils):
    playutils.settings("audioPreferredCodec", "aAc")
    result = play_utils.get_transcoding_audio_codec()
    assert result == "aac,mp3,ac3,opus,flac,vorbis"


def test_get_transcoding_audio_codec_no_duplicates(play_utils):
    result = play_utils.get_transcoding_audio_codec().split(",")
    assert len(result) == len(set(result))


def test_get_transcoding_audio_codec_preserve_order(play_utils):
    playutils.settings("audioPreferredCodec", "")
    result = play_utils.get_transcoding_audio_codec()
    assert result == "aac,mp3,ac3,opus,flac,vorbis"
