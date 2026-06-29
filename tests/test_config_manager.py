"""Tests for config_manager — read/write config, defaults, corrupt file recovery."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# _get_config_dir()
# ---------------------------------------------------------------------------


class TestGetConfigDir:
    """Tests for _get_config_dir() — cross-platform config directory resolution."""

    def test_macos_config_dir(self):
        """On macOS, config dir is ~/Library/Application Support/simple-edge-tts/"""
        from src.config_manager import _get_config_dir
        with patch.object(sys, "platform", "darwin"):
            result = _get_config_dir()
        expected = Path.home() / "Library" / "Application Support" / "simple-edge-tts"
        assert result == expected

    def test_windows_config_dir(self):
        """On Windows, config dir is %APPDATA%/simple-edge-tts/config/ when not frozen."""
        from src.config_manager import _get_config_dir
        fake_appdata = Path(r"C:\Users\test\AppData\Roaming")
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", False, create=True):
                with patch.dict("os.environ", {"APPDATA": str(fake_appdata)}):
                    result = _get_config_dir()
        expected = fake_appdata / "simple-edge-tts" / "config"
        assert result == expected

    def test_windows_frozen_writable_config_dir(self):
        """On Windows when frozen and the exe dir is writable, config dir is the exe directory."""
        from src.config_manager import _get_config_dir
        fake_exe = "D:/Program Files/simple-edge-tts/simple-edge-tts.exe"
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", fake_exe):
                    with patch("pathlib.Path.touch") as mock_touch, patch("pathlib.Path.unlink") as mock_unlink:
                        result = _get_config_dir()
                        mock_touch.assert_called_once()
                        mock_unlink.assert_called_once()
        expected = Path("D:/Program Files/simple-edge-tts")
        assert result == expected

    def test_windows_frozen_readonly_fallback(self):
        """On Windows when frozen but exe dir is not writable, fall back to APPDATA."""
        from src.config_manager import _get_config_dir
        fake_exe = "D:/Program Files/simple-edge-tts/simple-edge-tts.exe"
        fake_appdata = Path(r"C:\Users\test\AppData\Roaming")
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", fake_exe):
                    with patch.dict("os.environ", {"APPDATA": str(fake_appdata)}):
                        with patch("pathlib.Path.touch", side_effect=PermissionError()):
                            result = _get_config_dir()
        expected = fake_appdata / "simple-edge-tts" / "config"
        assert result == expected

    def test_linux_config_dir(self):
        """On Linux, config dir is $XDG_CONFIG_HOME/simple-edge-tts/"""
        from src.config_manager import _get_config_dir
        with patch.object(sys, "platform", "linux"):
            result = _get_config_dir()
        expected = Path.home() / ".config" / "simple-edge-tts"
        assert result == expected


# ---------------------------------------------------------------------------
# enable_file_logging default (spec #105)
# ---------------------------------------------------------------------------


class TestEnableFileLoggingDefault:
    """Test that enable_file_logging defaults to False (per spec #105)."""

    def test_enable_file_logging_default_is_false(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("enable_file_logging") is False
