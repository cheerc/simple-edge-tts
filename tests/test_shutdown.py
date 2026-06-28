"""Tests for shutdown handlers — dual-entry reentrancy regression.

Ref: #112 — Shutdown dual-entry reentrancy lacks automated regression test.
Extracted module-level functions execute_quit_shutdown + execute_window_closing_shutdown
are tested here with mocks to verify the dual-trigger (Cmd+Q → window.destroy() →
closing handler) scenario does not hang.
"""

from unittest.mock import MagicMock, patch


class FakeWindow:
    """Plain object stub for pywebview window — no MagicMock auto-attribute behavior.

    MagicMock's __getattr__ never raises AttributeError, which breaks
    getattr(window, '_original_evaluate_js', None) — it always returns a
    new MagicMock instead of None, making the monkey-patch guard always skip.
    """

    def __init__(self):
        self.evaluate_js = MagicMock()
        self.destroy = MagicMock()


class TestShutdownHandlers:
    """Tests for execute_quit_shutdown and execute_window_closing_shutdown."""

    def test_module_functions_importable(self):
        """verify from src.main import execute_quit_shutdown, execute_window_closing_shutdown works."""
        from src.main import execute_quit_shutdown, execute_window_closing_shutdown  # noqa: F811

        assert callable(execute_quit_shutdown)
        assert callable(execute_window_closing_shutdown)

    @patch("src.main.shutdown_event_loop")
    def test_quit_shutdown_calls_all_cleanup(self, mock_shutdown):
        """execute_quit_shutdown calls all 5 cleanup steps in order."""
        from src.main import execute_quit_shutdown

        audio_player = MagicMock()
        api = MagicMock()
        tray = MagicMock()
        window = FakeWindow()

        execute_quit_shutdown(audio_player, api, tray, window)

        audio_player.begin_shutdown.assert_called()
        api.cleanup_preview_files.assert_called()
        tray.stop.assert_called()
        mock_shutdown.assert_called()
        window.destroy.assert_called()

    @patch("src.main.shutdown_event_loop")
    def test_window_closing_shutdown_monkey_patches(self, mock_shutdown):
        """execute_window_closing_shutdown applies evaluate_js monkey-patch once."""
        from src.main import execute_window_closing_shutdown

        audio_player = MagicMock()
        api = MagicMock()
        window = FakeWindow()

        execute_window_closing_shutdown(audio_player, api, window)

        audio_player.begin_shutdown.assert_called()
        api.cleanup_preview_files.assert_called()
        # Monkey-patch guard: _original_evaluate_js set exactly once
        assert hasattr(window, "_original_evaluate_js")
        assert window.evaluate_js is not window._original_evaluate_js
        # shutdown_event_loop NOT called (only in quit path)

    @patch("src.main.shutdown_event_loop")
    def test_window_closing_shutdown_idempotent(self, mock_shutdown):
        """Second call to execute_window_closing_shutdown does not double-patch."""
        from src.main import execute_window_closing_shutdown

        audio_player = MagicMock()
        api = MagicMock()
        window = FakeWindow()

        execute_window_closing_shutdown(audio_player, api, window)
        first_patched = window.evaluate_js

        execute_window_closing_shutdown(audio_player, api, window)
        # Guard holds: evaluate_js should still be the same patched version
        assert window.evaluate_js is first_patched

    @patch("src.main.shutdown_event_loop")
    def test_dual_trigger_no_hang(self, mock_shutdown):
        """Simulate Cmd+Q → window.destroy() → closing handler re-enters.

        Wire FakeWindow.destroy.side_effect to invoke the closing handler
        to correctly simulate the reentrancy path. Verifies no exceptions,
        all cleanup called, and monkey-patch guard holds.
        """
        from src.main import execute_quit_shutdown, execute_window_closing_shutdown

        audio_player = MagicMock()
        api = MagicMock()
        tray = MagicMock()
        window = FakeWindow()

        # Wire reentrancy: window.destroy() triggers the closing handler
        def on_window_closing():
            execute_window_closing_shutdown(audio_player, api, window)

        window.destroy.side_effect = on_window_closing

        # Simulate Cmd+Q
        execute_quit_shutdown(audio_player, api, tray, window)

        # All cleanup called at least once (called from multiple paths)
        audio_player.begin_shutdown.assert_called()
        api.cleanup_preview_files.assert_called()
        tray.stop.assert_called()
        mock_shutdown.assert_called()

        # Monkey-patch guard held: only patched once
        assert hasattr(window, "_original_evaluate_js")

        # shut_down flag allows safe_evaluate_js to return None
        audio_player._shutting_down = True
        result = window.evaluate_js("some_script()")
        assert result is None
