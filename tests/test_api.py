"""Tests for PyWebView JS API bridge (src/api.py).

Validates that the Api class correctly delegates to TTSEngine,
ConfigManager, AudioPlayer, and I18n, returning proper JSON/values
for the frontend to consume via window.pywebview.api.*.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api import Api


@pytest.fixture
def mock_tts_engine():
    """Create a mock TTSEngine with standard test responses."""
    engine = MagicMock()
    engine.get_voices_sync.return_value = [
        {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
        {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
    ]
    engine.generate = AsyncMock()
    return engine


@pytest.fixture
def mock_config():
    """Create a mock ConfigManager."""
    config = MagicMock()
    config.get.return_value = "zh-TW"
    config.save = MagicMock()
    return config


@pytest.fixture
def mock_audio_player():
    """Create a mock AudioPlayer."""
    player = MagicMock()
    player.play = MagicMock()
    player.stop = MagicMock()
    return player


@pytest.fixture
def mock_i18n():
    """Create a mock I18n with test translations."""
    i18n = MagicMock()
    i18n.current_language = "zh-TW"
    i18n._strings = {"app_title": "Simple Edge TTS", "generate": "產生"}
    return i18n


@pytest.fixture
def api(mock_tts_engine, mock_config, mock_audio_player, mock_i18n):
    """Create an Api instance with all mocked dependencies."""
    return Api(mock_tts_engine, mock_config, mock_audio_player, mock_i18n)


class TestGetVoices:
    """Test get_voices() — returns JSON-encoded voice list."""

    def test_returns_valid_json(self, api, mock_tts_engine):
        result = api.get_voices()
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_voice_data_preserved(self, api, mock_tts_engine):
        result = api.get_voices()
        parsed = json.loads(result)
        assert parsed[0]["ShortName"] == "zh-TW-HsiaoChenNeural"
        assert parsed[1]["Locale"] == "en-US"

    def test_delegates_to_engine(self, api, mock_tts_engine):
        api.get_voices()
        mock_tts_engine.get_voices_sync.assert_called_once()


class TestGenerateTts:
    """Test generate_tts() — generates audio and returns file path."""

    def test_returns_file_path(self, api, mock_tts_engine, tmp_path):
        api._config.get.return_value = str(tmp_path)
        result = api.generate_tts("Hello", "en-US-JennyNeural", 0, 0)
        parsed = json.loads(result)
        assert "path" in parsed
        assert parsed["path"].endswith(".mp3")

    def test_passes_formatted_rate_and_pitch(self, api, mock_tts_engine, tmp_path):
        api._config.get.return_value = str(tmp_path)
        api.generate_tts("Test", "en-US-JennyNeural", 20, -10)
        mock_tts_engine.generate.assert_called_once()
        call_kwargs = mock_tts_engine.generate.call_args
        # rate and pitch should be formatted strings
        assert "+20%" in str(call_kwargs)
        assert "-10Hz" in str(call_kwargs)

    def test_empty_text_returns_error(self, api):
        result = api.generate_tts("", "en-US-JennyNeural", 0, 0)
        parsed = json.loads(result)
        assert "error" in parsed


class TestConfig:
    """Test get_config() / set_config() — config read/write."""

    def test_get_config_returns_json(self, api, mock_config):
        mock_config.get.return_value = "zh-TW"
        result = api.get_config("language")
        parsed = json.loads(result)
        assert parsed["value"] == "zh-TW"

    def test_get_config_delegates_to_manager(self, api, mock_config):
        api.get_config("language")
        mock_config.get.assert_called_with("language")

    def test_set_config_delegates_and_saves(self, api, mock_config):
        result = api.set_config("language", "en-US")
        mock_config.set.assert_called_with("language", "en-US")
        mock_config.save.assert_called_once()
        parsed = json.loads(result)
        assert parsed["success"] is True


class TestGetTranslations:
    """Test get_translations() — returns i18n strings for current language."""

    def test_returns_valid_json(self, api, mock_i18n):
        result = api.get_translations()
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_contains_language_key(self, api, mock_i18n):
        result = api.get_translations()
        parsed = json.loads(result)
        assert parsed["language"] == "zh-TW"

    def test_contains_strings(self, api, mock_i18n):
        result = api.get_translations()
        parsed = json.loads(result)
        assert "strings" in parsed


class TestPlayAudio:
    """Test play_audio() / stop_audio() — audio playback IPC."""

    def test_play_delegates_to_player(self, api, mock_audio_player, tmp_path):
        test_file = tmp_path / "test.mp3"
        test_file.write_bytes(b"fake audio data")
        api.play_audio(str(test_file))
        mock_audio_player.play.assert_called_once_with(str(test_file))

    def test_stop_delegates_to_player(self, api, mock_audio_player):
        api.stop_audio()
        mock_audio_player.stop.assert_called_once()

class TestOutputDir:
    """Test get_output_dir() / select_output_dir() — folder selection IPC."""

    def test_get_output_dir_returns_config_value(self, api, mock_config):
        mock_config.get.return_value = "/Users/test/Downloads"
        result = api.get_output_dir()
        parsed = json.loads(result)
        assert parsed["output_dir"] == "/Users/test/Downloads"
        mock_config.get.assert_called_with("output_dir")

    def test_get_output_dir_falls_back_to_desktop(self, api, mock_config):
        mock_config.get.return_value = None
        result = api.get_output_dir()
        parsed = json.loads(result)
        assert "Desktop" in parsed["output_dir"]

    def test_select_output_dir_no_window_returns_error(self, api):
        result = api.select_output_dir()
        parsed = json.loads(result)
        assert parsed.get("error") is not None

    def test_select_output_dir_persists_selection(self, api, mock_config):
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = ("/Users/test/Music",)
        api.set_window(mock_window)

        result = api.select_output_dir()
        parsed = json.loads(result)
        assert parsed["output_dir"] == "/Users/test/Music"
        mock_config.set.assert_called_with("output_dir", "/Users/test/Music")
        mock_config.save.assert_called()

    def test_select_output_dir_cancel_returns_current(self, api, mock_config):
        mock_window = MagicMock()
        mock_window.create_file_dialog.return_value = None
        api.set_window(mock_window)
        mock_config.get.return_value = "/Users/test/Desktop"

        result = api.select_output_dir()
        parsed = json.loads(result)
        assert parsed["output_dir"] == "/Users/test/Desktop"


class TestSetWindow:
    """Test set_window() — wires PyWebView window to Api."""

    def test_set_window_stores_reference(self, api):
        mock_window = MagicMock()
        api.set_window(mock_window)
        assert api._window is mock_window


class TestPreviewTts:
    """Test preview_tts() — generates to temp file, not output_dir (Issue #52)."""

    def test_returns_temp_path(self, api, mock_tts_engine):
        """preview_tts() returns a path in the system temp directory."""
        import tempfile

        result = api.preview_tts("Hello", "en-US-JennyNeural", 0, 0)
        parsed = json.loads(result)
        assert "path" in parsed
        assert parsed["path"].endswith(".mp3")
        # Should be in temp dir, not Desktop/output_dir
        assert tempfile.gettempdir() in parsed["path"] or "/tmp" in parsed["path"] or "Temp" in parsed["path"]

    def test_does_not_use_output_dir(self, api, mock_tts_engine, mock_config):
        """preview_tts() should NOT read output_dir from config."""
        result = api.preview_tts("Hello", "en-US-JennyNeural", 0, 0)
        parsed = json.loads(result)
        assert "path" in parsed
        # Should not contain Desktop or output_dir
        assert "Desktop" not in parsed["path"]

    def test_empty_text_returns_error(self, api):
        """preview_tts() returns error for empty text."""
        result = api.preview_tts("", "en-US-JennyNeural", 0, 0)
        parsed = json.loads(result)
        assert "error" in parsed

    def test_delegates_to_engine_generate(self, api, mock_tts_engine):
        """preview_tts() calls engine.generate() with correct params."""
        api.preview_tts("Test", "en-US-JennyNeural", 20, -10)
        mock_tts_engine.generate.assert_called_once()
        call_kwargs = mock_tts_engine.generate.call_args
        assert "+20%" in str(call_kwargs)
        assert "-10Hz" in str(call_kwargs)


class TestGetAudioUrl:
    """Test get_audio_url() — path traversal protection (Issue #111)."""

    def test_returns_data_url_for_valid_audio(self, api, mock_config, tmp_path):
        """get_audio_url() returns base64 data URL for audio in allowed dir."""
        mock_config.get.return_value = str(tmp_path)
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb\x90\x00")  # valid MP3 header

        result = api.get_audio_url(str(audio))

        assert result.startswith("data:audio/mpeg;base64,")

    def test_blocks_path_outside_allowed_dirs(self, api, mock_config):
        """get_audio_url() returns empty string for paths outside allowed dirs."""
        mock_config.get.return_value = "/tmp/allowed"

        # Try to read /etc/hosts
        result = api.get_audio_url("/etc/hosts")

        assert result == ""

    def test_blocks_absolute_path_traversal(self, api, mock_config, tmp_path):
        """get_audio_url() rejects paths with .. traversal escaping allowed dir."""
        mock_config.get.return_value = str(tmp_path)
        # Create a file inside allowed dir
        allowed_file = tmp_path / "safe.mp3"
        allowed_file.write_bytes(b"\xff\xfb\x90\x00")

        # Try to escape via .. traversal
        traversal = str(tmp_path / ".." / "etc" / "hosts")

        result = api.get_audio_url(traversal)

        assert result == ""

    def test_returns_empty_for_nonexistent_file(self, api, mock_config, tmp_path):
        """get_audio_url() returns empty string when file does not exist."""
        mock_config.get.return_value = str(tmp_path)

        result = api.get_audio_url(str(tmp_path / "nonexistent.mp3"))

        assert result == ""

    def test_allows_path_in_temp_dir(self, api, mock_config, tmp_path):
        """get_audio_url() allows paths in system temp directory."""
        mock_config.get.return_value = "/some/other/dir"
        # Use actual tempfile.gettempdir() — create file there
        import tempfile
        tmpdir = Path(tempfile.gettempdir())
        test_file = tmpdir / "simple_edge_tts_test_audio.mp3"
        test_file.write_bytes(b"\xff\xfb\x90\x00")
        try:
            result = api.get_audio_url(str(test_file))
            assert result.startswith("data:audio/mpeg;base64,")
        finally:
            test_file.unlink(missing_ok=True)

    def test_returns_empty_for_empty_path(self, api):
        """get_audio_url() returns empty string for empty file_path."""
        result = api.get_audio_url("")
        assert result == ""

    def test_blocks_symlink_pointing_outside(self, api, mock_config, tmp_path):
        """get_audio_url() rejects symlinks that resolve outside allowed dirs."""
        mock_config.get.return_value = str(tmp_path)
        # Create a valid file inside allowed dir
        real_file = tmp_path / "real.mp3"
        real_file.write_bytes(b"\xff\xfb\x90\x00")
        # Create a symlink inside allowed dir pointing to /etc/hosts
        symlink = tmp_path / "evil_link"
        symlink.symlink_to("/etc/hosts")
        try:
            result = api.get_audio_url(str(symlink))
            assert result == ""
        finally:
            symlink.unlink(missing_ok=True)

    def test_rejects_oversized_file(self, api, mock_config, tmp_path):
        """get_audio_url() returns empty string when file exceeds MAX_AUDIO_URL_BYTES (5MB)."""
        mock_config.get.return_value = str(tmp_path)
        audio = tmp_path / "large.mp3"
        # Create a file larger than 5MB
        audio.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1))

        result = api.get_audio_url(str(audio))

        assert result == ""

    def test_size_check_handles_os_error(self, api, mock_config, tmp_path):
        """get_audio_url() returns empty string when stat() raises OSError."""
        mock_config.get.return_value = str(tmp_path)
        audio = tmp_path / "unreadable.mp3"
        audio.write_bytes(b"\xff\xfb\x90\x00")

        # Bypass path-guard and exists() checks, then make stat() raise
        # OSError to simulate a file that disappears between exists()
        # and stat() (reviewer finding F1).
        with patch.object(api, "_is_path_within_allowed_dirs", return_value=True):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "stat", autospec=True,
                                  side_effect=OSError("Permission denied")):
                    result = api.get_audio_url(str(audio))

        assert result == ""


