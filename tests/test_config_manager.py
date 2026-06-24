"""Tests for config_manager — read/write config, defaults, corrupt file recovery."""

import json
from src.config_manager import ConfigManager


class TestConfigManagerDefaults:
    def test_default_language_is_zh_tw(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("language") == "zh-TW"

    def test_default_voice(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("last_voice") == "zh-TW-HsiaoChenNeural"

    def test_default_rate(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("rate") == "+0%"

    def test_default_pitch(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("pitch") == "+0Hz"

    def test_default_output_dir_is_desktop(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert "Desktop" in cm.get("output_dir") or cm.get("output_dir") == ""

    def test_unknown_key_returns_none(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("nonexistent_key") is None


class TestConfigManagerReadWrite:
    def test_set_and_get(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.set("language", "en-US")
        assert cm.get("language") == "en-US"

    def test_persistence_across_instances(self, tmp_path):
        cm1 = ConfigManager(config_dir=tmp_path)
        cm1.set("rate", "+20%")
        cm1.save()

        cm2 = ConfigManager(config_dir=tmp_path)
        assert cm2.get("rate") == "+20%"

    def test_save_creates_config_file(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.save()
        assert (tmp_path / "config.json").exists()

    def test_save_writes_valid_json(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.set("language", "en-US")
        cm.save()
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["language"] == "en-US"


class TestConfigManagerEdgeCases:
    def test_corrupt_json_resets_to_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json!!!}")
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("language") == "zh-TW"

    def test_missing_key_in_file_falls_back_to_default(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"language": "en-US"}')
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("language") == "en-US"
        assert cm.get("rate") == "+0%"

    def test_config_dir_created_if_missing(self, tmp_path):
        nested = tmp_path / "subdir" / "config"
        cm = ConfigManager(config_dir=nested)
        cm.save()
        assert nested.exists()
        assert (nested / "config.json").exists()
