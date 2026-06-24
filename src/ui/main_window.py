"""Main window: left-right splitter layout with voice panel and text panel."""

import asyncio
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QStatusBar,
)

from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, format_rate, format_pitch, make_output_filename
from src.audio_player import AudioPlayer, PlayerState
from src.ui.voice_panel import VoicePanel
from src.ui.text_panel import TextPanel


class TTSWorker(QThread):
    """Run edge-tts generation in background thread."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, voice, output_path, rate, pitch):
        super().__init__()
        self._text = text
        self._voice = voice
        self._output_path = output_path
        self._rate = rate
        self._pitch = pitch

    def run(self):
        try:
            engine = TTSEngine()
            asyncio.run(engine.generate(
                self._text, self._voice, self._output_path,
                rate=self._rate, pitch=self._pitch,
            ))
            self.finished.emit(self._output_path)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window with left-right split layout."""

    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._player = AudioPlayer(self)
        self._worker = None
        self._setup_ui()
        self._connect_signals()
        self._restore_state()

    def _setup_ui(self):
        self.setWindowTitle(self._i18n.t("app_title"))
        self.setMinimumSize(700, 500)
        self.resize(900, 600)

        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._voice_panel = VoicePanel(i18n=self._i18n)
        self._text_panel = TextPanel(i18n=self._i18n)

        splitter.addWidget(self._voice_panel)
        splitter.addWidget(self._text_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        # Language toggle
        self._lang_btn = QPushButton(self._i18n.t("lang_toggle"))
        self._lang_btn.setFixedSize(60, 28)
        self._lang_btn.clicked.connect(self._toggle_language)

        top_layout = QHBoxLayout()
        top_layout.addStretch()
        top_layout.addWidget(self._lang_btn)

        outer = QVBoxLayout(central)
        outer.addLayout(top_layout)
        outer.addWidget(splitter)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def _connect_signals(self):
        self._text_panel.preview_requested.connect(self._on_preview)
        self._text_panel.stop_requested.connect(self._on_stop)
        self._text_panel.export_requested.connect(self._on_export)
        self._player.state_changed.connect(self._on_player_state_changed)
        self._player.playback_finished.connect(
            lambda: self._text_panel.set_status(self._i18n.t("status_ready"))
        )

    def _restore_state(self):
        output_dir = self._config.get("output_dir")
        if output_dir:
            self._voice_panel.set_output_dir(output_dir)

        rate = self._config.get("rate")
        if rate:
            try:
                val = int(rate.replace("%", "").replace("+", ""))
                self._voice_panel._rate_slider.setValue(val)
            except ValueError:
                pass

        pitch = self._config.get("pitch")
        if pitch:
            try:
                val = int(pitch.replace("Hz", "").replace("+", ""))
                self._voice_panel._pitch_slider.setValue(val)
            except ValueError:
                pass

    def _on_preview(self):
        text = self._text_panel.get_text()
        voice = self._voice_panel.current_voice()
        if not text or not voice:
            return
        self._text_panel.set_status(self._i18n.t("status_generating"))
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        self._run_tts(text, voice, tmp.name, is_preview=True)

    def _on_export(self):
        text = self._text_panel.get_text()
        voice = self._voice_panel.current_voice()
        if not text or not voice:
            return
        output_dir = self._voice_panel._output_dir
        filename = make_output_filename(text)
        output_path = str(Path(output_dir) / filename)
        self._text_panel.set_status(self._i18n.t("status_generating"))
        self._run_tts(text, voice, output_path, is_preview=False)

    def _run_tts(self, text, voice, output_path, is_preview):
        rate = format_rate(self._voice_panel.rate_value())
        pitch = format_pitch(self._voice_panel.pitch_value())
        self._worker = TTSWorker(text, voice, output_path, rate, pitch)
        if is_preview:
            self._worker.finished.connect(self._on_preview_ready)
        else:
            self._worker.finished.connect(self._on_export_ready)
        self._worker.error.connect(self._on_tts_error)
        self._worker.start()

    def _on_preview_ready(self, file_path):
        self._text_panel.set_status(self._i18n.t("status_playing"))
        self._player.play(file_path)

    def _on_export_ready(self, file_path):
        filename = Path(file_path).name
        self._text_panel.set_status(
            self._i18n.t("status_exported", filename=filename)
        )

    def _on_tts_error(self, error_msg):
        self._text_panel.set_status(
            self._i18n.t("error_export_failed", error=error_msg)
        )

    def _on_stop(self):
        self._player.stop()

    def _on_player_state_changed(self, state):
        self._text_panel.set_playing(state == PlayerState.PLAYING)

    def _toggle_language(self):
        current = self._i18n.current_language
        new_lang = "en-US" if current == "zh-TW" else "zh-TW"
        self._i18n.set_language(new_lang)
        self._config.set("language", new_lang)
        self._lang_btn.setText(self._i18n.t("lang_toggle"))
        self.setWindowTitle(self._i18n.t("app_title"))
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def closeEvent(self, event):
        self._config.set("rate", format_rate(self._voice_panel.rate_value()))
        self._config.set("pitch", format_pitch(self._voice_panel.pitch_value()))
        self._config.save()
        super().closeEvent(event)
