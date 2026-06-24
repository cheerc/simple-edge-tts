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
