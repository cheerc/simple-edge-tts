# Wave 3 UI Components Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PySide6 UI for simple-edge-tts Wave 3, containing the Main Window (T7), Settings Dialog (T8), and System Tray (T9) with follower OS theming and full i18n support.

**Architecture:** Use PySide6 layouts and widgets. Pure UI logic and bindings are tested using `pytest-qt`. QThread is used to execute edge-tts generation asynchronously to avoid blocking the Qt GUI thread. ConfigManager and I18n are bound to UI components.

**Tech Stack:** Python 3.11+, PySide6, edge-tts, pytest, pytest-qt

---

## File Structure

| File | Responsibility |
|---|---|
| `src/ui/__init__.py` | Package marker |
| `src/ui/theme.py` | Light/dark theme detection and QSS styling |
| `src/ui/main_window.py` | QMainWindow with toolbar, text editor, voice selectors, and TTS controls |
| `src/ui/settings_dialog.py` | Settings dialog containing rate/pitch sliders, output dir picker, and language switching |
| `src/ui/system_tray.py` | System tray icon, minimize-to-tray behavior, context menu, and notifications |
| `src/app.py` | Application setup (theme listener, high-DPI) |
| `tests/test_ui/test_main_window.py` | Tests for Main Window UI logic, bindings, and states |
| `tests/test_ui/test_settings_dialog.py` | Tests for Settings Dialog sliders, directory picker, and language switching |
| `tests/test_ui/test_system_tray.py` | Tests for System Tray icon states and context menus |

---

## Task 7: Main Window & Theme System

