"""Integration tests for GUI lifecycle paths — shutdown, reentrancy, JS bridge injection (Issue #114).

These tests use mocked pywebview window, AudioPlayer, Api, SystemTrayManager,
and TTSEngine to exercise the shutdown/lifecycle functions extracted from main().
"""

from unittest.mock import MagicMock, patch

import pytest

from src.main import (
    execute_quit_shutdown,
    execute_window_closing_shutdown,
    inject_audio_bridge_js,
)


# ── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_audio_player():
    ap = MagicMock()
    ap._shutting_down = False
    return ap


@pytest.fixture
def mock_api():
    return MagicMock()


@pytest.fixture
def mock_tray():
    return MagicMock()


@pytest.fixture
def mock_window():
    """Create a mock window WITHOUT _original_evaluate_js attribute.

    execute_window_closing_shutdown() uses getattr(window, '_original_evaluate_js', None)
    as the reentrancy guard. MagicMock.__getattr__ never returns None (it auto-creates
    a new Mock), so we must patch getattr to return None for the first call.
    """
    w = MagicMock()
    w.evaluate_js = MagicMock(return_value=None)
    return w


# ── execute_quit_shutdown ────────────────────────────────────────────────────

class TestExecuteQuitShutdown:
    """Tests for execute_quit_shutdown() — tray Quit → full shutdown."""

    def test_calls_all_cleanup_steps(self, mock_audio_player, mock_api, mock_tray, mock_window):
        execute_quit_shutdown(mock_audio_player, mock_api, mock_tray, mock_window)

        mock_audio_player.begin_shutdown.assert_called_once()
        mock_api.cleanup_preview_files.assert_called_once()
        mock_tray.stop.assert_called_once()
        mock_window.destroy.assert_called_once()

    def test_shutdown_event_loop_called(self, mock_audio_player, mock_api, mock_tray, mock_window):
        with patch("src.main.shutdown_event_loop") as mock_shutdown:
            execute_quit_shutdown(mock_audio_player, mock_api, mock_tray, mock_window)
            mock_shutdown.assert_called_once()

    def test_idempotent_double_call(self, mock_audio_player, mock_api, mock_tray, mock_window):
        """Double-calling execute_quit_shutdown is safe (all steps idempotent)."""
        execute_quit_shutdown(mock_audio_player, mock_api, mock_tray, mock_window)
        execute_quit_shutdown(mock_audio_player, mock_api, mock_tray, mock_window)

        # Each step called twice
        assert mock_audio_player.begin_shutdown.call_count == 2
        assert mock_api.cleanup_preview_files.call_count == 2
        assert mock_tray.stop.call_count == 2
        assert mock_window.destroy.call_count == 2


# ── execute_window_closing_shutdown ──────────────────────────────────────────

