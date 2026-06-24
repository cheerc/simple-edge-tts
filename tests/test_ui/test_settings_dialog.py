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
