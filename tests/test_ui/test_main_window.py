"""Tests for main_window — layout, splitter, i18n toggle."""

import pytest
from src.ui.main_window import MainWindow
from src.i18n import I18n
from src.config_manager import ConfigManager
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


@pytest.fixture
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)


class TestMainWindow:
    def test_window_creates(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win is not None

    def test_window_title(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert "simple-edge-tts" in win.windowTitle()

    def test_has_voice_panel(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win._voice_panel is not None

    def test_has_text_panel(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win._text_panel is not None

    def test_minimum_size(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win.minimumWidth() >= 700
        assert win.minimumHeight() >= 500

    def test_main_window_has_left_right_split(self, qtbot, i18n, config):
        """Verify left-right split layout per spec §3.1: QHBoxLayout with 30/70 split."""
        from PySide6.QtWidgets import QSplitter
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        # Find the QSplitter in the window
        splitter = win.centralWidget().findChild(QSplitter)
        assert splitter is not None, "MainWindow must contain a QSplitter"
        assert splitter.count() == 2, "Splitter must have exactly 2 children"
        # Verify VoicePanel is left (index 0) and TextPanel is right (index 1)
        from src.ui.voice_panel import VoicePanel
        from src.ui.text_panel import TextPanel
        assert isinstance(splitter.widget(0), VoicePanel), "Left panel must be VoicePanel"
        assert isinstance(splitter.widget(1), TextPanel), "Right panel must be TextPanel"