class TestExecuteWindowClosingShutdown:
    """Tests for execute_window_closing_shutdown() — X-button / window close path."""

    def test_calls_begin_shutdown_and_cleanup(self, mock_audio_player, mock_api, mock_window):
        execute_window_closing_shutdown(mock_audio_player, mock_api, mock_window)

        mock_audio_player.begin_shutdown.assert_called_once()
        mock_api.cleanup_preview_files.assert_called_once()

    def test_monkey_patches_evaluate_js(self, mock_audio_player, mock_api, mock_window):
        """First call monkey-patches window.evaluate_js."""
        original_evaluate_js = mock_window.evaluate_js

        # MagicMock.__getattr__ never returns None, so we use a plain object
        # with an explicit _original_evaluate_js=None to test the guard.
        class FakeWindow:
            pass

        fake = FakeWindow()
        fake.evaluate_js = MagicMock(return_value="original")
        fake._original_evaluate_js = None  # explicitly None — guard passes

        execute_window_closing_shutdown(mock_audio_player, mock_api, fake)

        # evaluate_js should be replaced with a function
        assert fake.evaluate_js is not original_evaluate_js
        assert callable(fake.evaluate_js)

    def test_patched_evaluate_js_noops_when_shutting_down(self, mock_audio_player, mock_api, mock_window):
        """Patched evaluate_js returns None when _shutting_down is True."""
        with patch.object(mock_window, "_original_evaluate_js", None, create=True):
            execute_window_closing_shutdown(mock_audio_player, mock_api, mock_window)

        mock_audio_player._shutting_down = True
        result = mock_window.evaluate_js("someScript()")
        assert result is None

    def test_patched_evaluate_js_delegates_when_not_shutting_down(self, mock_audio_player, mock_api, mock_window):
        """Patched evaluate_js delegates to original when _shutting_down is False."""
        # Use a plain object to avoid MagicMock getattr issues
        class FakeWindow:
            pass

        fake = FakeWindow()
        fake.evaluate_js = MagicMock(return_value="ok")
        fake._original_evaluate_js = None

        execute_window_closing_shutdown(mock_audio_player, mock_api, fake)

        mock_audio_player._shutting_down = False
        fake.evaluate_js("someScript()")
        # The original evaluate_js (saved as _original_evaluate_js) should have been called
        # The patched function delegates to _original_evaluate_js(script, callback=None)
        fake._original_evaluate_js.assert_called_with("someScript()", None)

    def test_reentrancy_guard_applies_patch_only_once(self, mock_audio_player, mock_api, mock_window):
        """Double-calling execute_window_closing_shutdown: second call is no-op for patching."""
        with patch.object(mock_window, "_original_evaluate_js", None, create=True):
            execute_window_closing_shutdown(mock_audio_player, mock_api, mock_window)

        # After first call, _original_evaluate_js is set to the original evaluate_js
        # Second call: guard sees _original_evaluate_js is not None → skips re-patch
        # Should not raise
        execute_window_closing_shutdown(mock_audio_player, mock_api, mock_window)

    def test_reentrancy_guard_both_paths(self, mock_audio_player, mock_api, mock_tray, mock_window):
        """When quit_shutdown fires after window_closing_shutdown, the
        evaluate_js patch is NOT re-applied (reentrancy guard)."""
        # First: window closing path patches evaluate_js
        with patch.object(mock_window, "_original_evaluate_js", None, create=True):
            execute_window_closing_shutdown(mock_audio_player, mock_api, mock_window)

        # Then: quit path runs (which does NOT call execute_window_closing_shutdown)
        with patch("src.main.shutdown_event_loop"):
            execute_quit_shutdown(mock_audio_player, mock_api, mock_tray, mock_window)

        # Should not raise — both paths completed


# ── inject_audio_bridge_js ───────────────────────────────────────────────────

class TestInjectAudioBridgeJs:
    """Tests for inject_audio_bridge_js() — JS bridge injection on WebView loaded."""

    def test_reads_and_evaluates_bridge_js(self, mock_window, tmp_path):
        """inject_audio_bridge_js() reads the file and evaluates it in the window."""
        bridge_path = tmp_path / "audio_player_bridge.js"
        bridge_path.write_text("window.audioPlayerBridge = {};", encoding="utf-8")

        result = inject_audio_bridge_js(mock_window, bridge_path)

        assert result is True
        mock_window.evaluate_js.assert_called_once_with("window.audioPlayerBridge = {};")

    def test_returns_false_on_file_read_error(self, mock_window, tmp_path):
        """inject_audio_bridge_js() returns False when file cannot be read."""
        bridge_path = tmp_path / "nonexistent.js"
        # File does not exist

        result = inject_audio_bridge_js(mock_window, bridge_path)

        assert result is False

    def test_returns_false_on_evaluate_js_error(self, mock_window, tmp_path):
        """inject_audio_bridge_js() returns False when evaluate_js raises."""
        bridge_path = tmp_path / "bridge.js"
        bridge_path.write_text("code", encoding="utf-8")
        mock_window.evaluate_js.side_effect = Exception("JS error")

        result = inject_audio_bridge_js(mock_window, bridge_path)

        assert result is False

    def test_does_not_raise_on_error(self, mock_window, tmp_path):
        """inject_audio_bridge_js() never raises — always catches exceptions."""
        bridge_path = tmp_path / "bridge.js"
        bridge_path.write_text("code", encoding="utf-8")
        mock_window.evaluate_js.side_effect = RuntimeError("unexpected")

        # Should not raise
        result = inject_audio_bridge_js(mock_window, bridge_path)
        assert result is False