**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/theme.py`
- Create: `src/ui/main_window.py`
- Create: `tests/test_ui/test_main_window.py`
- Modify: `src/app.py`
- Modify: `src/main.py`
- Modify: `src/resources/translations/zh-TW.json`
- Modify: `src/resources/translations/en-US.json`

- [ ] **Step 1: Create `src/ui/__init__.py`**

An empty file to mark the `src/ui` directory as a package.

- [ ] **Step 2: Add translation keys for new settings dialog and tray options**

Update translation files to support Settings and Tray menus.

Modify `src/resources/translations/zh-TW.json`:
```json
{
  "app_title": "simple-edge-tts",
  "voice_selection": "聲音選擇",
  "search_voice": "搜尋聲音...",
  "parameters": "參數設定",
  "rate": "語速 (Rate)",
  "pitch": "音調 (Pitch)",
  "output_settings": "輸出設定",
  "choose_folder": "選擇資料夾",
  "text_placeholder": "輸入要轉換的文字...",
  "preview": "試聽",
  "stop": "停止",
  "export_mp3": "匯出 MP3",
  "status_ready": "就緒",
  "status_generating": "產生語音中...",
  "status_playing": "播放中...",
  "status_exported": "匯出完成：{filename}",
  "error_no_internet": "無法連線到 TTS 服務，請檢查網路連線",
  "error_export_failed": "匯出失敗：{error}",
  "error_folder_not_writable": "無法寫入資料夾，請選擇其他位置",
  "voice_group_tw": "台灣中文",
  "voice_group_en": "English",
  "voice_group_other": "其他",
  "lang_toggle": "EN",
  "settings": "設定",
  "settings_title": "系統設定",
  "language": "語言 (Language)",
  "save": "儲存",
  "cancel": "取消",
  "show_main": "顯示主視窗",
  "exit": "結束",
  "tray_tooltip": "simple-edge-tts 語音合成",
  "export_success_title": "匯出成功",
  "export_success_msg": "已成功匯出 MP3 至：{path}"
}
```

Modify `src/resources/translations/en-US.json`:
```json
{
  "app_title": "simple-edge-tts",
  "voice_selection": "Voice Selection",
  "search_voice": "Search voice...",
  "parameters": "Settings Parameters",
  "rate": "Rate",
  "pitch": "Pitch",
  "output_settings": "Output Settings",
  "choose_folder": "Choose Folder",
  "text_placeholder": "Type text here to convert...",
  "preview": "Preview",
  "stop": "Stop",
  "export_mp3": "Export MP3",
  "status_ready": "Ready",
  "status_generating": "Generating speech...",
  "status_playing": "Playing...",
  "status_exported": "Exported: {filename}",
  "error_no_internet": "Cannot connect to TTS service, please check internet",
  "error_export_failed": "Export failed: {error}",
  "error_folder_not_writable": "Cannot write to output folder, please choose another",
  "voice_group_tw": "Taiwan Chinese",
  "voice_group_en": "English",
  "voice_group_other": "Others",
  "lang_toggle": "繁中",
  "settings": "Settings",
  "settings_title": "Settings",
  "language": "Language",
  "save": "Save",
  "cancel": "Cancel",
  "show_main": "Show Window",
  "exit": "Exit",
  "tray_tooltip": "simple-edge-tts TTS Synthesizer",
  "export_success_title": "Export Succeeded",
  "export_success_msg": "Successfully exported MP3 to: {path}"
}
```

- [ ] **Step 3: Implement `src/ui/theme.py`**

Create `src/ui/theme.py`:
```python
"""Theme definitions and helper to apply OS light/dark modes."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

LIGHT_QSS = """
QMainWindow {
    background-color: #f5f5f7;
}
QTextEdit {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 12px;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 6px;
}
QPushButton {
    background-color: #007aff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #0066d6;
}
QPushButton:disabled {
    background-color: #d2d2d7;
    color: #86868b;
}
"""

DARK_QSS = """
QMainWindow {
    background-color: #1c1c1e;
}
QTextEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    padding: 12px;
}
QComboBox {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 6px;
}
QPushButton {
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
}
QPushButton:hover {
    background-color: #409cff;
}
QPushButton:disabled {
    background-color: #3a3a3c;
    color: #636366;
}
"""

def is_dark_mode() -> bool:
    hints = QApplication.instance().styleHints()
    if hasattr(hints, "colorScheme"):
        return hints.colorScheme() == Qt.ColorScheme.Dark
    palette = QApplication.instance().palette()
    return palette.color(QPalette.ColorRole.Window).lightness() < 128

def apply_theme(app: QApplication):
    qss = DARK_QSS if is_dark_mode() else LIGHT_QSS
    app.setStyleSheet(qss)
```

- [ ] **Step 4: Write failing tests for MainWindow**

Create `tests/test_ui/test_main_window.py`:
```python
"""Tests for main_window — layout, toolbar, widgets, i18n, worker thread integration."""

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from src.ui.main_window import MainWindow
from src.i18n import I18n
from src.config_manager import ConfigManager

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"

@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)

@pytest.fixture
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)

def test_mainwindow_creates(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    assert win is not None
    assert "simple-edge-tts" in win.windowTitle()

def test_mainwindow_buttons_initially_disabled(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    assert not win._preview_btn.isEnabled()
    assert not win._export_btn.isEnabled()
    assert not win._stop_btn.isEnabled()

def test_mainwindow_buttons_enabled_when_text_present(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    win._text_edit.setPlainText("Test speech")
    assert win._preview_btn.isEnabled()
    assert win._export_btn.isEnabled()

def test_mainwindow_text_cleared_disables_buttons(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    win._text_edit.setPlainText("Test speech")
    win._text_edit.clear()
    assert not win._preview_btn.isEnabled()
    assert not win._export_btn.isEnabled()
```

- [ ] **Step 5: Run tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_main_window.py -v`
Expected: FAIL (No module named `src.ui.main_window`)

- [ ] **Step 6: Implement `src/ui/main_window.py`**

Create `src/ui/main_window.py`:
```python
"""Main window: toolbar settings action, voice selectors, input area, and export controls."""

import asyncio
import tempfile
from pathlib import Path
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QComboBox, QLineEdit, QPushButton, QStatusBar, QMessageBox,
    QToolBar, QLabel
)
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, make_output_filename
from src.audio_player import AudioPlayer, PlayerState

class TTSWorker(QThread):
    """QThread to handle edge-tts asynchronous speech generation."""
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text: str, voice: str, output_path: str, rate: str, pitch: str):
        super().__init__()
        self.text = text
        self.voice = voice
        self.output_path = output_path
        self.rate = rate
        self.pitch = pitch

    def run(self):
        try:
            engine = TTSEngine()
            asyncio.run(engine.generate(
                self.text, self.voice, self.output_path,
                rate=self.rate, pitch=self.pitch
            ))
            self.finished.emit(self.output_path)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    """Main window of simple-edge-tts."""
    language_changed = Signal(str)

    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._player = AudioPlayer(self)
        self._tts_worker = None
        self._all_voices = []

        self._setup_ui()
        self._connect_signals()
        self._load_voices()
        self._restore_state()

    def _setup_ui(self):
        self.setWindowTitle(self._i18n.t("app_title"))
        self.setMinimumSize(700, 500)
        self.resize(self._config.get("window_geometry")["w"], self._config.get("window_geometry")["h"])

        # Toolbar
        self._toolbar = QToolBar("Main Toolbar", self)
        self._toolbar.setMovable(False)
        self.addToolBar(self._toolbar)

        # Toolbar Settings Action
        self._settings_action = self._toolbar.addAction(self._i18n.t("settings"))
        self._settings_action.triggered.connect(self._on_open_settings)

        self._toolbar.addSeparator()

        # Language quick toggle action
        self._lang_action = self._toolbar.addAction(self._i18n.t("lang_toggle"))
        self._lang_action.triggered.connect(self._toggle_language)

        # Central Widget Layout
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Voice Selector Row
        voice_layout = QHBoxLayout()
        self._voice_label = QLabel(self._i18n.t("voice_selection"))
        voice_layout.addWidget(self._voice_label)

        self._voice_search = QLineEdit()
        self._voice_search.setPlaceholderText(self._i18n.t("search_voice"))
        self._voice_search.textChanged.connect(self._filter_voices)
        voice_layout.addWidget(self._voice_search)

        self._voice_combo = QComboBox()
        self._voice_combo.currentTextChanged.connect(self._on_voice_changed)
        voice_layout.addWidget(self._voice_combo)
        voice_layout.setStretch(2, 2)
        main_layout.addLayout(voice_layout)

        # Text input editor
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(self._i18n.t("text_placeholder"))
        self._text_edit.textChanged.connect(self._on_text_changed)
        main_layout.addWidget(self._text_edit)

        # Button Row
        btn_layout = QHBoxLayout()
        self._preview_btn = QPushButton(f"▶ {self._i18n.t('preview')}")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self._on_preview)
        btn_layout.addWidget(self._preview_btn)

        self._stop_btn = QPushButton(f"⏹ {self._i18n.t('stop')}")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._on_stop)
        btn_layout.addWidget(self._stop_btn)

        self._export_btn = QPushButton(f"💾 {self._i18n.t('export_mp3')}")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        btn_layout.addWidget(self._export_btn)
        main_layout.addLayout(btn_layout)

        # Status Bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def _connect_signals(self):
        self._player.state_changed.connect(self._on_player_state_changed)
        self._player.playback_finished.connect(
            lambda: self.statusBar().showMessage(self._i18n.t("status_ready"))
        )

    def _load_voices(self):
        try:
            engine = TTSEngine()
            grouped = engine.get_grouped_voices_sync()
            self._voice_combo.clear()
            self._all_voices = []

            # Populate combo box with grouping tags
            for group, voices in grouped.items():
                group_name = self._i18n.t(f"voice_group_{group.lower().replace('-', '_')}")
                if "voice_group" in group_name: # fallback
                    group_name = group

                for v in voices:
                    name = v["ShortName"]
                    gender = v.get("Gender", "")
                    label = f"{name} ({gender}) - {group_name}"
                    self._all_voices.append({"label": label, "name": name, "raw": v})
                    self._voice_combo.addItem(label, name)
        except Exception as e:
            self.statusBar().showMessage(f"Load voices failed: {e}")

    def _restore_state(self):
        last_voice = self._config.get("last_voice")
        if last_voice:
            idx = self._voice_combo.findData(last_voice)
            if idx >= 0:
                self._voice_combo.setCurrentIndex(idx)

    def _filter_voices(self, search_text: str):
        self._voice_combo.clear()
        search_text = search_text.lower()
        for item in self._all_voices:
            if search_text in item["label"].lower() or search_text in item["name"].lower():
                self._voice_combo.addItem(item["label"], item["name"])

    def _on_text_changed(self):
        has_text = bool(self._text_edit.toPlainText().strip())
        self._preview_btn.setEnabled(has_text and self._player.state != PlayerState.PLAYING)
        self._export_btn.setEnabled(has_text and self._player.state != PlayerState.PLAYING)

    def _on_voice_changed(self, text: str):
        voice = self._voice_combo.currentData()
        if voice:
            self._config.set("last_voice", voice)
            self._config.save()

    def _on_preview(self):
        text = self._text_edit.toPlainText().strip()
        voice = self._voice_combo.currentData()
        if not text or not voice:
            return

        self.statusBar().showMessage(self._i18n.t("status_generating"))
        self._preview_btn.setEnabled(False)
        self._export_btn.setEnabled(False)

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        rate = self._config.get("rate")
        pitch = self._config.get("pitch")

        self._tts_worker = TTSWorker(text, voice, tmp.name, rate, pitch)
        self._tts_worker.finished.connect(self._on_preview_ready)
        self._tts_worker.error.connect(self._on_tts_error)
        self._tts_worker.start()

    def _on_preview_ready(self, file_path: str):
        self.statusBar().showMessage(self._i18n.t("status_playing"))
        self._player.play(file_path)

    def _on_export(self):
        text = self._text_edit.toPlainText().strip()
        voice = self._voice_combo.currentData()
        if not text or not voice:
            return

        output_dir = Path(self._config.get("output_dir"))
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                QMessageBox.warning(self, "Error", self._i18n.t("error_folder_not_writable"))
                return

        filename = make_output_filename(text)
        output_path = output_dir / filename

        self.statusBar().showMessage(self._i18n.t("status_generating"))
        self._preview_btn.setEnabled(False)
        self._export_btn.setEnabled(False)

        rate = self._config.get("rate")
        pitch = self._config.get("pitch")

        self._tts_worker = TTSWorker(text, voice, str(output_path), rate, pitch)
        self._tts_worker.finished.connect(self._on_export_ready)
        self._tts_worker.error.connect(self._on_tts_error)
        self._tts_worker.start()

    def _on_export_ready(self, file_path: str):
        filename = Path(file_path).name
        self.statusBar().showMessage(self._i18n.t("status_exported", filename=filename))
        self._on_text_changed()

    def _on_tts_error(self, error_msg: str):
        QMessageBox.critical(self, "TTS Error", self._i18n.t("error_export_failed", error=error_msg))
        self.statusBar().showMessage(self._i18n.t("status_ready"))
        self._on_text_changed()

    def _on_stop(self):
        self._player.stop()

    def _on_player_state_changed(self, state: PlayerState):
        is_playing = state == PlayerState.PLAYING
        self._stop_btn.setEnabled(is_playing)
        self._on_text_changed()

    def _on_open_settings(self):
        # Implementation in Task 8
        pass

    def _toggle_language(self):
        current = self._i18n.current_language
        new_lang = "en-US" if current == "zh-TW" else "zh-TW"
        self.set_language(new_lang)

    def set_language(self, language: str):
        self._i18n.set_language(language)
        self._config.set("language", language)
        self._config.save()
        self.language_changed.emit(language)
        self.update_ui_texts()

    def update_ui_texts(self):
        self.setWindowTitle(self._i18n.t("app_title"))
        self._settings_action.setText(self._i18n.t("settings"))
        self._lang_action.setText(self._i18n.t("lang_toggle"))
        self._voice_label.setText(self._i18n.t("voice_selection"))
        self._voice_search.setPlaceholderText(self._i18n.t("search_voice"))
        self._text_edit.setPlaceholderText(self._i18n.t("text_placeholder"))
        self._preview_btn.setText(f"▶ {self._i18n.t('preview')}")
        self._stop_btn.setText(f"⏹ {self._i18n.t('stop')}")
        self._export_btn.setText(f"💾 {self._i18n.t('export_mp3')}")
        self.statusBar().showMessage(self._i18n.t("status_ready"))
        self._load_voices()

    def closeEvent(self, event):
        # Save window geometry
        geom = self.geometry()
        self._config.set("window_geometry", {"x": geom.x(), "y": geom.y(), "w": geom.width(), "h": geom.height()})
        self._config.save()
        super().closeEvent(event)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_main_window.py -v`
Expected: PASS

- [ ] **Step 8: Update `src/app.py`**

Modify `src/app.py`:
```python
"""Application-level setup: theme, high-DPI, font."""

import sys
from PySide6.QtWidgets import QApplication
from src.ui.theme import apply_theme

def create_app(argv=None) -> QApplication:
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    app.setApplicationName("simple-edge-tts")
    app.setApplicationVersion("0.1.0")
    apply_theme(app)

    # Listen for OS theme changes
    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda: apply_theme(app))

    return app
```

- [ ] **Step 9: Update `src/main.py`**

Modify `src/main.py`:
```python
"""Entry point for simple-edge-tts application."""

import sys
from pathlib import Path
from src.app import create_app
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.ui.main_window import MainWindow

TRANSLATIONS_DIR = Path(__file__).parent / "resources" / "translations"

def main():
    app = create_app()
    config = ConfigManager()
    i18n = I18n(config.get("language"), translations_dir=TRANSLATIONS_DIR)
    window = MainWindow(i18n=i18n, config=config)
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

- [ ] **Step 10: Commit**

```bash
git add src/ui/__init__.py src/ui/theme.py src/ui/main_window.py src/app.py src/main.py src/resources/translations/ tests/test_ui/test_main_window.py
git commit -m "feat: main window QMainWindow setup with follower theme and toolbar integration"
```

---

## Task 8: Settings Dialog

**Files:**
- Create: `src/ui/settings_dialog.py`
- Create: `tests/test_ui/test_settings_dialog.py`
- Modify: `src/ui/main_window.py`

- [ ] **Step 1: Write failing tests for SettingsDialog**

Create `tests/test_ui/test_settings_dialog.py`:
```python
"""Tests for SettingsDialog — sliders, output folder selection, language changing."""

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from src.ui.settings_dialog import SettingsDialog
from src.i18n import I18n
from src.config_manager import ConfigManager

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"

@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)

@pytest.fixture
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)

def test_settings_dialog_initializes_with_config(qtbot, i18n, config):
    config.set("rate", "+10%")
    config.set("pitch", "-5Hz")
    dialog = SettingsDialog(i18n=i18n, config=config)
    qtbot.addWidget(dialog)

    assert dialog._rate_slider.value() == 10
    assert dialog._pitch_slider.value() == -5

def test_settings_dialog_slider_resets_on_double_click(qtbot, i18n, config):
    dialog = SettingsDialog(i18n=i18n, config=config)
    qtbot.addWidget(dialog)

    dialog._rate_slider.setValue(20)
    # Simulate double click or direct trigger of event handler
    dialog._on_rate_slider_double_clicked(None)
    assert dialog._rate_slider.value() == 0

def test_settings_dialog_save_persists_config(qtbot, i18n, config):
    dialog = SettingsDialog(i18n=i18n, config=config)
    qtbot.addWidget(dialog)

    dialog._rate_slider.setValue(30)
    dialog._pitch_slider.setValue(15)
    dialog._save_config()

    assert config.get("rate") == "+30%"
    assert config.get("pitch") == "+15Hz"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_settings_dialog.py -v`
Expected: FAIL (No module named `src.ui.settings_dialog`)

- [ ] **Step 3: Implement `src/ui/settings_dialog.py`**

Create `src/ui/settings_dialog.py`:
```python
"""Settings Dialog: Sliders for rate and pitch, output dir picker, and language switching."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QFileDialog, QComboBox, QDialogButtonBox
)
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import format_rate, format_pitch

