"""Audio playback controller using QMediaPlayer. State machine: idle ↔ playing."""

from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QUrl, QObject, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class PlayerState(Enum):
    IDLE = auto()
    PLAYING = auto()


class AudioPlayer(QObject):
    """Play/stop audio files with state tracking."""

    state_changed = Signal(PlayerState)
    playback_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = PlayerState.IDLE
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.mediaStatusChanged.connect(self._on_status_changed)

    @property
    def state(self) -> PlayerState:
        return self._state

    def play(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._media_player.play()
        self._state = PlayerState.PLAYING
        self.state_changed.emit(self._state)

    def stop(self):
        if self._state == PlayerState.IDLE:
            return
        self._media_player.stop()
        self._state = PlayerState.IDLE
        self.state_changed.emit(self._state)

    def _on_status_changed(self, status):
        if status in (
            QMediaPlayer.MediaStatus.EndOfMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
            QMediaPlayer.MediaStatus.NoMedia,
        ):
            self._state = PlayerState.IDLE
            self.state_changed.emit(self._state)
            if status == QMediaPlayer.MediaStatus.EndOfMedia:
                self.playback_finished.emit()
