"""Entry point for simple-edge-tts application."""

import sys
from pathlib import Path

from src.app import create_app
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.ui.main_window import MainWindow
from src.ui.system_tray import SystemTrayManager


TRANSLATIONS_DIR = Path(__file__).parent / "resources" / "translations"


def main():
    """Launch the application."""
    app = create_app()
    config = ConfigManager()
    i18n = I18n(config.get("language"), translations_dir=TRANSLATIONS_DIR)
    window = MainWindow(i18n=i18n, config=config)

    # Wire system tray (minimize-to-tray + tray menu)
    tray_mgr = SystemTrayManager(window, i18n)
    window._tray = tray_mgr  # Enables closeEvent minimize-to-tray

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
