"""Tests for SystemTrayManager — pystray-based tray icon.

pystray requires a display server at import time on Linux, so all pystray
imports are deferred in the source module. Tests mock pystray at the call
site inside SystemTrayManager.start().

Ref: T20 — Replace PySide6 QSystemTrayIcon with pystray
"""

from unittest.mock import MagicMock, patch

import pytest

from src.system_tray import SystemTrayManager, _create_default_icon, _load_icon


class FakeWindow:
    """Minimal pywebview window stub with show/hide methods."""

    def __init__(self):
        self.show = MagicMock()
        self.hide = MagicMock()
        self.destroy = MagicMock()


@pytest.fixture
def window():
    return FakeWindow()


@pytest.fixture
def tray(window):
    return SystemTrayManager(window=window)


def test_create_default_icon_returns_rgba_image():
    """Default icon should be a 64x64 RGBA PIL Image."""
    img = _create_default_icon()
    assert img.size == (64, 64)
    assert img.mode == "RGBA"


def test_create_default_icon_custom_size():
    """Default icon respects custom size parameter."""
    img = _create_default_icon(size=128)
    assert img.size == (128, 128)


def test_load_icon_falls_back_to_default():
    """When no icon file exists, _load_icon returns a generated image."""
    img = _load_icon()
    # Should return a valid PIL Image regardless
    assert img.size[0] > 0
    assert img.size[1] > 0


def test_system_tray_creation(tray):
    """SystemTrayManager initializes without starting the icon."""
    assert tray._icon is None
    assert tray.is_visible() is False


@patch("src.system_tray.Icon", create=True)
@patch("src.system_tray.Menu", create=True)
@patch("src.system_tray.MenuItem", create=True)
def test_system_tray_start(mock_menuitem, mock_menu, mock_icon_cls, tray):
    """start() creates an Icon and calls run_detached()."""
    mock_icon = MagicMock()
    mock_icon_cls.return_value = mock_icon

    # Patch the pystray import inside start()
    import types
    fake_pystray = types.ModuleType("pystray")
    fake_pystray.Icon = mock_icon_cls
    fake_pystray.Menu = mock_menu
    fake_pystray.MenuItem = mock_menuitem

    with patch.dict("sys.modules", {"pystray": fake_pystray}):
        tray.start()

    mock_icon_cls.assert_called_once()
    mock_icon.run_detached.assert_called_once()
    assert tray.is_visible() is True


def test_system_tray_stop(tray):
    """stop() calls icon.stop() and clears the reference."""
    mock_icon = MagicMock()
    tray._icon = mock_icon  # Simulate started state

    assert tray.is_visible() is True
    tray.stop()
    mock_icon.stop.assert_called_once()
    assert tray.is_visible() is False


def test_system_tray_stop_idempotent(tray):
    """Calling stop() when not started should be safe."""
    tray.stop()  # Should not raise
    assert tray.is_visible() is False


def test_toggle_window_hides_when_visible(tray, window):
    """_toggle_window hides window when currently visible."""
    tray._visible = True
    tray._toggle_window(MagicMock(), MagicMock())

    window.hide.assert_called_once()
    assert tray._visible is False


def test_toggle_window_shows_when_hidden(tray, window):
    """_toggle_window shows window when currently hidden."""
    tray._visible = False
    tray._toggle_window(MagicMock(), MagicMock())

    window.show.assert_called_once()
    assert tray._visible is True


def test_quit_stops_tray_and_calls_callback(window):
    """_quit stops the tray icon and invokes the on_quit callback."""
    quit_callback = MagicMock()
    mock_icon = MagicMock()

    tray = SystemTrayManager(window=window, on_quit=quit_callback)
    tray._icon = mock_icon  # Simulate started state

    tray._quit(MagicMock(), MagicMock())

    mock_icon.stop.assert_called_once()
    quit_callback.assert_called_once()


def test_quit_without_callback(tray):
    """_quit with no on_quit callback should not raise."""
    tray._quit(MagicMock(), MagicMock())  # Should not raise


def test_is_visible_reflects_icon_state(tray):
    """is_visible() returns True when icon is running, False when stopped."""
    assert tray.is_visible() is False

    mock_icon = MagicMock()
    tray._icon = mock_icon
    assert tray.is_visible() is True

    tray.stop()
    assert tray.is_visible() is False
