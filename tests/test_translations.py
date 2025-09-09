import os
from pathlib import Path

import pytest


BASEDIR = Path(__file__).parent.parent
TRANSLATIONS_BASE = BASEDIR / "resources" / "language"

TRANSLATION_DIRS = os.listdir(TRANSLATIONS_BASE)

KNOWN_KODI_LANGUAGE_CODES = {
    "en_gb",  # Base language
    "es_es",
    "ta_in",
    "fr_ca",
    "en_nz",
    "eo",
    "fa_ir",
    "szl",
    "nb_no",
    "vi_vn",
    "sk_sk",
    "mn_mn",
    "ru_ru",
    "fi_fi",
    "nl_nl",
    "lv_lv",
    "hi_in",
    "pt_pt",
    "de_de",
    "it_it",
    "ja_jp",
    "ms_my",
    "sr_rs@latin",
    "is_is",
    "pl_pl",
    "fo_fo",
    "si_lk",
    "es_mx",
    "hu_hu",
    "pt_br",
    "en_us",
    "ar_sa",
    "tg_tj",
    "el_gr",
    "ast_es",
    "es_ar",
    "be_by",
    "af_za",
    "sv_se",
    "am_et",
    "my_mm",
    "fr_fr",
    "sq_al",
    "et_ee",
    "ga_ie",
    "ko_kr",
    "id_id",
    "gl_es",
    "bg_bg",
    "cs_cz",
    "eu_es",
    "fa_af",
    "ro_ro",
    "th_th",
    "zh_tw",
    "mi",
    "mt_mt",
    "ml_in",
    "uk_ua",
    "da_dk",
    "cy_gb",
    "az_az",
    "he_il",
    "kn_in",
    "zh_cn",
    "hy_am",
    "te_in",
    "hr_hr",
    "ca_es",
    "tr_tr",
    "bs_ba",
    "sr_rs",
    "uz_uz",
    "lt_lt",
    "os_os",
    "fil",
    "sl_si",
    "en_au",
    "mk_mk",
}

ADDITIONAL_LANGUAGE_EXCEPTIONS = {
    "es_419",  # Spanish, Latin America
}


@pytest.mark.parametrize(
    "dir",
    TRANSLATION_DIRS,
)
def test_langcode_lower(dir: str):
    _, code = dir.rsplit(".", 1)
    assert code.islower()


@pytest.mark.parametrize(
    "dir",
    TRANSLATION_DIRS,
)
def test_langcode_country(dir: str):
    _, code = dir.rsplit(".", 1)

    if (
        code not in KNOWN_KODI_LANGUAGE_CODES
        and code not in ADDITIONAL_LANGUAGE_EXCEPTIONS
    ):
        for c in KNOWN_KODI_LANGUAGE_CODES:
            if code in c:
                print(f"Maybe {code} should be {c}?")

        assert len(code) == 5
        assert "_" in code
        lang, country = code.split("_", 1)
        assert lang.isalpha()
        assert country.isalpha()


def parse_language_headers(file):
    with open(file, "rt", encoding="utf-8") as fh:
        sections = {}
        section = None
        for line in fh:
            line = line.strip()
            if not line:
                break

            if line[0] == "#":
                continue
            elif line[0] == '"':
                sections[section].append(line)
            else:
                section, value = line.split(None, 1)
                sections[section] = [value]

        for section in sections.keys():
            sections[section] = "".join(
                [
                    x[1:-1].replace('\\"', '"').replace("\\n", "\n")
                    for x in sections[section]
                ]
            )

        d = {"file": file}
        for line in sections["msgstr"].split("\n"):
            line = line.strip()
            if not line:
                continue
            key, value = line.split(":", 1)
            d[key] = value.strip()

        return d


@pytest.mark.parametrize(
    "dir",
    TRANSLATION_DIRS,
)
def test_langcode_matches(dir: str):
    _, code = dir.rsplit(".", 1)

    headers = parse_language_headers(TRANSLATIONS_BASE / dir / "strings.po")

    assert "Language" in headers
    assert headers["Language"] == code