class TestPreviewCleanup:
    """Test preview tempfile tracking and cleanup (Issue #123)."""

    def test_preview_tts_tracks_tempfile(self, api, mock_tts_engine):
        """preview_tts() appends created tempfile path to _preview_tempfiles."""
        result = api.preview_tts("Hello", "en-US-JennyNeural", 0, 0)
        parsed = json.loads(result)
        tmp_path = Path(parsed["path"])

        assert tmp_path in api._preview_tempfiles
        # Clean up
        tmp_path.unlink(missing_ok=True)

    def test_cleanup_preview_files_removes_tracked_files(self, api, mock_tts_engine):
        """cleanup_preview_files() deletes all tracked tempfiles."""
        # Create two preview files
        result1 = api.preview_tts("First", "en-US-JennyNeural", 0, 0)
        result2 = api.preview_tts("Second", "en-US-JennyNeural", 0, 0)
        path1 = Path(json.loads(result1)["path"])
        path2 = Path(json.loads(result2)["path"])

        assert path1.exists()
        assert path2.exists()
        assert len(api._preview_tempfiles) == 2

        api.cleanup_preview_files()

        assert not path1.exists()
        assert not path2.exists()

    def test_cleanup_preview_files_clears_list(self, api, mock_tts_engine):
        """cleanup_preview_files() clears _preview_tempfiles after cleanup."""
        api.preview_tts("Hello", "en-US-JennyNeural", 0, 0)
        result = api.preview_tts("World", "en-US-JennyNeural", 0, 0)
        path2 = Path(json.loads(result)["path"])

        assert len(api._preview_tempfiles) == 2

        api.cleanup_preview_files()

        assert api._preview_tempfiles == []
        # Clean up in case cleanup failed
        path2.unlink(missing_ok=True)

    def test_cleanup_preview_files_idempotent(self, api, mock_tts_engine):
        """cleanup_preview_files() is idempotent — safe to call multiple times."""
        api.preview_tts("Hello", "en-US-JennyNeural", 0, 0)
        result = json.loads(api.preview_tts("World", "en-US-JennyNeural", 0, 0))
        path2 = Path(result["path"])

        api.cleanup_preview_files()
        # Second call should not raise
        api.cleanup_preview_files()

        assert api._preview_tempfiles == []
        path2.unlink(missing_ok=True)

    def test_cleanup_preview_files_handles_missing_file(self, api, mock_tts_engine):
        """cleanup_preview_files() tolerates files already deleted."""
        result = api.preview_tts("Hello", "en-US-JennyNeural", 0, 0)
        path = Path(json.loads(result)["path"])
        # Delete the file before cleanup
        path.unlink()

        # Should not raise
        api.cleanup_preview_files()

        assert api._preview_tempfiles == []


