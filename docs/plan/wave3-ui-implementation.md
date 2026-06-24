# Wave 3 UI Components Implementation Plan (v2 — rework)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PySide6 UI for simple-edge-tts Wave 3, containing the Main Window (T7), Settings Dialog (T8), and System Tray (T9) with follower OS theming and full i18n support.

**Architecture:** Per spec §3.1/§4.1 — left-right split layout. `voice_panel.py` (left ~30%) hosts voice selection, rate/pitch sliders, and output folder. `text_panel.py` (right ~70%) hosts text input, action buttons, and status display. `main_window.py` composes both panels. QThread-based async for voice loading (no `asyncio.run()` in Qt event loop). ConfigManager and I18n are bound to UI components.

**Tech Stack:** Python 3.11+, PySide6, edge-tts, pytest, pytest-qt

**Rework rationale (reviewer REJECTED v1):**
- **F1 CRITICAL**: v1 used single-column `QVBoxLayout`; spec §3.1 requires left-right split (`QHBoxLayout`, 30/70)
- **F2 WARNING**: v1 eliminated `voice_panel.py` / `text_panel.py`; spec §4.1 mandates them
- **F7 WARNING**: `get_grouped_voices_sync()` calls `asyncio.run()`, crashes inside running Qt event loop on language change → use QThread
- **F3 WARNING**: `from pathlib import Path` at bottom of `system_tray.py` → move to top
- **F4 WARNING**: `closeEvent` accesses private `_tray_icon` → expose public `is_visible()` method
- **F8 WARNING**: `_on_voice_changed` auto-saves on every programmatic combo update → guard with `_loading` flag
- **F9 WARNING**: No validation in rate/pitch parsing → add `try/except` with fallback

---

## File Structure

| File | Responsibility |
|---|---|
| `src/ui/__init__.py` | Package marker |
| `src/ui/theme.py` | Light/dark theme detection and QSS styling |
| `src/ui/voice_panel.py` | Left panel (~30%): voice dropdown (with search), rate/pitch sliders, output folder picker |
| `src/ui/text_panel.py` | Right panel (~70%): text input area, action buttons, status display |
| `src/ui/main_window.py` | QMainWindow: composes voice_panel + text_panel in left-right split, toolbar, status bar |
| `src/ui/settings_dialog.py` | Modal dialog for language switching (rate/pitch/output now inline in voice_panel) |
| `src/ui/system_tray.py` | System tray icon, minimize-to-tray behavior, context menu, notifications |
| `src/app.py` | Application setup (theme listener, high-DPI) |
| `tests/test_ui/__init__.py` | Test package marker |
| `tests/test_ui/test_voice_panel.py` | Tests for voice panel: voice loading, filtering, slider values, config save guard |
| `tests/test_ui/test_text_panel.py` | Tests for text panel: button states, text input, signal emission |
| `tests/test_ui/test_main_window.py` | Tests for main window: panel composition, toolbar, language toggle |
| `tests/test_ui/test_settings_dialog.py` | Tests for Settings Dialog: language switching |
| `tests/test_ui/test_system_tray.py` | Tests for System Tray icon states and context menus |

---

## Task 7: Main Window, Voice Panel, Text Panel & Theme System

**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/theme.py`
- Create: `src/ui/voice_panel.py`
- Create: `src/ui/text_panel.py`
- Create: `src/ui/main_window.py`
- Create: `tests/test_ui/__init__.py`
- Create: `tests/test_ui/test_voice_panel.py`
- Create: `tests/test_ui/test_text_panel.py`
- Create: `tests/test_ui/test_main_window.py`
- Modify: `src/app.py`
- Modify: `src/main.py`
- Modify: `src/resources/translations/zh-TW.json`
- Modify: `src/resources/translations/en-US.json`

- [ ] **Step 1: Create `src/ui/__init__.py` and `tests/test_ui/__init__.py`**

Empty files to mark directories as packages.

- [ ] **Step 2: Add translation keys for UI**

Update translation files to support all UI labels including voice panel, text panel, settings, and tray.

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
  "status_loading_voices": "載入聲音列表中...",
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
  "export_success_title": "匯出完成",
  "export_success_msg": "已儲存至 {path}"
}
```

