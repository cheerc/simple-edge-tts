"""Tests for voice_panel — voice combo, search filter, sliders, folder picker."""

import pytest
from PySide6.QtCore import Qt
from src.ui.voice_panel import VoicePanel
from src.i18n import I18n
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


class TestVoicePanel:
    def test_panel_creates(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel is not None

    def test_rate_slider_default_zero(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel.rate_value() == 0

    def test_pitch_slider_default_zero(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel.pitch_value() == 0

    def test_rate_slider_range(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._rate_slider.setValue(-50)
        assert panel.rate_value() == -50
        panel._rate_slider.setValue(100)
        assert panel.rate_value() == 100

    def test_voice_combo_exists(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel._voice_combo is not None

    def test_search_filter_exists(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel._search_input is not None