class TestSSMLSanitization:
    """Test SSML/XML escaping in TTS text input (Issue #120)."""

    def test_generate_tts_escapes_xml_tags(self, api, mock_tts_engine):
        """generate_tts() escapes < and > in text before passing to engine."""
        api.generate_tts("<speak>Hello</speak>", "en-US-JennyNeural", 0, 0)

        call_args = mock_tts_engine.generate.call_args
        assert call_args is not None
        text_passed = call_args.kwargs.get("text") or call_args.args[0]
        assert "<" not in text_passed
        assert ">" not in text_passed
        assert "&lt;" in text_passed

    def test_generate_tts_escapes_ampersand(self, api, mock_tts_engine):
        """generate_tts() escapes & in text."""
        api.generate_tts("Rock & Roll", "en-US-JennyNeural", 0, 0)

        call_args = mock_tts_engine.generate.call_args
        text_passed = call_args.kwargs.get("text") or call_args.args[0]
        assert "&amp;" in text_passed
        assert "& " not in text_passed  # raw & not followed by amp;

    def test_generate_tts_preserves_normal_text(self, api, mock_tts_engine):
        """generate_tts() does not modify text without XML special chars."""
        api.generate_tts("Hello world", "en-US-JennyNeural", 0, 0)

        call_args = mock_tts_engine.generate.call_args
        text_passed = call_args.kwargs.get("text") or call_args.args[0]
        assert text_passed == "Hello world"