Modify `src/resources/translations/en-US.json`:
```json
{
  "app_title": "simple-edge-tts",
  "voice_selection": "Voice Selection",
  "search_voice": "Search voices...",
  "parameters": "Parameters",
  "rate": "Rate",
  "pitch": "Pitch",
  "output_settings": "Output Settings",
  "choose_folder": "Choose Folder",
  "text_placeholder": "Enter text to convert...",
  "preview": "Preview",
  "stop": "Stop",
  "export_mp3": "Export MP3",
  "status_ready": "Ready",
  "status_generating": "Generating speech...",
  "status_playing": "Playing...",
  "status_exported": "Exported: {filename}",
  "status_loading_voices": "Loading voices...",
  "error_no_internet": "Cannot connect to TTS service. Please check your internet connection.",
  "error_export_failed": "Export failed: {error}",
  "error_folder_not_writable": "Cannot write to folder. Please choose another location.",
  "voice_group_tw": "Traditional Chinese",
  "voice_group_en": "English",
  "voice_group_other": "Other",
  "lang_toggle": "繁中",
  "settings": "Settings",
  "settings_title": "Settings",
  "language": "Language",
  "save": "Save",
  "cancel": "Cancel",
  "show_main": "Show Main Window",
  "exit": "Exit",
  "export_success_title": "Export Complete",
  "export_success_msg": "Saved to {path}"
}
```

- [ ] **Step 3: Create `src/ui/theme.py`**

Create `src/ui/theme.py`:
```python
"""Light/dark theme detection and QSS styling. Listens to OS theme changes."""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette


def is_dark_mode(app: QApplication) -> bool:
    """Detect OS dark mode via palette luminance."""
    palette = app.palette()
    bg = palette.color(QPalette.ColorRole.Window)
    # Use luminance formula: darker backgrounds have lower values
    luminance = 0.299 * bg.redF() + 0.587 * bg.greenF() + 0.114 * bg.blueF()
    return luminance < 0.5


_LIGHT_QSS = """
QMainWindow { background-color: #f5f5f5; }
QTextEdit { background-color: #ffffff; border: 1px solid #cccccc; border-radius: 4px; padding: 8px; }
QComboBox { padding: 4px 8px; }
QSlider::groove:horizontal { height: 6px; background: #cccccc; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; background: #4a90d9; border-radius: 8px; margin: -5px 0; }
QPushButton { padding: 6px 16px; border-radius: 4px; background-color: #4a90d9; color: white; border: none; }
QPushButton:hover { background-color: #3a7bc8; }
QPushButton:disabled { background-color: #cccccc; color: #888888; }
QGroupBox { font-weight: bold; border: 1px solid #dddddd; border-radius: 4px; margin-top: 12px; padding-top: 16px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
"""

_DARK_QSS = """
QMainWindow { background-color: #2b2b2b; }
QTextEdit { background-color: #3c3c3c; color: #e0e0e0; border: 1px solid #555555; border-radius: 4px; padding: 8px; }
QComboBox { padding: 4px 8px; background-color: #3c3c3c; color: #e0e0e0; }
QSlider::groove:horizontal { height: 6px; background: #555555; border-radius: 3px; }
QSlider::handle:horizontal { width: 16px; height: 16px; background: #5b9bd5; border-radius: 8px; margin: -5px 0; }
QPushButton { padding: 6px 16px; border-radius: 4px; background-color: #5b9bd5; color: white; border: none; }
QPushButton:hover { background-color: #4a8ac4; }
QPushButton:disabled { background-color: #555555; color: #888888; }
QGroupBox { font-weight: bold; border: 1px solid #555555; border-radius: 4px; margin-top: 12px; padding-top: 16px; color: #e0e0e0; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
"""


def apply_theme(app: QApplication):
    """Apply light or dark QSS based on OS setting."""
    if is_dark_mode(app):
        app.setStyleSheet(_DARK_QSS)
    else:
        app.setStyleSheet(_LIGHT_QSS)
```

- [ ] **Step 4: Write failing tests for VoicePanel**

