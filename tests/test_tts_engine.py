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


class TestTTSEnginePrefetchCache:
    """Tests for voice prefetch cache behavior (Issue #43 fix)."""

    def test_init_voices_cache_is_none(self):
        """TTSEngine.__init__ initializes _voices_cache = None."""
        engine = TTSEngine()
        assert engine._voices_cache is None

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_prefetch_voices_populates_cache(self, mock_list):
        """prefetch_voices() calls run_async(edge_tts.list_voices()) and stores result."""
        mock_voices = [
            {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
        ]
        mock_list.return_value = mock_voices
        engine = TTSEngine()
        engine.prefetch_voices()
        assert engine._voices_cache == mock_voices

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_get_voices_sync_returns_cache_when_populated(self, mock_list):
        """get_voices_sync() returns _voices_cache when non-None, without calling list_voices."""
        cached = [{"ShortName": "cached-voice", "Locale": "test", "Gender": "Male"}]
        engine = TTSEngine()
        engine._voices_cache = cached
        result = engine.get_voices_sync()
        assert result == cached
        mock_list.assert_not_called()

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_get_voices_sync_falls_back_when_cache_is_none(self, mock_list):
        """get_voices_sync() fetches online when _voices_cache is None."""
        online_voices = [
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
        ]
        mock_list.return_value = online_voices
        engine = TTSEngine()
        assert engine._voices_cache is None
        result = engine.get_voices_sync()
        assert result == online_voices

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_prefetch_voices_exception_leaves_cache_none(self, mock_list):
        """If prefetch_voices() raises, _voices_cache stays None (fallback still works)."""
        mock_list.side_effect = Exception("network error")
        engine = TTSEngine()
        engine.prefetch_voices()  # Should not raise
        assert engine._voices_cache is None


class TestGetLoopCustomExecutor:
    """Test that _get_loop() sets a custom ThreadPoolExecutor on new loops."""

    def test_loop_has_custom_executor(self):
        """_get_loop() should set a custom ThreadPoolExecutor on the event loop."""
        import concurrent.futures
        from src.tts_engine import _get_loop

        loop = _get_loop()
        # The loop should have a custom default executor set
        # (asyncio stores it in loop._default_executor)
        executor = getattr(loop, "_default_executor", None)
        assert executor is not None
        assert isinstance(executor, concurrent.futures.ThreadPoolExecutor)


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