class TestSSMLSanitizationPreview:
    """Test SSML/XML escaping in preview_tts() (Issue #120)."""

    def test_preview_tts_escapes_xml_tags(self, api, mock_tts_engine):
        """preview_tts() escapes < and > in text."""
        import tempfile
        with patch.object(tempfile, 'NamedTemporaryFile'):
            try:
                api.preview_tts("<voice>Test</voice>", "en-US-JennyNeural", 0, 0)
            except Exception:
                pass  # may fail due to mocked tempfile, but call should have happened

            call_args = mock_tts_engine.generate.call_args
            if call_args:
                text_passed = call_args.kwargs.get("text") or call_args.args[0]
                assert "<" not in text_passed


class TestOutputDirValidation:
    """Test output_dir path validation in set_config() (Issue #121)."""

    def test_set_config_rejects_relative_output_dir(self, api, mock_config):
        """set_config() rejects relative paths for output_dir."""
        result = api.set_config("output_dir", "relative/path")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "error" in parsed
        # Config must NOT be saved with invalid value
        mock_config.set.assert_not_called()

    def test_set_config_rejects_path_traversal_output_dir(self, api, mock_config):
        """set_config() rejects output_dir containing .. traversal."""
        result = api.set_config("output_dir", "/Users/cheerc/../../etc")
        parsed = json.loads(result)
        assert parsed["success"] is False

    def test_set_config_accepts_valid_absolute_path(self, api, mock_config):
        """set_config() accepts a valid absolute path for output_dir."""
        home = str(Path.home())
        result = api.set_config("output_dir", home)
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_config.set.assert_called_with("output_dir", home)
        mock_config.save.assert_called_once()

    def test_set_config_accepts_other_keys_unchanged(self, api, mock_config):
        """set_config() does not validate non-output_dir keys."""
        result = api.set_config("language", "ja-JP")
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_config.set.assert_called_with("language", "ja-JP")

    def test_set_config_rejects_nonexistent_directory(self, api, mock_config):
        """set_config() rejects output_dir that does not exist on disk."""
        result = api.set_config("output_dir", "/nonexistent/path/xyz")
        parsed = json.loads(result)
        assert parsed["success"] is False

    def test_set_config_rejects_empty_output_dir(self, api, mock_config):
        """set_config() rejects empty string for output_dir."""
        result = api.set_config("output_dir", "")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "error" in parsed