Create `tests/test_ui/test_voice_panel.py`:
```python
"""Tests for VoicePanel — voice loading (async), filtering, slider values, config save guard."""

from pathlib import Path
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt
from src.ui.voice_panel import VoicePanel
from src.i18n import I18n
from src.config_manager import ConfigManager

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"

@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)

@pytest.fixture
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)

def test_voice_panel_creates_with_correct_widgets(qtbot, i18n, config):
    panel = VoicePanel(i18n=i18n, config=config)
    qtbot.addWidget(panel)

    # Should have search input, voice combo, rate/pitch sliders, output dir
    assert panel._voice_search is not None
    assert panel._voice_combo is not None
    assert panel._rate_slider is not None
    assert panel._pitch_slider is not None
    assert panel._dir_btn is not None

def test_voice_panel_rate_slider_range(qtbot, i18n, config):
    panel = VoicePanel(i18n=i18n, config=config)
    qtbot.addWidget(panel)
    assert panel._rate_slider.minimum() == -50
    assert panel._rate_slider.maximum() == 100

def test_voice_panel_pitch_slider_range(qtbot, i18n, config):
    panel = VoicePanel(i18n=i18n, config=config)
    qtbot.addWidget(panel)
    assert panel._pitch_slider.minimum() == -50
    assert panel._pitch_slider.maximum() == 50

def test_voice_panel_loading_flag_prevents_config_save(qtbot, i18n, config):
    """F8 fix: programmatic combo changes during loading should NOT trigger config save."""
    panel = VoicePanel(i18n=i18n, config=config)
    qtbot.addWidget(panel)

    # Simulate the loading guard
    panel._loading = True
    config.save = MagicMock()
    panel._voice_combo.addItem("test", "test-voice")
    panel._voice_combo.setCurrentIndex(0)
    config.save.assert_not_called()

def test_voice_panel_rate_config_load_with_invalid_value(qtbot, i18n, config):
    """F9 fix: invalid rate/pitch values should fallback to 0."""
    config.set("rate", "invalid")
    config.set("pitch", "also-invalid")
    panel = VoicePanel(i18n=i18n, config=config)
    qtbot.addWidget(panel)

    assert panel._rate_slider.value() == 0
    assert panel._pitch_slider.value() == 0
```

- [ ] **Step 5: Run VoicePanel tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_voice_panel.py -v`
Expected: FAIL (No module named `src.ui.voice_panel`)

- [ ] **Step 6: Implement `src/ui/voice_panel.py` (Left Panel ~30%)**

Create `src/ui/voice_panel.py`:
```python
"""Left panel: voice dropdown (with search), rate/pitch sliders, output folder picker.

Spec §3.1: This is the left ~30% of the main window layout.
Spec §4.1: Module ui/voice_panel.py.
"""

import re
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QSlider, QPushButton, QGroupBox, QFileDialog,
)

from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, format_rate, format_pitch


class VoiceLoaderThread(QThread):
    """Load voices asynchronously to avoid asyncio.run() inside Qt event loop.

    F7 fix: get_grouped_voices_sync() calls asyncio.run(), which crashes if
    called inside a running Qt event loop. This QThread runs its own event loop.
    """
    voices_loaded = Signal(object)  # OrderedDict
    load_failed = Signal(str)

    def run(self):
        try:
            engine = TTSEngine()
            grouped = engine.get_grouped_voices_sync()
            self.voices_loaded.emit(grouped)
        except Exception as e:
            self.load_failed.emit(str(e))


class DoubleClickSlider(QSlider):
    """Custom slider that resets to 0 on double-click."""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)

    def mouseDoubleClickEvent(self, event):
        self.setValue(0)
        super().mouseDoubleClickEvent(event)


