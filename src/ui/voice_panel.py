"""Left panel: voice selection with search, rate/pitch sliders, output folder picker."""


from pathlib import Path

from PySide6.QtCore import Signal, Qt, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QComboBox, QLineEdit,
    QSlider, QLabel, QHBoxLayout, QPushButton, QFileDialog,
)

from src.i18n import I18n
from src.tts_engine import TTSEngine


class VoiceLoaderThread(QThread):
    """Load available TTS voices in a background thread to avoid blocking UI."""

    voices_loaded = Signal(list)
    load_failed = Signal(str)

    def run(self):
        try:
            engine = TTSEngine()
            grouped = engine.get_grouped_voices_sync()  # already calls asyncio.run internally
            # Flatten grouped OrderedDict into a flat list for the combo
            voices = []
            for locale_voices in grouped.values():
                voices.extend(locale_voices)
            self.voices_loaded.emit(voices)
        except Exception as e:
            self.load_failed.emit(str(e))


class VoicePanel(QWidget):
    """Left panel containing voice selection, parameter sliders, and output settings."""

    voice_changed = Signal(str)
    rate_changed = Signal(int)
    pitch_changed = Signal(int)
    output_dir_changed = Signal(str)

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._output_dir = str(Path.home() / "Desktop")
        self._all_voices: list[dict] = []
        self._loading = False
        self._loader_thread = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Voice selection group
        voice_group = QGroupBox(self._i18n.t("voice_selection"))
        voice_layout = QVBoxLayout(voice_group)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(self._i18n.t("search_voice"))
        self._search_input.textChanged.connect(self._filter_voices)
        voice_layout.addWidget(self._search_input)
        self._voice_combo = QComboBox()
        self._voice_combo.currentTextChanged.connect(self._on_voice_changed)
        voice_layout.addWidget(self._voice_combo)
        layout.addWidget(voice_group)

        # Parameters group
        param_group = QGroupBox(self._i18n.t("parameters"))
        param_layout = QVBoxLayout(param_group)

        # Rate slider
        self._rate_label = QLabel(f"{self._i18n.t('rate')}: +0%")
        param_layout.addWidget(self._rate_label)
        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(-50, 100)
        self._rate_slider.setValue(0)
        self._rate_slider.valueChanged.connect(self._on_rate_changed)
        param_layout.addWidget(self._rate_slider)

        # Pitch slider
        self._pitch_label = QLabel(f"{self._i18n.t('pitch')}: +0Hz")
        param_layout.addWidget(self._pitch_label)
        self._pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-50, 50)
        self._pitch_slider.setValue(0)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        param_layout.addWidget(self._pitch_slider)

        layout.addWidget(param_group)

        # Output settings group
        output_group = QGroupBox(self._i18n.t("output_settings"))
        output_layout = QVBoxLayout(output_group)
        self._dir_label = QLabel(self._output_dir)
        self._dir_label.setWordWrap(True)
        output_layout.addWidget(self._dir_label)
        dir_btn = QPushButton(self._i18n.t("choose_folder"))
        dir_btn.clicked.connect(self._choose_folder)
        output_layout.addWidget(dir_btn)
        layout.addWidget(output_group)

        layout.addStretch()

    def _on_voice_changed(self, text: str):
        """Guard against programmatic combo changes during loading/filtering."""
        if not self._loading:
            self.voice_changed.emit(text)

    def _on_rate_changed(self, value: int):
        sign = "+" if value >= 0 else ""
        self._rate_label.setText(f"{self._i18n.t('rate')}: {sign}{value}%")
        self.rate_changed.emit(value)

    def _on_pitch_changed(self, value: int):
        sign = "+" if value >= 0 else ""
        self._pitch_label.setText(f"{self._i18n.t('pitch')}: {sign}{value}Hz")
        self.pitch_changed.emit(value)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "", self._output_dir)
        if folder:
            self._output_dir = folder
            self._dir_label.setText(folder)
            self.output_dir_changed.emit(folder)

    def _filter_voices(self, text: str):
        """Filter voice combo items by search text — clear and repopulate."""
        self._loading = True
        try:
            self._voice_combo.clear()
            search = text.lower()
            for v in self._all_voices:
                name = v.get("ShortName", "")
                if not search or search in name.lower():
                    self._voice_combo.addItem(name, v)
        finally:
            self._loading = False

    def load_voices_async(self):
        """Start loading voices in a background thread."""
        self._loader_thread = VoiceLoaderThread()
        self._loader_thread.voices_loaded.connect(self._on_voices_loaded)
        self._loader_thread.load_failed.connect(
            lambda e: None  # Silently handle — voices remain empty
        )
        self._loader_thread.start()

    def _on_voices_loaded(self, voices: list[dict]):
        """Callback when voice loading thread completes."""
        self.set_voices(voices)

    def set_voices(self, voices: list[dict]):
        """Populate the voice combo with a list of voice dictionaries."""
        self._loading = True
        try:
            self._all_voices = voices
            self._voice_combo.clear()
            for v in voices:
                self._voice_combo.addItem(v["ShortName"], v)
        finally:
            self._loading = False

    def set_output_dir(self, path: str):
        """Set the output directory path and update label."""
        self._output_dir = path
        self._dir_label.setText(path)

    def rate_value(self) -> int:
        """Return the current rate slider value."""
        return self._rate_slider.value()

    def pitch_value(self) -> int:
        """Return the current pitch slider value."""
        return self._pitch_slider.value()

    def current_voice(self) -> str:
        """Return the currently selected voice short name."""
        return self._voice_combo.currentText()

    def update_texts(self):
        """Called when language changes — re-apply all i18n strings."""
        pass
