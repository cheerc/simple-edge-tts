"""Tests for i18n — translation loading, key parity, fallback."""

import json
from pathlib import Path
from src.i18n import I18n


TRANSLATIONS_DIR = Path(__file__).parent.parent / "src" / "resources" / "translations"


class TestI18nLoading:
    def test_load_zh_tw(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "試聽"

    def test_load_en_us(self):
        i18n = I18n("en-US", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "Preview"

    def test_switch_language(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "試聽"
        i18n.set_language("en-US")
        assert i18n.t("preview") == "Preview"

    def test_current_language(self):
        i18n = I18n("en-US", translations_dir=TRANSLATIONS_DIR)
        assert i18n.current_language == "en-US"


class TestI18nFallback:
    def test_missing_key_returns_key_name(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("nonexistent_key") == "nonexistent_key"

    def test_invalid_language_falls_back_to_zh_tw(self):
        i18n = I18n("fr-FR", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "試聽"


class TestI18nKeyParity:
    def test_both_languages_have_same_keys(self):
        zh = json.loads((TRANSLATIONS_DIR / "zh-TW.json").read_text())
        en = json.loads((TRANSLATIONS_DIR / "en-US.json").read_text())
        assert set(zh.keys()) == set(en.keys()), (
            f"Key mismatch: zh-TW only={set(zh.keys()) - set(en.keys())}, "
            f"en-US only={set(en.keys()) - set(zh.keys())}"
        )


class TestI18nFormatting:
    def test_string_interpolation(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        result = i18n.t("status_exported", filename="test.mp3")
        assert result == "匯出完成：test.mp3"

    def test_string_interpolation_en(self):
        i18n = I18n("en-US", translations_dir=TRANSLATIONS_DIR)
        result = i18n.t("status_exported", filename="test.mp3")
        assert result == "Exported: test.mp3"