class VoicePanel(QWidget):
    """Left panel containing voice selection, parameter sliders, and output settings.

    Signals:
        voice_changed(str): Emitted when voice selection changes (voice short name).
        rate_changed(str): Emitted when rate slider changes (formatted like "+10%").
        pitch_changed(str): Emitted when pitch slider changes (formatted like "-5Hz").
    """
    voice_changed = Signal(str)
    rate_changed = Signal(str)
    pitch_changed = Signal(str)

    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._all_voices: list[dict] = []
        self._loading = False  # F8 fix: guard against programmatic combo changes
        self._voice_loader: VoiceLoaderThread | None = None

        self._setup_ui()
        self._load_config()
        self._load_voices_async()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # -- Voice Selection Group --
        voice_group = QGroupBox(self._i18n.t("voice_selection"))
        voice_layout = QVBoxLayout(voice_group)

        self._voice_search = QLineEdit()
        self._voice_search.setPlaceholderText(self._i18n.t("search_voice"))
        self._voice_search.textChanged.connect(self._filter_voices)
        voice_layout.addWidget(self._voice_search)

        self._voice_combo = QComboBox()
        self._voice_combo.currentTextChanged.connect(self._on_voice_changed)
        voice_layout.addWidget(self._voice_combo)

        layout.addWidget(voice_group)

        # -- Parameters Group (rate/pitch sliders) --
        param_group = QGroupBox(self._i18n.t("parameters"))
        param_layout = QVBoxLayout(param_group)

        # Rate slider
        self._rate_label = QLabel(self._i18n.t("rate"))
        param_layout.addWidget(self._rate_label)

        self._rate_slider = DoubleClickSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(-50, 100)
        self._rate_slider.setValue(0)
        self._rate_slider.valueChanged.connect(self._on_rate_changed)
        param_layout.addWidget(self._rate_slider)

        # Pitch slider
        self._pitch_label = QLabel(self._i18n.t("pitch"))
        param_layout.addWidget(self._pitch_label)

        self._pitch_slider = DoubleClickSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-50, 50)
        self._pitch_slider.setValue(0)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        param_layout.addWidget(self._pitch_slider)

        layout.addWidget(param_group)

        # -- Output Settings Group --
        output_group = QGroupBox(self._i18n.t("output_settings"))
        output_layout = QVBoxLayout(output_group)

        self._dir_path_label = QLabel(self._config.get("output_dir"))
        self._dir_path_label.setWordWrap(True)
        output_layout.addWidget(self._dir_path_label)

        self._dir_btn = QPushButton(self._i18n.t("choose_folder"))
        self._dir_btn.clicked.connect(self._choose_folder)
        output_layout.addWidget(self._dir_btn)

        layout.addWidget(output_group)
        layout.addStretch()

    def _load_config(self):
        """Load rate/pitch from config with validation (F9 fix)."""
        # Rate
        rate_str = self._config.get("rate") or "+0%"
        try:
            val = int(re.sub(r'[%+]', '', rate_str))
            val = max(-50, min(100, val))
        except (ValueError, TypeError):
            val = 0
        self._rate_slider.setValue(val)

        # Pitch
        pitch_str = self._config.get("pitch") or "+0Hz"
        try:
            val = int(re.sub(r'[Hz+]', '', pitch_str))
            val = max(-50, min(50, val))
        except (ValueError, TypeError):
            val = 0
        self._pitch_slider.setValue(val)

    def _load_voices_async(self):
        """Load voices in a QThread (F7 fix: avoids asyncio.run in Qt event loop)."""
        self._loading = True
        self._voice_loader = VoiceLoaderThread()
        self._voice_loader.voices_loaded.connect(self._on_voices_loaded)
        self._voice_loader.load_failed.connect(self._on_voices_load_failed)
        self._voice_loader.start()

    def _on_voices_loaded(self, grouped):
        """Populate combo box after async voice loading completes."""
        self._voice_combo.clear()
        self._all_voices = []

        for group, voices in grouped.items():
            group_key = f"voice_group_{group.lower().replace('-', '_')}"
            group_name = self._i18n.t(group_key)
            if group_key == group_name:  # key not found, use raw
                group_name = group

            for v in voices:
                name = v["ShortName"]
                gender = v.get("Gender", "")
                label = f"{name} ({gender}) - {group_name}"
                self._all_voices.append({"label": label, "name": name, "raw": v})
                self._voice_combo.addItem(label, name)

        # Restore last voice
        last_voice = self._config.get("last_voice")
        if last_voice:
            idx = self._voice_combo.findData(last_voice)
            if idx >= 0:
                self._voice_combo.setCurrentIndex(idx)

        self._loading = False

    def _on_voices_load_failed(self, error_msg: str):
        self._loading = False
        # Status will be updated by main_window via signal if needed

    def _filter_voices(self, search_text: str):
        self._loading = True  # F8 fix: guard during repopulation
        self._voice_combo.clear()
        search_lower = search_text.lower()
        for item in self._all_voices:
            if search_lower in item["label"].lower() or search_lower in item["name"].lower():
                self._voice_combo.addItem(item["label"], item["name"])
        self._loading = False

    def _on_voice_changed(self, text: str):
        """F8 fix: only save config when not in loading/filtering state."""
        voice = self._voice_combo.currentData()
        if voice and not self._loading:
            self._config.set("last_voice", voice)
            self._config.save()
            self.voice_changed.emit(voice)

    def _on_rate_changed(self, val: int):
        sign = "+" if val >= 0 else ""
        self._rate_label.setText(f"{self._i18n.t('rate')}: {sign}{val}%")
        formatted = format_rate(val)
        if not self._loading:
            self._config.set("rate", formatted)
            self._config.save()
        self.rate_changed.emit(formatted)

    def _on_pitch_changed(self, val: int):
        sign = "+" if val >= 0 else ""
        self._pitch_label.setText(f"{self._i18n.t('pitch')}: {sign}{val}Hz")
        formatted = format_pitch(val)
        if not self._loading:
            self._config.set("pitch", formatted)
            self._config.save()
        self.pitch_changed.emit(formatted)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self._i18n.t("choose_folder"), self._config.get("output_dir")
        )
        if folder:
            self._config.set("output_dir", folder)
            self._config.save()
            self._dir_path_label.setText(folder)

    def get_selected_voice(self) -> str | None:
        return self._voice_combo.currentData()

    def get_rate(self) -> str:
        return format_rate(self._rate_slider.value())

    def get_pitch(self) -> str:
        return format_pitch(self._pitch_slider.value())

    def update_ui_texts(self):
        """Update all labels for language change."""
        self._voice_search.setPlaceholderText(self._i18n.t("search_voice"))
        self._rate_label.setText(self._i18n.t("rate"))
        self._pitch_label.setText(self._i18n.t("pitch"))
        self._dir_btn.setText(self._i18n.t("choose_folder"))

        # Reload voices with new language labels
        self._load_voices_async()
