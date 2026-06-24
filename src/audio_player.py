"""Audio playback controller using HTML5 <audio> via pywebview bridge.

State machine: idle ↔ playing. Actual playback is handled by the browser's
HTMLAudioElement in the WebView frontend; this Python module is a thin bridge
that tracks state and communicates with JS via window.evaluate_js().

Transitional compatibility: When PySide6 is available, AudioPlayer inherits
from QObject and uses Qt Signals so existing UI code (main_window.py) works
unchanged. When PySide6 is not available, falls back to plain Python class
with SimpleSignal. This dual-mode support will be removed in T18 when the
PySide6 UI is replaced.
"""

import json
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Optional

# Transitional: use Qt base class + signals when PySide6 is available
try:
    from PySide6.QtCore import QObject, Signal as QtSignal

    _HAS_QT = True
except ImportError:
    _HAS_QT = False


class PlayerState(Enum):
    IDLE = auto()
    PLAYING = auto()


class SimpleSignal:
    """Minimal signal implementation compatible with Qt Signal.connect() API.

    Used only when PySide6 is not available. Provides .connect(callback)
    and .emit(*args) so code using PySide6 Signal pattern still works.
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


def _make_player_methods():
    """Shared method implementations for both Qt and non-Qt AudioPlayer."""

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
        """Called from JS when audio playback ends naturally."""
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
                pass

    return {
        "set_webview_window": set_webview_window,
        "play": play,
        "stop": stop,
        "notify_playback_finished": notify_playback_finished,
        "_set_state": _set_state,
        "_eval_js": _eval_js,
    }


_methods = _make_player_methods()

if _HAS_QT:

    class AudioPlayer(QObject):  # type: ignore[no-redef]
        """Play/stop audio files via HTML5 <audio> in WebView (Qt mode)."""

        state_changed = QtSignal(PlayerState)
        playback_finished = QtSignal()

        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self._state = PlayerState.IDLE
            self._window: Optional[object] = None
            self._current_file: Optional[Path] = None
            self.on_state_changed: Optional[Callable[[PlayerState], None]] = None
            self.on_playback_finished: Optional[Callable[[], None]] = None

        @property
        def state(self) -> PlayerState:
            return self._state

        @property
        def current_file(self) -> Optional[Path]:
            return self._current_file

        set_webview_window = _methods["set_webview_window"]
        play = _methods["play"]
        stop = _methods["stop"]
        notify_playback_finished = _methods["notify_playback_finished"]
        _set_state = _methods["_set_state"]
        _eval_js = _methods["_eval_js"]

else:

    class AudioPlayer:  # type: ignore[no-redef]
        """Play/stop audio files via HTML5 <audio> in WebView (non-Qt mode)."""

        def __init__(self, parent: object = None) -> None:
            self._state = PlayerState.IDLE
            self._window: Optional[object] = None
            self._current_file: Optional[Path] = None
            self.state_changed = SimpleSignal()
            self.playback_finished = SimpleSignal()
            self.on_state_changed: Optional[Callable[[PlayerState], None]] = None
            self.on_playback_finished: Optional[Callable[[], None]] = None

        @property
        def state(self) -> PlayerState:
            return self._state

        @property
        def current_file(self) -> Optional[Path]:
            return self._current_file

        set_webview_window = _methods["set_webview_window"]
        play = _methods["play"]
        stop = _methods["stop"]
        notify_playback_finished = _methods["notify_playback_finished"]
        _set_state = _methods["_set_state"]
        _eval_js = _methods["_eval_js"]