class DoubleClickSlider(QSlider):
    """Custom slider that catches double clicks to reset value to 0."""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

    def mouseDoubleClickEvent(self, event):
        self.setValue(0)
        super().mouseDoubleClickEvent(event)

class SettingsDialog(QDialog):
    """Modal dialog for rate/pitch settings, directory picking, and language choice."""
    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._output_dir = self._config.get("output_dir")
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        self.setWindowTitle(self._i18n.t("settings_title"))
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Rate Slider Block
        rate_layout = QVBoxLayout()
        self._rate_label = QLabel(self._i18n.t("rate"))
        rate_layout.addWidget(self._rate_label)

        self._rate_slider = DoubleClickSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(-50, 100)
        self._rate_slider.setValue(0)
        self._rate_slider.valueChanged.connect(self._on_rate_changed)
        rate_layout.addWidget(self._rate_slider)
        layout.addLayout(rate_layout)

        # Pitch Slider Block
        pitch_layout = QVBoxLayout()
        self._pitch_label = QLabel(self._i18n.t("pitch"))
        pitch_layout.addWidget(self._pitch_label)

        self._pitch_slider = DoubleClickSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-50, 50)
        self._pitch_slider.setValue(0)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        pitch_layout.addWidget(self._pitch_slider)
        layout.addLayout(pitch_layout)

        # Output Dir Block
        output_layout = QVBoxLayout()
        self._output_title = QLabel(self._i18n.t("output_settings"))
        output_layout.addWidget(self._output_title)

        dir_row = QHBoxLayout()
        self._dir_path_label = QLabel(self._output_dir)
        self._dir_path_label.setWordWrap(True)
        dir_row.addWidget(self._dir_path_label)

        self._dir_btn = QPushButton(self._i18n.t("choose_folder"))
        self._dir_btn.clicked.connect(self._choose_folder)
        dir_row.addWidget(self._dir_btn)
        output_layout.addLayout(dir_row)
        layout.addLayout(output_layout)

        # Language dropdown choice
        lang_layout = QHBoxLayout()
        self._lang_label = QLabel(self._i18n.t("language"))
        lang_layout.addWidget(self._lang_label)

        self._lang_combo = QComboBox()
        self._lang_combo.addItem("繁體中文", "zh-TW")
        self._lang_combo.addItem("English", "en-US")
        lang_layout.addWidget(self._lang_combo)
        layout.addLayout(lang_layout)

        # Dialog Buttons
        self._btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        # Update save/cancel button labels manually for translation support
        self._btn_box.button(QDialogButtonBox.StandardButton.Save).setText(self._i18n.t("save"))
        self._btn_box.button(QDialogButtonBox.StandardButton.Cancel).setText(self._i18n.t("cancel"))

        self._btn_box.accepted.connect(self._on_save_clicked)
        self._btn_box.rejected.connect(self.reject)
        layout.addWidget(self._btn_box)

    def _load_config(self):
        # Rate
        rate_str = self._config.get("rate")
        try:
            val = int(rate_str.replace("%", "").replace("+", ""))
            self._rate_slider.setValue(val)
        except ValueError:
            self._rate_slider.setValue(0)

        # Pitch
        pitch_str = self._config.get("pitch")
        try:
            val = int(pitch_str.replace("Hz", "").replace("+", ""))
            self._pitch_slider.setValue(val)
        except ValueError:
            self._pitch_slider.setValue(0)

        # Language
        lang = self._config.get("language")
        idx = self._lang_combo.findData(lang)
        if idx >= 0:
            self._lang_combo.setCurrentIndex(idx)

    def _on_rate_changed(self, val: int):
        sign = "+" if val >= 0 else ""
        self._rate_label.setText(f"{self._i18n.t('rate')}: {sign}{val}%")

    def _on_pitch_changed(self, val: int):
        sign = "+" if val >= 0 else ""
        self._pitch_label.setText(f"{self._i18n.t('pitch')}: {sign}{val}Hz")

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, self._i18n.t("choose_folder"), self._output_dir)
        if folder:
            self._output_dir = folder
            self._dir_path_label.setText(folder)

    def _on_rate_slider_double_clicked(self, event):
        self._rate_slider.setValue(0)

    def _on_save_clicked(self):
        self._save_config()
        self.accept()

    def _save_config(self):
        self._config.set("rate", format_rate(self._rate_slider.value()))
        self._config.set("pitch", format_pitch(self._pitch_slider.value()))
        self._config.set("output_dir", self._output_dir)
        self._config.set("language", self._lang_combo.currentData())
        self._config.save()