```

- [ ] **Step 7: Write failing tests for TextPanel**

Create `tests/test_ui/test_text_panel.py`:
```python
"""Tests for TextPanel — button states, text input, signal emission."""

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from src.ui.text_panel import TextPanel
from src.i18n import I18n

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"

@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)

def test_text_panel_creates_with_correct_widgets(qtbot, i18n):
    panel = TextPanel(i18n=i18n)
    qtbot.addWidget(panel)

    assert panel._text_edit is not None
    assert panel._preview_btn is not None
    assert panel._stop_btn is not None
    assert panel._export_btn is not None

def test_text_panel_buttons_disabled_initially(qtbot, i18n):
    panel = TextPanel(i18n=i18n)
    qtbot.addWidget(panel)

    assert not panel._preview_btn.isEnabled()
    assert not panel._stop_btn.isEnabled()
    assert not panel._export_btn.isEnabled()

def test_text_panel_buttons_enabled_with_text(qtbot, i18n):
    panel = TextPanel(i18n=i18n)
    qtbot.addWidget(panel)

    panel._text_edit.setPlainText("Hello world")
    assert panel._preview_btn.isEnabled()
    assert panel._export_btn.isEnabled()
    assert not panel._stop_btn.isEnabled()

def test_text_panel_preview_signal(qtbot, i18n):
    panel = TextPanel(i18n=i18n)
    qtbot.addWidget(panel)

    panel._text_edit.setPlainText("Test text")
    with qtbot.waitSignal(panel.preview_requested, timeout=1000):
        panel._preview_btn.click()

def test_text_panel_get_text(qtbot, i18n):
    panel = TextPanel(i18n=i18n)
    qtbot.addWidget(panel)

    panel._text_edit.setPlainText("  Hello  ")
    assert panel.get_text() == "Hello"
