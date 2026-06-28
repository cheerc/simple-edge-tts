"""Tests for audio_player — state machine: idle→playing→idle, stop, errors.

Replaced PySide6 QMediaPlayer with HTML5 <audio> bridge pattern.
Python side is a thin bridge; actual playback handled by JS in WebView.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.audio_player import AudioPlayer, PlayerState, SimpleSignal


class TestPlayerState:
    def test_initial_state_is_idle(self):
        player = AudioPlayer()
        assert player.state == PlayerState.IDLE

    def test_play_changes_state(self):
        player = AudioPlayer()
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            assert player.state == PlayerState.PLAYING

    def test_stop_returns_to_idle(self):
        player = AudioPlayer()
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            player.stop()
            assert player.state == PlayerState.IDLE

    def test_stop_when_idle_is_noop(self):
        player = AudioPlayer()
        player.stop()
        assert player.state == PlayerState.IDLE

    def test_play_nonexistent_file_stays_idle(self):
        player = AudioPlayer()
        player.play("/nonexistent/file.mp3")
        assert player.state == PlayerState.IDLE


class TestWebViewBridge:
    """Tests for the WebView JS bridge integration."""

    def test_set_webview_window(self):
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        assert player._window is mock_window

    def test_play_calls_js_when_window_set(self):
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            mock_window.evaluate_js.assert_called_once()
            js_call = mock_window.evaluate_js.call_args[0][0]
            assert "playAudio" in js_call

    def test_stop_calls_js_when_window_set(self):
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            player.stop()
            mock_window.evaluate_js.assert_called()
            # Last call should be stopAudio
            js_call = mock_window.evaluate_js.call_args[0][0]
            assert "stopAudio" in js_call

    def test_play_without_window_still_tracks_state(self):
        """Player tracks state even without JS bridge (headless/test mode)."""
        player = AudioPlayer()
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            assert player.state == PlayerState.PLAYING

    def test_stop_without_window_still_tracks_state(self):
        player = AudioPlayer()
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            player.stop()
            assert player.state == PlayerState.IDLE


class TestCallbacks:
    """Tests for state change and playback finished callbacks."""

    def test_state_changed_callback(self):
        player = AudioPlayer()
        states = []
        player.on_state_changed = lambda s: states.append(s)
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            assert states == [PlayerState.PLAYING]

    def test_playback_finished_callback(self):
        player = AudioPlayer()
        finished = []
        player.on_playback_finished = lambda: finished.append(True)
        player.notify_playback_finished()
        assert finished == [True]
        assert player.state == PlayerState.IDLE

    def test_notify_finished_changes_state(self):
        player = AudioPlayer()
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            assert player.state == PlayerState.PLAYING
            player.notify_playback_finished()
            assert player.state == PlayerState.IDLE

    def test_state_changed_on_stop(self):
        player = AudioPlayer()
        states = []
        player.on_state_changed = lambda s: states.append(s)
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            player.stop()
            assert states == [PlayerState.PLAYING, PlayerState.IDLE]


class TestFilePath:
    """Tests for file path handling."""

    def test_play_resolves_path(self):
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        with patch("src.audio_player.Path.exists", return_value=True), \
             patch("src.audio_player.Path.resolve", return_value=Path("/resolved/path.mp3")):
            player.play("/fake/path.mp3")
            js_call = mock_window.evaluate_js.call_args[0][0]
            # Should contain the file path in the JS call
            assert "path.mp3" in js_call

    def test_current_file_property(self):
        player = AudioPlayer()
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
            assert player.current_file is not None
            assert "path.mp3" in str(player.current_file)

    def test_current_file_none_when_idle(self):
        player = AudioPlayer()
        assert player.current_file is None


class TestShutdownGuard:
    def test_begin_shutdown_prevents_eval_js(self):
        """After begin_shutdown(), _eval_js must not call evaluate_js."""
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        player.begin_shutdown()
        player._eval_js("some_code()")
        mock_window.evaluate_js.assert_not_called()

    def test_stop_skips_js_after_shutdown(self):
        """stop() should not call evaluate_js after begin_shutdown."""
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
        mock_window.evaluate_js.reset_mock()
        player.begin_shutdown()
        player.stop()
        mock_window.evaluate_js.assert_not_called()
        assert player.state == PlayerState.IDLE

    def test_notify_finished_no_eval_js(self):
        """notify_playback_finished must not call _eval_js (moved to JS)."""
        player = AudioPlayer()
        mock_window = MagicMock()
        player.set_webview_window(mock_window)
        with patch("src.audio_player.Path.exists", return_value=True):
            player.play("/fake/path.mp3")
        mock_window.evaluate_js.reset_mock()
        player.notify_playback_finished()
        mock_window.evaluate_js.assert_not_called()
        assert player.state == PlayerState.IDLE


class TestSimpleSignal:
    """Tests for SimpleSignal — connect, disconnect, and emit."""

    def test_connect_and_emit(self):
        """connect callback, emit → callback fires with correct args."""
        signal = SimpleSignal()
        cb = MagicMock()
        signal.connect(cb)
        signal.emit("arg1", "arg2")
        cb.assert_called_once_with("arg1", "arg2")

    def test_disconnect_single_callback(self):
        """connect 2 callbacks, disconnect one, emit → only remaining fires."""
        signal = SimpleSignal()
        cb1 = MagicMock()
        cb2 = MagicMock()
        signal.connect(cb1)
        signal.connect(cb2)
        signal.disconnect(cb1)
        signal.emit()
        cb1.assert_not_called()
        cb2.assert_called_once()

    def test_disconnect_all(self):
        """disconnect() with no args → clear all callbacks, none fire."""
        signal = SimpleSignal()
        cb1 = MagicMock()
        cb2 = MagicMock()
        signal.connect(cb1)
        signal.connect(cb2)
        signal.disconnect()
        signal.emit()
        cb1.assert_not_called()
        cb2.assert_not_called()
