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


class TestShutdownEventLoop:
    """Tests for shutdown_event_loop() — graceful event loop teardown (Issue #47 fix)."""

    def test_shutdown_stops_running_loop(self):
        """shutdown_event_loop() stops the persistent event loop and joins the thread."""
        from src.tts_engine import _get_loop, shutdown_event_loop

        # Ensure the loop is running
        loop = _get_loop()
        assert loop.is_running()

        shutdown_event_loop()

        # After shutdown, loop should be stopped
        assert not loop.is_running()

    def test_shutdown_idempotent_when_no_loop(self):
        """shutdown_event_loop() is safe to call when no loop exists."""
        import src.tts_engine as tts_mod
        from src.tts_engine import shutdown_event_loop

        # Force module state to no loop
        old_loop = tts_mod._loop
        old_thread = tts_mod._thread
        tts_mod._loop = None
        tts_mod._thread = None
        try:
            shutdown_event_loop()  # Should not raise
        finally:
            # Restore so other tests aren't affected
            tts_mod._loop = old_loop
            tts_mod._thread = old_thread

    def test_shutdown_allows_loop_recreation(self):
        """After shutdown, _get_loop() creates a fresh loop that works."""
        from src.tts_engine import _get_loop, shutdown_event_loop

        # Get initial loop and shut it down
        loop1 = _get_loop()
        shutdown_event_loop()

        # Get a new loop — should be a fresh one
        loop2 = _get_loop()
        assert loop2.is_running()
        assert loop2 is not loop1


class TestWindowsEventLoopPolicy:
    """Tests for Windows-specific event loop policy fix (Issue #95).

    On Windows, asyncio defaults to ProactorEventLoop which is incompatible
    with aiohttp's DNS resolver. _get_loop() must ensure SelectorEventLoop
    is used on Windows to prevent the app from hanging during voice list
    initialization.
    """

    def test_ensure_selector_policy_sets_policy_on_windows(self):
        """_ensure_selector_policy() sets WindowsSelectorEventLoopPolicy when on Windows."""
        from src.tts_engine import _ensure_selector_policy

        with patch("src.tts_engine.sys") as mock_sys:
            mock_sys.platform = "win32"
            # Mock the Windows-specific policy class
            mock_policy_cls = MagicMock()
            with patch.dict("sys.modules", {}):
                with patch("asyncio.WindowsSelectorEventLoopPolicy", mock_policy_cls, create=True):
                    with patch("asyncio.set_event_loop_policy") as mock_set_policy:
                        _ensure_selector_policy()
                        mock_set_policy.assert_called_once_with(mock_policy_cls())

    def test_ensure_selector_policy_noop_on_non_windows(self):
        """_ensure_selector_policy() does nothing on macOS/Linux."""
        from src.tts_engine import _ensure_selector_policy

        with patch("src.tts_engine.sys") as mock_sys:
            mock_sys.platform = "darwin"
            with patch("asyncio.set_event_loop_policy") as mock_set_policy:
                _ensure_selector_policy()
                mock_set_policy.assert_not_called()

    def test_get_loop_does_not_call_ensure_selector_policy(self):
        """_get_loop() does NOT call _ensure_selector_policy() — it's called from main() instead (Ref: #95)."""
        from src.tts_engine import _get_loop, shutdown_event_loop

        # Shutdown any existing loop so _get_loop creates a new one
        shutdown_event_loop()

        with patch("src.tts_engine._ensure_selector_policy") as mock_ensure:
            loop = _get_loop()
            mock_ensure.assert_not_called()
            assert loop.is_running()


class TestGetVoicesSyncGracefulDegradation:
    """Tests for graceful degradation when voice fetch fails (Issue #95).

    When both prefetch cache is empty AND online fetch fails, get_voices_sync()
    should return an empty list instead of propagating the exception — this
    prevents the Windows app from hanging when the IPC call blocks.
    """

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_get_voices_sync_returns_empty_on_failure(self, mock_list):
        """get_voices_sync() returns [] when cache is None and online fetch raises."""
        mock_list.side_effect = Exception("network error")
        engine = TTSEngine()
        assert engine._voices_cache is None
        result = engine.get_voices_sync()
        assert result == []

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_get_voices_sync_returns_empty_on_timeout(self, mock_list):
        """get_voices_sync() returns [] when online fetch times out."""
        mock_list.side_effect = TimeoutError("timed out")
        engine = TTSEngine()
        result = engine.get_voices_sync()
        assert result == []


