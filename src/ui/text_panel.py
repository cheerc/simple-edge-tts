"""Right panel: text input area, preview/stop/export buttons, status display."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QLabel,
)

from src.i18n import I18n


class TextPanel(QWidget):
    """Right panel containing text input and action buttons."""

    preview_requested = Signal()
    stop_requested = Signal()
    export_requested = Signal()

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Text input
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(self._i18n.t("text_placeholder"))
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._preview_btn = QPushButton(f"▶ {self._i18n.t('preview')}")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self.preview_requested.emit)
        btn_layout.addWidget(self._preview_btn)

        self._stop_btn = QPushButton(f"⏹ {self._i18n.t('stop')}")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        btn_layout.addWidget(self._stop_btn)

        self._export_btn = QPushButton(f"💾 {self._i18n.t('export_mp3')}")
        self._export_btn.setObjectName("exportButton")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_requested.emit)
        btn_layout.addWidget(self._export_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Status
        self._status_label = QLabel(self._i18n.t("status_ready"))
        layout.addWidget(self._status_label)

    def _on_text_changed(self):
        has_text = bool(self._text_edit.toPlainText().strip())
        self._preview_btn.setEnabled(has_text)
        self._export_btn.setEnabled(has_text)

    def get_text(self) -> str:
        """Return the current text content."""
        return self._text_edit.toPlainText()

    def set_status(self, text: str):
        """Update the status label text."""
        self._status_label.setText(text)

    def set_playing(self, playing: bool):
        """Toggle button states based on playback state."""
        self._stop_btn.setEnabled(playing)
        self._preview_btn.setEnabled(not playing and bool(self.get_text().strip()))

    def update_texts(self):
        """Called when language changes — re-apply all i18n strings."""
        pass
