"""Tests for SystemTrayManager — tray menu actions, visibility logic."""

from pathlib import Path
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Signal, QObject
from PySide6.QtWidgets import QMainWindow, QSystemTrayIcon
from src.ui.system_tray import SystemTrayManager
from src.i18n import I18n

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


class StubMainWindow(QMainWindow):
    """Minimal stub for MainWindow until T7 merges.

    Provides the signals and methods that SystemTrayManager expects.
    """
    language_changed = Signal()

    def __init__(self):
        super().__init__()

    def _on_open_settings(self):
        pass


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


@pytest.fixture
def main_window(qtbot):
    win = StubMainWindow()
    qtbot.addWidget(win)
    return win


def test_system_tray_creation(qtbot, main_window, i18n):
    tray_mgr = SystemTrayManager(main_window, i18n)
    assert tray_mgr._tray_icon is not None
    assert tray_mgr._tray_icon.toolTip() == i18n.t("app_title")


def test_system_tray_is_visible_method(qtbot, main_window, i18n):
    """F4 fix: use public is_visible() instead of accessing private _tray_icon."""
    tray_mgr = SystemTrayManager(main_window, i18n)
    # is_visible should be callable (no direct _tray_icon access needed externally)
    assert hasattr(tray_mgr, 'is_visible')
    # Method should return a bool
    result = tray_mgr.is_visible()
    assert isinstance(result, bool)


def test_system_tray_context_menu_has_actions(qtbot, main_window, i18n):
    tray_mgr = SystemTrayManager(main_window, i18n)
    menu = tray_mgr._tray_icon.contextMenu()
    assert menu is not None

    action_texts = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert i18n.t("show_main") in action_texts
    assert i18n.t("settings") in action_texts
    assert i18n.t("exit") in action_texts


def test_system_tray_show_notification(qtbot, main_window, i18n):
    tray_mgr = SystemTrayManager(main_window, i18n)
    # Should not raise
    tray_mgr.show_notification("Test Title", "Test Message")


def test_system_tray_language_update(qtbot, main_window, i18n):
    """When language_changed is emitted, tray menu texts should update."""
    tray_mgr = SystemTrayManager(main_window, i18n)

    # Switch language
    i18n.set_language("en-US")
    main_window.language_changed.emit()

    assert tray_mgr._tray_icon.toolTip() == i18n.t("app_title")
    assert tray_mgr._show_action.text() == i18n.t("show_main")
    assert tray_mgr._exit_action.text() == i18n.t("exit")