class TestVoiceFetchTimeout:
    """Tests for _fetch_voices_with_timeout() — network-level timeout wrapper (Issue #95).

    edge_tts.list_voices() uses aiohttp with no timeout by default.
    _fetch_voices_with_timeout() wraps it with asyncio.wait_for(timeout=10)
    and a force_close TCPConnector to prevent indefinite hangs on Windows.
    """

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_fetch_voices_with_timeout_returns_voices(self, mock_list):
        """_fetch_voices_with_timeout() returns voice list when network succeeds."""
        mock_voices = [
            {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
        ]
        mock_list.return_value = mock_voices
        from src.tts_engine import _fetch_voices_with_timeout, run_async
        result = run_async(_fetch_voices_with_timeout())
        assert result == mock_voices

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_prefetch_voices_passes_connector_to_list_voices(self, mock_list):
        """prefetch_voices() → _fetch_voices_with_timeout() passes a TCPConnector to list_voices."""
        mock_voices = [{"ShortName": "test", "Locale": "en-US", "Gender": "Female"}]
        mock_list.return_value = mock_voices
        engine = TTSEngine()
        engine.prefetch_voices()
        assert engine._voices_cache == mock_voices
        # Verify list_voices was called with a connector kwarg
        call_kwargs = mock_list.call_args.kwargs
        assert "connector" in call_kwargs
        import aiohttp
        assert isinstance(call_kwargs["connector"], aiohttp.TCPConnector)

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_get_voices_sync_passes_connector_to_list_voices(self, mock_list):
        """get_voices_sync() → _fetch_voices_with_timeout() passes a TCPConnector to list_voices."""
        mock_voices = [{"ShortName": "test", "Locale": "en-US", "Gender": "Female"}]
        mock_list.return_value = mock_voices
        engine = TTSEngine()
        result = engine.get_voices_sync()
        assert result == mock_voices
        call_kwargs = mock_list.call_args.kwargs
        assert "connector" in call_kwargs

    @patch("src.tts_engine.edge_tts.list_voices", new_callable=AsyncMock)
    def test_fetch_voices_with_timeout_propagates_exception(self, mock_list):
        """_fetch_voices_with_timeout() propagates exceptions from list_voices."""
        mock_list.side_effect = Exception("network error")
        from src.tts_engine import _fetch_voices_with_timeout, run_async
        try:
            run_async(_fetch_voices_with_timeout())
            assert False, "Should have raised"
        except Exception:
            pass  # Expected — exception propagates through asyncio.wait_for


class TestRunAsyncTimeout:
    """Test that run_async() uses the reduced timeout (Ref: #95)."""

    def test_run_async_timeout_is_15_seconds(self):
        """run_async() should use _RUN_ASYNC_TIMEOUT = 15 (reduced from 30)."""
        from src.tts_engine import _RUN_ASYNC_TIMEOUT, run_async
        assert _RUN_ASYNC_TIMEOUT == 15

        # Verify run_async passes the correct timeout to future.result
        with patch("src.tts_engine._get_loop") as mock_get_loop:
            mock_loop = MagicMock()
            mock_future = MagicMock()
            mock_loop.is_closed.return_value = False
            mock_future.result = MagicMock(return_value="ok")
            with patch("src.tts_engine.asyncio.run_coroutine_threadsafe", return_value=mock_future):
                mock_get_loop.return_value = mock_loop
                async def dummy_coro():
                    return "ok"
                result = run_async(dummy_coro())
                assert result == "ok"
                mock_future.result.assert_called_once_with(timeout=15)


class TestEnsureSelectorPolicyExported:
    """Test that _ensure_selector_policy is exported and callable."""

    def test_ensure_selector_policy_is_importable(self):
        """_ensure_selector_policy is importable from src.tts_engine."""
        from src.tts_engine import _ensure_selector_policy
        assert callable(_ensure_selector_policy)

    def test_ensure_selector_policy_noop_on_non_windows(self):
        """_ensure_selector_policy() is a no-op on non-Windows platforms (macOS/Linux)."""
        import sys
        assert sys.platform != "win32"  # This test runs on macOS/Linux CI
        from src.tts_engine import _ensure_selector_policy
        with patch("asyncio.set_event_loop_policy") as mock_set:
            _ensure_selector_policy()
            mock_set.assert_not_called()