```

- [ ] **Step 4: Integrate SettingsDialog with MainWindow**

Modify `_on_open_settings` in `src/ui/main_window.py` to trigger the dialog and reload settings:
```python
    def _on_open_settings(self):
        from src.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._i18n, self._config, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            # Sync main window state/texts if language changed
            config_lang = self._config.get("language")
            if config_lang != self._i18n.current_language:
                self.set_language(config_lang)
            else:
                # Reload voices/texts to ensure they stay up-to-date
                self.statusBar().showMessage(self._i18n.t("status_ready"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_settings_dialog.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/ui/settings_dialog.py src/ui/main_window.py tests/test_ui/test_settings_dialog.py
git commit -m "feat: settings dialog with double-click reset sliders and output dir picker"
```

---

## Task 9: System Tray Integration

**Files:**
- Create: `src/ui/system_tray.py`
- Create: `tests/test_ui/test_system_tray.py`
- Modify: `src/ui/main_window.py`

- [ ] **Step 1: Write failing tests for SystemTrayManager**

Create `tests/test_ui/test_system_tray.py`:
```python
"""Tests for SystemTrayManager — tray menu actions, visibility logic."""

from pathlib import Path
import pytest
from PySide6.QtWidgets import QSystemTrayIcon
from src.ui.system_tray import SystemTrayManager
from src.ui.main_window import MainWindow
from src.i18n import I18n
from src.config_manager import ConfigManager

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"

@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)

@pytest.fixture
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)