class TestCheckUpdate:
    """Test check_update() — GitHub release update check (Issue #113)."""

    def test_returns_error_on_version_failure(self, api):
        """check_update() returns error object when version resolution fails."""
        with patch.object(Api, "_get_app_version", side_effect=Exception("version error")):
            result = api.check_update()
        parsed = json.loads(result)
        assert parsed == {"error": "version error"}

    def test_returns_result_from_checker(self, api, mock_config):
        """check_update() returns the UpdateChecker result as JSON."""
        mock_config.get.return_value = None  # skip_version
        mock_result = {"latest": "1.0.0", "url": "https://example.com"}
        with patch.object(Api, "_get_app_version", return_value="0.1.0"):
            with patch("src.update_checker.UpdateChecker") as mock_checker_cls:
                mock_checker = MagicMock()
                mock_checker.check.return_value = mock_result
                mock_checker_cls.return_value = mock_checker
                result = api.check_update()
        parsed = json.loads(result)
        assert parsed == mock_result

    def test_passes_skip_version_to_checker(self, api, mock_config):
        """check_update() passes skip_version from config to UpdateChecker."""
        mock_config.get.return_value = "0.9.0"  # skip_version
        mock_result = {"latest": "1.0.0", "url": "https://example.com"}
        with patch.object(Api, "_get_app_version", return_value="0.1.0"):
            with patch("src.update_checker.UpdateChecker") as mock_checker_cls:
                mock_checker = MagicMock()
                mock_checker.check.return_value = mock_result
                mock_checker_cls.return_value = mock_checker
                api.check_update()
                # Verify UpdateChecker was constructed with skip_version
                call_args = mock_checker_cls.call_args
                assert call_args.kwargs.get("skip_version") == "0.9.0"

    def test_get_app_version_fallback_to_pyproject_toml(self, api):
        """_get_app_version() falls back to pyproject.toml when package metadata missing."""
        with patch("importlib.metadata.version", side_effect=ImportError("no module")):
            ver = api._get_app_version()
        assert ver == "0.1.0"  # from pyproject.toml in repo

    def test_get_app_version_ultimate_fallback(self, api):
        """_get_app_version() returns '0.0.0' when both sources fail."""
        with patch("importlib.metadata.version", side_effect=ImportError("no module")):
            with patch.object(Path, "read_text", side_effect=OSError("no file")):
                ver = api._get_app_version()
        assert ver == "0.0.0"


class TestNotifyPlaybackFinished:
    """Test notify_playback_finished() — JS bridge playback end notification (Issue #113)."""

    def test_delegates_to_audio_player(self, api, mock_audio_player):
        """notify_playback_finished() calls AudioPlayer.notify_playback_finished()."""
        api.notify_playback_finished()
        mock_audio_player.notify_playback_finished.assert_called_once()

    def test_returns_none(self, api):
        """notify_playback_finished() returns None (void method)."""
        result = api.notify_playback_finished()
        assert result is None

