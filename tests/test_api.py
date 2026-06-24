"""Tests for PyWebView JS API bridge (src/api.py).

Validates that the Api class correctly delegates to TTSEngine,
ConfigManager, AudioPlayer, and I18n, returning proper JSON/values
for the frontend to consume via window.pywebview.api.*.
"""

import json
from unittest.mock import AsyncMock, MagicMock

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
