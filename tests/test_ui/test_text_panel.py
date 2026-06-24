"""Tests for text_panel — text input, button states, signals."""

import pytest
from PySide6.QtCore import Qt
from src.ui.text_panel import TextPanel
from src.i18n import I18n
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


class TestTextPanel:
    def test_panel_creates(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel is not None

    def test_buttons_disabled_when_empty(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert not panel._preview_btn.isEnabled()
        assert not panel._export_btn.isEnabled()

    def test_buttons_enabled_when_text_entered(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        assert panel._preview_btn.isEnabled()
        assert panel._export_btn.isEnabled()

    def test_buttons_disabled_again_when_text_cleared(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        panel._text_edit.clear()
        assert not panel._preview_btn.isEnabled()
        assert not panel._export_btn.isEnabled()

    def test_get_text(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("測試文字")
        assert panel.get_text() == "測試文字"

    def test_preview_signal_emitted(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        with qtbot.waitSignal(panel.preview_requested):
            panel._preview_btn.click()

    def test_export_signal_emitted(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        with qtbot.waitSignal(panel.export_requested):
            panel._export_btn.click()
