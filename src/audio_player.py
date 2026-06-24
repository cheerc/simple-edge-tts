"""Audio playback controller using HTML5 <audio> via pywebview bridge.

State machine: idle ↔ playing. Actual playback is handled by the browser's
HTMLAudioElement in the WebView frontend; this Python module is a thin bridge
that tracks state and communicates with JS via window.evaluate_js().

Works in headless/test mode (no WebView window) — state tracking still
functions, JS calls are simply skipped.
"""

import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional


class PlayerState(Enum):
    IDLE = auto()
    PLAYING = auto()


class SimpleSignal:
    """Minimal signal implementation compatible with Qt Signal.connect() API.

    Provides .connect(callback) and .emit(*args) so existing code using
    PySide6 Signal pattern continues to work after migrating away from Qt.
    """

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]) -> None:
        """Register a callback to be called when the signal is emitted."""
        self._callbacks.append(callback)

    def disconnect(self, callback: Optional[Callable[..., Any]] = None) -> None:
        """Remove a callback. If None, remove all callbacks."""
        if callback is None:
            self._callbacks.clear()
        else:
            self._callbacks = [cb for cb in self._callbacks if cb is not callback]

    def emit(self, *args: Any) -> None:
        """Emit the signal, calling all connected callbacks."""
        for callback in self._callbacks:
            callback(*args)


class AudioPlayer:
    """Play/stop audio files via HTML5 <audio> in WebView.

    Usage:
        player = AudioPlayer()
        player.set_webview_window(webview_window)  # after webview starts
        player.play("/path/to/file.mp3")
        player.stop()

    Signal-compatible API:
        player.state_changed.connect(on_state_changed)  # Qt-style
        player.playback_finished.connect(on_finished)
    """

    def __init__(self, parent: object = None) -> None:
        # parent is accepted for backward compatibility with PySide6 code
        # (e.g. AudioPlayer(self) in QWidget subclasses) but is not used.
        self._state = PlayerState.IDLE
        self._window: Optional[object] = None
        self._current_file: Optional[Path] = None

        # Qt-compatible signals (use .connect() / .emit())
        self.state_changed = SimpleSignal()
        self.playback_finished = SimpleSignal()

        # Simple callback API (alternative to signals)
        self.on_state_changed: Optional[Callable[[PlayerState], None]] = None
        self.on_playback_finished: Optional[Callable[[], None]] = None

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def current_file(self) -> Optional[Path]:
        return self._current_file

    def set_webview_window(self, window: object) -> None:
        """Set the pywebview window for JS bridge communication."""
        self._window = window

    def play(self, file_path: str) -> None:
        """Play an audio file. Requires file to exist."""
        path = Path(file_path)
        if not path.exists():
            return

        resolved = path.resolve()
        self._current_file = resolved
        self._set_state(PlayerState.PLAYING)

        if self._window is not None:
            # Send file path to JS frontend for HTML5 <audio> playback.
            # The pywebview HTTP server serves local files, so we convert
            # the absolute path to a URL the frontend can fetch.
            path_str = json.dumps(str(resolved))
            self._eval_js(f"window.audioPlayerBridge.playAudio({path_str})")

    def stop(self) -> None:
        """Stop current playback."""
        if self._state == PlayerState.IDLE:
            return

        self._current_file = None
        self._set_state(PlayerState.IDLE)

        if self._window is not None:
            self._eval_js("window.audioPlayerBridge.stopAudio()")

    def notify_playback_finished(self) -> None:
        """Called from JS when audio playback ends naturally.

        This method is exposed to JS via pywebview's window.expose()
        so the frontend can notify Python when <audio> 'ended' fires.
        """
        self._current_file = None
        self._set_state(PlayerState.IDLE)
        self.playback_finished.emit()
        if self.on_playback_finished is not None:
            self.on_playback_finished()

    def _set_state(self, new_state: PlayerState) -> None:
        self._state = new_state
        self.state_changed.emit(new_state)
        if self.on_state_changed is not None:
            self.on_state_changed(new_state)

    def _eval_js(self, js_code: str) -> None:
        """Safely evaluate JS in the WebView window."""
        if self._window is not None:
            try:
                self._window.evaluate_js(js_code)  # type: ignore[union-attr]
            except Exception:
                # WebView may not be ready yet; silently skip
                pass