```

- [ ] **Step 8: Implement `src/ui/text_panel.py` (Right Panel ~70%)**

Create `src/ui/text_panel.py`:
```python
"""Right panel: text input, action buttons, status display.

Spec §3.1: This is the right ~70% of the main window layout.
Spec §4.1: Module ui/text_panel.py.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel,
)

from src.i18n import I18n


class TextPanel(QWidget):
    """Right panel containing text input, action buttons, and status label.

    Signals:
        preview_requested: Emitted when user clicks Preview button.
        export_requested: Emitted when user clicks Export button.
        stop_requested: Emitted when user clicks Stop button.
    """
    preview_requested = Signal()
    export_requested = Signal()
    stop_requested = Signal()

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Text input area
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(self._i18n.t("text_placeholder"))
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit, stretch=1)

        # Button row
        btn_layout = QHBoxLayout()

        self._preview_btn = QPushButton(f"▶ {self._i18n.t('preview')}")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self.preview_requested.emit)
        btn_layout.addWidget(self._preview_btn)

        self._stop_btn = QPushButton(f"⏹ {self._i18n.t('stop')}")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        btn_layout.addWidget(self._stop_btn)

        self._export_btn = QPushButton(f"💾 {self._i18n.t('export_mp3')}")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_requested.emit)
        btn_layout.addWidget(self._export_btn)

        layout.addLayout(btn_layout)

        # Status label (inline, not status bar — that's on MainWindow)
        self._status_label = QLabel(self._i18n.t("status_ready"))
        layout.addWidget(self._status_label)

    def _on_text_changed(self):
        has_text = bool(self._text_edit.toPlainText().strip())
        self._preview_btn.setEnabled(has_text)
        self._export_btn.setEnabled(has_text)

    def get_text(self) -> str:
        return self._text_edit.toPlainText().strip()

    def set_status(self, message: str):
        self._status_label.setText(message)

    def set_generating(self, generating: bool):
        """Disable buttons during TTS generation."""
        self._preview_btn.setEnabled(not generating and bool(self.get_text()))
        self._export_btn.setEnabled(not generating and bool(self.get_text()))

    def set_playing(self, playing: bool):
        """Update button states based on playback state."""
        self._stop_btn.setEnabled(playing)
        has_text = bool(self.get_text())
        self._preview_btn.setEnabled(not playing and has_text)
        self._export_btn.setEnabled(not playing and has_text)

    def update_ui_texts(self):
        """Update all labels for language change."""
        self._text_edit.setPlaceholderText(self._i18n.t("text_placeholder"))
        self._preview_btn.setText(f"▶ {self._i18n.t('preview')}")
        self._stop_btn.setText(f"⏹ {self._i18n.t('stop')}")
        self._export_btn.setText(f"💾 {self._i18n.t('export_mp3')}")
        self._status_label.setText(self._i18n.t("status_ready"))
```

- [ ] **Step 9: Write failing tests for MainWindow**

Create `tests/test_ui/test_main_window.py`:
```python
"""Tests for MainWindow — panel composition, toolbar, language toggle."""

from pathlib import Path
import pytest
from PySide6.QtWidgets import QHBoxLayout
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

def test_main_window_has_left_right_split(qtbot, i18n, config):
    """F1 fix: MainWindow must use left-right QHBoxLayout per spec §3.1."""
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)

    central = win.centralWidget()
    layout = central.layout()
    # The central widget's layout should be an HBox (left-right split)
    assert isinstance(layout, QHBoxLayout), f"Expected QHBoxLayout, got {type(layout).__name__}"

def test_main_window_has_voice_panel(qtbot, i18n, config):
    """F2 fix: MainWindow must compose voice_panel per spec §4.1."""
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    assert win._voice_panel is not None

def test_main_window_has_text_panel(qtbot, i18n, config):
    """F2 fix: MainWindow must compose text_panel per spec §4.1."""
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    assert win._text_panel is not None

def test_main_window_default_size(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    assert win.minimumWidth() >= 700
    assert win.minimumHeight() >= 500

def test_main_window_has_toolbar(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    toolbars = win.findChildren(type(win._toolbar))
    assert len(toolbars) >= 1

def test_main_window_language_toggle(qtbot, i18n, config):
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)
    assert i18n.current_language == "zh-TW"

    win._toggle_language()
    assert i18n.current_language == "en-US"
```

- [ ] **Step 10: Run MainWindow tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_main_window.py -v`
Expected: FAIL (No module named `src.ui.main_window`)

- [ ] **Step 11: Implement `src/ui/main_window.py` (Composes left-right split)**

Create `src/ui/main_window.py`:
```python
"""Main window: left-right split layout composing voice_panel + text_panel.

