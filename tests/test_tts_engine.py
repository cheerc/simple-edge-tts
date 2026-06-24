"""Tests for tts_engine — voice listing, param formatting, async generation (mocked)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.tts_engine import TTSEngine, format_rate, format_pitch, sanitize_filename


class TestParamFormatting:
    def test_format_rate_positive(self):
        assert format_rate(20) == "+20%"

    def test_format_rate_zero(self):
        assert format_rate(0) == "+0%"

    def test_format_rate_negative(self):
        assert format_rate(-30) == "-30%"

    def test_format_pitch_positive(self):
        assert format_pitch(10) == "+10Hz"

    def test_format_pitch_zero(self):
        assert format_pitch(0) == "+0Hz"

    def test_format_pitch_negative(self):
        assert format_pitch(-25) == "-25Hz"


class TestSanitizeFilename:
    def test_ascii_text(self):
        result = sanitize_filename("Hello World")
        assert result == "Hello_Wo"

    def test_chinese_text(self):
        result = sanitize_filename("你好世界測試用文字")
        assert result == "你好世界測試用文"

    def test_short_text(self):
        result = sanitize_filename("Hi")
        assert result == "Hi"

    def test_special_chars_replaced(self):
        result = sanitize_filename('a/b\\c:d"e')
        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result

    def test_empty_text(self):
        result = sanitize_filename("")
        assert result == "untitled"


class TestTTSEngineVoices:
    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_list_voices_returns_list(self, mock_list):
        mock_list.return_value = [
            {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
        ]
        engine = TTSEngine()
        voices = engine.get_voices_sync()
        assert len(voices) >= 2

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_voices_grouped_tw_first(self, mock_list):
        mock_voices = [
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
            {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
            {"ShortName": "ja-JP-NanamiNeural", "Locale": "ja-JP", "Gender": "Female"},
        ]
        mock_list.return_value = mock_voices
        engine = TTSEngine()
        grouped = engine.get_grouped_voices_sync()
        groups = list(grouped.keys())
        assert groups[0] == "zh-TW"
        assert groups[1] == "en-US"


class TestTTSEngineGenerate:
    @patch("src.tts_engine.edge_tts.Communicate")
    def test_generate_creates_file(self, mock_communicate, tmp_path):
        mock_instance = MagicMock()
        mock_instance.save = AsyncMock()
        mock_communicate.return_value = mock_instance

        engine = TTSEngine()
        output = tmp_path / "test.mp3"
        asyncio.run(engine.generate("Hello", "en-US-JennyNeural", str(output)))

        mock_communicate.assert_called_once()
        mock_instance.save.assert_called_once_with(str(output))