def test_system_tray_creation(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)

    tray_mgr = SystemTrayManager(win)
    assert tray_mgr._tray_icon is not None
    assert tray_mgr._tray_icon.toolTip() == win._i18n.t("app_title")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_system_tray.py -v`
Expected: FAIL (No module named `src.ui.system_tray`)

- [ ] **Step 3: Implement `src/ui/system_tray.py`**

Create `src/ui/system_tray.py`:
```python
"""System tray icon manager. Enables minimize-to-tray and notifications."""

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle

class SystemTrayManager(QObject):
    """Manages QSystemTrayIcon lifecycle and interactions."""
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._i18n = main_window._i18n

        # Setup standard system fallback icon if resources are missing
        icon_path = Path(__file__).parent.parent / "resources" / "icons" / "icon.png"
        if icon_path.exists():
            icon = QIcon(str(icon_path))
        else:
            icon = QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self._tray_icon = QSystemTrayIcon(icon, self)
        self._tray_icon.setToolTip(self._i18n.t("app_title"))

        self._setup_menu()
        self._tray_icon.activated.connect(self._on_activated)
        self._tray_icon.show()

        # Connect to main window language changes to update tray
        self._main_window.language_changed.connect(self._on_language_changed)

    def _setup_menu(self):
        menu = QMenu()

        self._show_action = QAction(self._i18n.t("show_main"), self)
        self._show_action.triggered.connect(self._restore_main_window)
        menu.addAction(self._show_action)

        self._settings_action = QAction(self._i18n.t("settings"), self)
        self._settings_action.triggered.connect(self._main_window._on_open_settings)
        menu.addAction(self._settings_action)

        menu.addSeparator()

        self._exit_action = QAction(self._i18n.t("exit"), self)
        self._exit_action.triggered.connect(self._quit_application)
        menu.addAction(self._exit_action)

        self._tray_icon.setContextMenu(menu)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self._main_window.isVisible():
                self._main_window.hide()
            else:
                self._restore_main_window()

    def _restore_main_window(self):
        self._main_window.showNormal()
        self._main_window.activateWindow()

    def _quit_application(self):
        self._tray_icon.hide()
        QApplication.quit()

    def show_notification(self, title: str, message: str):
        self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_language_changed(self):
        self._tray_icon.setToolTip(self._i18n.t("app_title"))
        self._show_action.setText(self._i18n.t("show_main"))
        self._settings_action.setText(self._i18n.t("settings"))
        self._exit_action.setText(self._i18n.t("exit"))