Spec §3.1: Left-Right Split (~30% left / ~70% right).
Spec §4.1: Composes voice_panel + text_panel.
"""

import asyncio
import tempfile
from pathlib import Path

from PySide6.QtCore import Signal, QThread
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QToolBar, QStatusBar, QMessageBox,
)

from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, make_output_filename
from src.audio_player import AudioPlayer, PlayerState
from src.ui.voice_panel import VoicePanel
from src.ui.text_panel import TextPanel


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
    """Main window of simple-edge-tts with left-right split layout."""
    language_changed = Signal(str)

    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._player = AudioPlayer(self)
        self._tts_worker = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setWindowTitle(self._i18n.t("app_title"))
        self.setMinimumSize(700, 500)
        geom = self._config.get("window_geometry")
        self.resize(geom["w"], geom["h"])

        # Toolbar
        self._toolbar = QToolBar("Main Toolbar", self)
        self._toolbar.setMovable(False)
        self.addToolBar(self._toolbar)

        self._settings_action = self._toolbar.addAction(self._i18n.t("settings"))
        self._settings_action.triggered.connect(self._on_open_settings)

        self._toolbar.addSeparator()

        self._lang_action = self._toolbar.addAction(self._i18n.t("lang_toggle"))
        self._lang_action.triggered.connect(self._toggle_language)

        # Central Widget — Left-Right Split (F1 fix: QHBoxLayout)
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # Left panel (~30%): Voice Panel
        self._voice_panel = VoicePanel(i18n=self._i18n, config=self._config)
        main_layout.addWidget(self._voice_panel, stretch=3)

        # Right panel (~70%): Text Panel
        self._text_panel = TextPanel(i18n=self._i18n)
        main_layout.addWidget(self._text_panel, stretch=7)

        # Status Bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def _connect_signals(self):
        self._player.state_changed.connect(self._on_player_state_changed)
        self._player.playback_finished.connect(
            lambda: self._update_status(self._i18n.t("status_ready"))
        )
        self._text_panel.preview_requested.connect(self._on_preview)
        self._text_panel.export_requested.connect(self._on_export)
        self._text_panel.stop_requested.connect(self._on_stop)

    def _update_status(self, message: str):
        self.statusBar().showMessage(message)
        self._text_panel.set_status(message)

    def _on_preview(self):
        text = self._text_panel.get_text()
        voice = self._voice_panel.get_selected_voice()
        if not text or not voice:
            return

        self._update_status(self._i18n.t("status_generating"))
        self._text_panel.set_generating(True)

        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()

        rate = self._voice_panel.get_rate()
        pitch = self._voice_panel.get_pitch()

        self._tts_worker = TTSWorker(text, voice, tmp.name, rate, pitch)
        self._tts_worker.finished.connect(self._on_preview_ready)
        self._tts_worker.error.connect(self._on_tts_error)
        self._tts_worker.start()

    def _on_preview_ready(self, file_path: str):
        self._update_status(self._i18n.t("status_playing"))
        self._text_panel.set_generating(False)
        self._player.play(file_path)

    def _on_export(self):
        text = self._text_panel.get_text()
        voice = self._voice_panel.get_selected_voice()
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

        self._update_status(self._i18n.t("status_generating"))
        self._text_panel.set_generating(True)

        rate = self._voice_panel.get_rate()
        pitch = self._voice_panel.get_pitch()

        self._tts_worker = TTSWorker(text, voice, str(output_path), rate, pitch)
        self._tts_worker.finished.connect(self._on_export_ready)
        self._tts_worker.error.connect(self._on_tts_error)
        self._tts_worker.start()

    def _on_export_ready(self, file_path: str):
        filename = Path(file_path).name
        self._update_status(self._i18n.t("status_exported", filename=filename))
        self._text_panel.set_generating(False)

    def _on_tts_error(self, error_msg: str):
        QMessageBox.critical(self, "TTS Error", self._i18n.t("error_export_failed", error=error_msg))
        self._update_status(self._i18n.t("status_ready"))
        self._text_panel.set_generating(False)

    def _on_stop(self):
        self._player.stop()

    def _on_player_state_changed(self, state: PlayerState):
        is_playing = state == PlayerState.PLAYING
        self._text_panel.set_playing(is_playing)

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
        self._voice_panel.update_ui_texts()
        self._text_panel.update_ui_texts()
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def closeEvent(self, event):
        geom = self.geometry()
        self._config.set("window_geometry", {
            "x": geom.x(), "y": geom.y(),
            "w": geom.width(), "h": geom.height()
        })
        self._config.save()
        super().closeEvent(event)
```

- [ ] **Step 12: Run all T7 tests**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_voice_panel.py tests/test_ui/test_text_panel.py tests/test_ui/test_main_window.py -v`
Expected: PASS

- [ ] **Step 13: Update `src/app.py`**

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

- [ ] **Step 14: Update `src/main.py`**

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

- [ ] **Step 15: Commit**

```bash
git add src/ui/ src/app.py src/main.py src/resources/translations/ tests/test_ui/
git commit -m "feat: main window with left-right split layout, voice_panel, text_panel (spec §3.1/§4.1)"
```

---

## Task 8: Settings Dialog

**Files:**
- Create: `src/ui/settings_dialog.py`
- Create: `tests/test_ui/test_settings_dialog.py`
- Modify: `src/ui/main_window.py`

**Scope note:** Since rate/pitch sliders and output dir picker are now in `voice_panel.py` (matching spec §3.1 layout), the Settings Dialog is simplified to language switching only.

- [ ] **Step 1: Write failing tests for SettingsDialog**

Create `tests/test_ui/test_settings_dialog.py`:
```python
"""Tests for SettingsDialog — language switching."""

from pathlib import Path
import pytest
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

def test_settings_dialog_initializes_with_current_language(qtbot, i18n, config):
    dialog = SettingsDialog(i18n=i18n, config=config)
    qtbot.addWidget(dialog)
    assert dialog._lang_combo.currentData() == "zh-TW"

def test_settings_dialog_save_changes_language(qtbot, i18n, config):
    dialog = SettingsDialog(i18n=i18n, config=config)
    qtbot.addWidget(dialog)

    # Switch to English
    idx = dialog._lang_combo.findData("en-US")
    dialog._lang_combo.setCurrentIndex(idx)
    dialog._save_config()

    assert config.get("language") == "en-US"

def test_settings_dialog_has_save_cancel_buttons(qtbot, i18n, config):
    dialog = SettingsDialog(i18n=i18n, config=config)
    qtbot.addWidget(dialog)
    assert dialog._btn_box is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_settings_dialog.py -v`
Expected: FAIL (No module named `src.ui.settings_dialog`)

- [ ] **Step 3: Implement `src/ui/settings_dialog.py`**

Create `src/ui/settings_dialog.py`:
```python
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
```

- [ ] **Step 4: Integrate SettingsDialog with MainWindow**

Modify `_on_open_settings` in `src/ui/main_window.py`:
```python
    def _on_open_settings(self):
        from src.ui.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self._i18n, self._config, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            config_lang = self._config.get("language")
            if config_lang != self._i18n.current_language:
                self.set_language(config_lang)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_settings_dialog.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/ui/settings_dialog.py src/ui/main_window.py tests/test_ui/test_settings_dialog.py
git commit -m "feat: settings dialog with language switching"
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

    tray_mgr = SystemTrayManager(win, i18n)
    assert tray_mgr._tray_icon is not None
    assert tray_mgr._tray_icon.toolTip() == i18n.t("app_title")

def test_system_tray_is_visible_method(qtbot, i18n, config):
    """F4 fix: use public is_visible() instead of accessing private _tray_icon."""
    win = MainWindow(i18n=i18n, config=config)
    qtbot.addWidget(win)

    tray_mgr = SystemTrayManager(win, i18n)
    # is_visible should be callable (no direct _tray_icon access needed externally)
    assert hasattr(tray_mgr, 'is_visible')
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest tests/test_ui/test_system_tray.py -v`
Expected: FAIL (No module named `src.ui.system_tray`)

- [ ] **Step 3: Implement `src/ui/system_tray.py`**

Create `src/ui/system_tray.py`:
```python
"""System tray icon manager. Enables minimize-to-tray and notifications.

