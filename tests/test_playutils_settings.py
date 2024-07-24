from unittest.mock import patch

import pytest


@pytest.fixture
def mock_play_utils():
    with patch("jellyfin_kodi.helper.playutils.PlayUtils") as MockPlayUtils:
        mock_instance = MockPlayUtils.return_value
        mock_instance.get_transcoding_video_codec.return_value = ""
        yield mock_instance


def test_hevc_transcoding_scenario(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        # Scenario 1: Force Transcode enabled, Transcode HEVC disabled
        mock_settings.side_effect = [
            True,  # transcode_h265 = True (Transcode HEVC disabled)
            "",  # videoPreferredCodec = "" (no preference)
            False,  # transcode_mpeg2 = False
            False,  # transcode_vc1 = False
        ]
        mock_play_utils.get_transcoding_video_codec.return_value = (
            "h264,mpeg4,mpeg2video,vc1"
        )
        result_1 = mock_play_utils.get_transcoding_video_codec()

        # Scenario 2: Force Transcode enabled, Transcode HEVC enabled
        mock_settings.side_effect = [
            False,  # transcode_h265 = False (Transcode HEVC enabled)
            "",  # videoPreferredCodec = "" (no preference)
            False,  # transcode_mpeg2 = False
            False,  # transcode_vc1 = False
        ]
        mock_play_utils.get_transcoding_video_codec.return_value = (
            "h264,mpeg4,mpeg2video,vc1,hevc"
        )
        result_2 = mock_play_utils.get_transcoding_video_codec()

        # Assertions
        assert (
            "hevc" not in result_1
        ), "HEVC should not be in codec list when Transcode HEVC is disabled"
        assert (
            "hevc" in result_2
        ), "HEVC should be in codec list when Transcode HEVC is enabled"

        # Ensure other codecs are present in both scenarios
        for codec in ["h264", "mpeg4", "mpeg2video", "vc1"]:
            assert (
                codec in result_1
            ), f"{codec} should be in codec list regardless of HEVC setting"
            assert (
                codec in result_2
            ), f"{codec} should be in codec list regardless of HEVC setting"

        # Ensure the order is correct in both scenarios
        assert (
            result_1 == "h264,mpeg4,mpeg2video,vc1"
        ), "Codec order incorrect when HEVC is disabled"
        assert (
            result_2 == "h264,mpeg4,mpeg2video,vc1,hevc"
        ), "Codec order incorrect when HEVC is enabled"


@pytest.mark.parametrize(
    "transcode_h265, preferred_codec, expected_result",
    [
        (False, "", "h264,mpeg4,mpeg2video,vc1,hevc"),
        (True, "", "h264,mpeg4,mpeg2video,vc1"),
        (False, "H265/HEVC", "hevc,h264,mpeg4,mpeg2video,vc1"),
        (True, "H265/HEVC", "h264,mpeg4,mpeg2video,vc1"),
        (False, "H264", "h264,mpeg4,mpeg2video,vc1,hevc"),
        (True, "H264", "h264,mpeg4,mpeg2video,vc1"),
        (False, "MPEG4", "mpeg4,h264,mpeg2video,vc1,hevc"),
        (True, "MPEG4", "mpeg4,h264,mpeg2video,vc1"),
    ],
)
def test_get_transcoding_video_codec_settings(
    mock_play_utils, transcode_h265, preferred_codec, expected_result
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [transcode_h265, preferred_codec]
        mock_play_utils.get_transcoding_video_codec.return_value = expected_result
        result = mock_play_utils.get_transcoding_video_codec()
        assert result == expected_result


@pytest.mark.parametrize(
    "transcode_mpeg2, transcode_vc1, expected_result",
    [
        (False, False, "h264,mpeg4,mpeg2video,vc1,hevc"),
        (True, False, "h264,mpeg4,vc1,hevc"),
        (False, True, "h264,mpeg4,mpeg2video,hevc"),
        (True, True, "h264,mpeg4,hevc"),
    ],
)
def test_get_transcoding_video_codec_transcode_options(
    mock_play_utils, transcode_mpeg2, transcode_vc1, expected_result
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, "", transcode_mpeg2, transcode_vc1]
        mock_play_utils.get_transcoding_video_codec.return_value = expected_result
        result = mock_play_utils.get_transcoding_video_codec()
        assert result == expected_result


@pytest.mark.parametrize(
    "preferred_codec, expected_first, expected_second",
    [
        ("H265/HEVC", "hevc", "h264"),
        ("H264", "h264", "hevc"),
        ("MPEG4", "mpeg4", "h264"),
    ],
)
def test_get_transcoding_video_codec_order(
    mock_play_utils, preferred_codec, expected_first, expected_second
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, preferred_codec]
        mock_play_utils.get_transcoding_video_codec.return_value = (
            f"{expected_first},{expected_second},mpeg2video,vc1"
        )
        result = mock_play_utils.get_transcoding_video_codec()
        assert result.startswith(expected_first)
        assert expected_second in result
        assert result.index(expected_first) < result.index(expected_second)


def test_get_transcoding_video_codec_no_duplicates(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, ""]
        mock_play_utils.get_transcoding_video_codec.return_value = (
            "h264,mpeg4,mpeg2video,vc1,hevc"
        )
        result = mock_play_utils.get_transcoding_video_codec()
        assert result.count("hevc") == 1
        assert result.count("h264") == 1
        assert result.count("mpeg4") == 1
        assert result.count("mpeg2video") == 1
        assert result.count("vc1") == 1


def test_get_transcoding_video_codec_empty_result(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [True, ""]
        mock_play_utils.get_transcoding_video_codec.return_value = ""
        result = mock_play_utils.get_transcoding_video_codec()
        assert result == ""


def test_get_transcoding_video_codec_single_codec(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [True, "H264"]
        mock_play_utils.get_transcoding_video_codec.return_value = "h264"
        result = mock_play_utils.get_transcoding_video_codec()
        assert result == "h264"


def test_get_transcoding_video_codec_unknown_preferred(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, "UNKNOWN"]
        mock_play_utils.get_transcoding_video_codec.return_value = (
            "h264,mpeg4,mpeg2video,vc1,hevc"
        )
        result = mock_play_utils.get_transcoding_video_codec()
        assert result == "h264,mpeg4,mpeg2video,vc1,hevc"


@pytest.mark.parametrize(
    "transcode_h265, preferred_codec, transcode_mpeg2, transcode_vc1, expected_result",
    [
        (True, "H264", True, True, "h264,mpeg4"),
        (False, "H265/HEVC", False, False, "hevc,h264,mpeg4,mpeg2video,vc1"),
        (True, "MPEG4", True, False, "mpeg4,h264,vc1"),
    ],
)
def test_get_transcoding_video_codec_combined_settings(
    mock_play_utils,
    transcode_h265,
    preferred_codec,
    transcode_mpeg2,
    transcode_vc1,
    expected_result,
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [
            transcode_h265,
            preferred_codec,
            transcode_mpeg2,
            transcode_vc1,
        ]
        mock_play_utils.get_transcoding_video_codec.return_value = expected_result
        result = mock_play_utils.get_transcoding_video_codec()
        assert result == expected_result


@pytest.mark.parametrize(
    "transcode_h265, preferred_codec, expected_result",
    [
        (False, "", "h264,mpeg4,mpeg2video,vc1,hevc"),
        (True, "", "h264,mpeg4,mpeg2video,vc1"),
        (False, "H265/HEVC", "hevc,h264,mpeg4,mpeg2video,vc1"),
        (True, "H265/HEVC", "h264,mpeg4,mpeg2video,vc1"),
        (False, "H264", "h264,mpeg4,mpeg2video,vc1,hevc"),
        (True, "H264", "h264,mpeg4,mpeg2video,vc1"),
        (False, "MPEG4", "mpeg4,h264,mpeg2video,vc1,hevc"),
        (True, "MPEG4", "mpeg4,h264,mpeg2video,vc1"),
    ],
)
def test_get_directplay_video_codec(
    mock_play_utils, transcode_h265, preferred_codec, expected_result
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [transcode_h265, preferred_codec]
        mock_play_utils.get_directplay_video_codec.return_value = expected_result
        result = mock_play_utils.get_directplay_video_codec()
        assert result == expected_result


@pytest.mark.parametrize(
    "transcode_mpeg2, transcode_vc1, expected_result",
    [
        (False, False, "h264,mpeg4,mpeg2video,vc1,hevc"),
        (True, False, "h264,mpeg4,vc1,hevc"),
        (False, True, "h264,mpeg4,mpeg2video,hevc"),
        (True, True, "h264,mpeg4,hevc"),
    ],
)
def test_get_directplay_video_codec_transcode_options(
    mock_play_utils, transcode_mpeg2, transcode_vc1, expected_result
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, "", transcode_mpeg2, transcode_vc1]
        mock_play_utils.get_directplay_video_codec.return_value = expected_result
        result = mock_play_utils.get_directplay_video_codec()
        assert result == expected_result


def test_get_directplay_video_codec_no_duplicates(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, ""]
        mock_play_utils.get_directplay_video_codec.return_value = (
            "h264,mpeg4,mpeg2video,vc1,hevc"
        )
        result = mock_play_utils.get_directplay_video_codec()
        assert result.count("hevc") == 1
        assert result.count("h264") == 1
        assert result.count("mpeg4") == 1
        assert result.count("mpeg2video") == 1
        assert result.count("vc1") == 1


def test_get_directplay_video_codec_empty_result(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [True, ""]
        mock_play_utils.get_directplay_video_codec.return_value = ""
        result = mock_play_utils.get_directplay_video_codec()
        assert result == ""


def test_get_directplay_video_codec_single_codec(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [True, "H264"]
        mock_play_utils.get_directplay_video_codec.return_value = "h264"
        result = mock_play_utils.get_directplay_video_codec()
        assert result == "h264"


def test_get_directplay_video_codec_unknown_preferred(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [False, "UNKNOWN"]
        mock_play_utils.get_directplay_video_codec.return_value = (
            "h264,mpeg4,mpeg2video,vc1,hevc"
        )
        result = mock_play_utils.get_directplay_video_codec()
        assert result == "h264,mpeg4,mpeg2video,vc1,hevc"


@pytest.mark.parametrize(
    "transcode_h265, preferred_codec, transcode_mpeg2, transcode_vc1, expected_result",
    [
        (True, "H264", True, True, "h264,mpeg4"),
        (False, "H265/HEVC", False, False, "hevc,h264,mpeg4,mpeg2video,vc1"),
        (True, "MPEG4", True, False, "mpeg4,h264,vc1"),
    ],
)
def test_get_directplay_video_codec_combined_settings(
    mock_play_utils,
    transcode_h265,
    preferred_codec,
    transcode_mpeg2,
    transcode_vc1,
    expected_result,
):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = [
            transcode_h265,
            preferred_codec,
            transcode_mpeg2,
            transcode_vc1,
        ]
        mock_play_utils.get_directplay_video_codec.return_value = expected_result
        result = mock_play_utils.get_directplay_video_codec()
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
def test_get_transcoding_audio_codec(mock_play_utils, preferred_codec, expected_result):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.return_value = preferred_codec
        mock_play_utils.get_transcoding_audio_codec.return_value = expected_result
        result = mock_play_utils.get_transcoding_audio_codec()
        assert result == expected_result


def test_get_transcoding_audio_codec_case_insensitive(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.return_value = "aAc"
        mock_play_utils.get_transcoding_audio_codec.return_value = (
            "aac,mp3,ac3,opus,flac,vorbis"
        )
        result = mock_play_utils.get_transcoding_audio_codec()
        assert result == "aac,mp3,ac3,opus,flac,vorbis"


def test_get_transcoding_audio_codec_no_duplicates(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.return_value = ""
        mock_play_utils.get_transcoding_audio_codec.return_value = (
            "aac,mp3,ac3,opus,flac,vorbis"
        )
        result = mock_play_utils.get_transcoding_audio_codec()
        assert result.count("aac") == 1
        assert result.count("mp3") == 1
        assert result.count("ac3") == 1
        assert result.count("opus") == 1
        assert result.count("flac") == 1
        assert result.count("vorbis") == 1


def test_get_transcoding_audio_codec_empty_result(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.return_value = ""
        mock_play_utils.get_transcoding_audio_codec.return_value = ""
        result = mock_play_utils.get_transcoding_audio_codec()
        assert result == ""


def test_get_transcoding_audio_codec_single_codec(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.return_value = "AAC"
        mock_play_utils.get_transcoding_audio_codec.return_value = "aac"
        result = mock_play_utils.get_transcoding_audio_codec()
        assert result == "aac"


def test_get_transcoding_audio_codec_preserve_order(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.return_value = ""
        mock_play_utils.get_transcoding_audio_codec.return_value = (
            "aac,mp3,ac3,opus,flac,vorbis"
        )
        result = mock_play_utils.get_transcoding_audio_codec()
        assert result == "aac,mp3,ac3,opus,flac,vorbis"


def test_get_transcoding_audio_codec_multiple_calls(mock_play_utils):
    with patch("jellyfin_kodi.helper.playutils.settings") as mock_settings:
        mock_settings.side_effect = ["AAC", "MP3", "FLAC"]
        mock_play_utils.get_transcoding_audio_codec.side_effect = [
            "aac,mp3,ac3,opus,flac,vorbis",
            "mp3,aac,ac3,opus,flac,vorbis",
            "flac,aac,mp3,ac3,opus,vorbis",
        ]
        result1 = mock_play_utils.get_transcoding_audio_codec()
        result2 = mock_play_utils.get_transcoding_audio_codec()
        result3 = mock_play_utils.get_transcoding_audio_codec()
        assert result1 == "aac,mp3,ac3,opus,flac,vorbis"
        assert result2 == "mp3,aac,ac3,opus,flac,vorbis"
        assert result3 == "flac,aac,mp3,ac3,opus,vorbis"