from pathlib import Path
```

- [ ] **Step 4: Integrate SystemTrayManager into MainWindow**

Modify `src/ui/main_window.py` to hold a reference to `SystemTrayManager` and override `closeEvent` for minimize-to-tray:

Modify imports in `src/ui/main_window.py`:
```python
from src.ui.system_tray import SystemTrayManager
```

Add initialization in `__init__` of `MainWindow`:
```python
        self._tray_manager = SystemTrayManager(self)
```

Modify `_on_export_ready` in `src/ui/main_window.py` to trigger notification:
```python
    def _on_export_ready(self, file_path: str):
        filename = Path(file_path).name
        self.statusBar().showMessage(self._i18n.t("status_exported", filename=filename))
        self._tray_manager.show_notification(
            self._i18n.t("export_success_title"),
            self._i18n.t("export_success_msg", path=file_path)
        )
        self._on_text_changed()
```

Modify `closeEvent` to hide the window instead of exiting:
```python
    def closeEvent(self, event):
        if self._tray_manager._tray_icon.isVisible():
            self.hide()
            event.ignore()
        else:
            geom = self.geometry()
            self._config.set("window_geometry", {"x": geom.x(), "y": geom.y(), "w": geom.width(), "h": geom.height()})
            self._config.save()
            super().closeEvent(event)
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest -v`
Expected: 56 passed (51 existing + 5 new UI tests)

- [ ] **Step 6: Commit**

```bash
git add src/ui/system_tray.py src/ui/main_window.py tests/test_ui/test_system_tray.py
git commit -m "feat: system tray minimize-to-tray behavior and export completion notifications"
```