F3 fix: all imports at module top.
F4 fix: public is_visible() method instead of exposing _tray_icon.
"""

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QStyle

from src.i18n import I18n


class SystemTrayManager(QObject):
    """Manages QSystemTrayIcon lifecycle and interactions."""
    def __init__(self, main_window, i18n: I18n, parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._i18n = i18n

        # Setup icon
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

    def is_visible(self) -> bool:
        """F4 fix: public method to check tray visibility."""
        return self._tray_icon.isVisible()

    def show_notification(self, title: str, message: str):
        self._tray_icon.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)

    def _on_language_changed(self):
        self._tray_icon.setToolTip(self._i18n.t("app_title"))
        self._show_action.setText(self._i18n.t("show_main"))
        self._settings_action.setText(self._i18n.t("settings"))
        self._exit_action.setText(self._i18n.t("exit"))
```

- [ ] **Step 4: Integrate SystemTrayManager into MainWindow**

Modify `src/ui/main_window.py`:

Add import at top:
```python
from src.ui.system_tray import SystemTrayManager
```

Add initialization in `__init__` of `MainWindow` (after `_connect_signals()`):
```python
        self._tray_manager = SystemTrayManager(self, self._i18n)
```

Modify `_on_export_ready` to trigger notification:
```python
    def _on_export_ready(self, file_path: str):
        filename = Path(file_path).name
        self._update_status(self._i18n.t("status_exported", filename=filename))
        self._tray_manager.show_notification(
            self._i18n.t("export_success_title"),
            self._i18n.t("export_success_msg", path=file_path)
        )
        self._text_panel.set_generating(False)
```

Modify `closeEvent` to use public `is_visible()` (F4 fix):
```python
    def closeEvent(self, event):
        if self._tray_manager.is_visible():
            self.hide()
            event.ignore()
        else:
            geom = self.geometry()
            self._config.set("window_geometry", {
                "x": geom.x(), "y": geom.y(),
                "w": geom.width(), "h": geom.height()
            })
            self._config.save()
            super().closeEvent(event)
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `/Users/cheerc/.local/bin/uv run --extra dev pytest -v`
Expected: All previous tests + new UI tests pass

- [ ] **Step 6: Commit**

```bash
git add src/ui/system_tray.py src/ui/main_window.py tests/test_ui/test_system_tray.py
git commit -m "feat: system tray with minimize-to-tray and export notifications"
```
