"""Settings Dialog: language switching.

Rate/pitch sliders and output dir are in voice_panel.py per spec §3.1 layout.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QDialogButtonBox,
)
from src.config_manager import ConfigManager
from src.i18n import I18n


class SettingsDialog(QDialog):
    """Modal dialog for language selection."""
    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(self._i18n.t("settings_title"))
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Language dropdown
        lang_layout = QHBoxLayout()
        self._lang_label = QLabel(self._i18n.t("language"))
        lang_layout.addWidget(self._lang_label)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("繁體中文", "zh-TW")
        self._lang_combo.addItem("English", "en-US")

        # Set current language
        lang = self._config.get("language")
        idx = self._lang_combo.findData(lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

        lang_layout.addWidget(self._lang_combo)
        layout.addLayout(lang_layout)

        # Dialog Buttons
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self._btn_box.button(QDialogButtonBox.StandardButton.Save).setText(self._i18n.t("save"))
        self._btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(self._i18n.t("cancel"))
        self._btn_box.accepted.connect(self._on_save_clicked)
        self._btn_box.rejected.connect(self.reject)
        layout.addWidget(self._btn_box)

    def _on_save_clicked(self):
        self._save_config()
        self.accept()

    def _save_config(self):
        self._config.set("language", self._lang_combo.currentData())
        self._config.save()
