"""Entry point for simple-edge-tts application."""

import sys
from pathlib import Path

from src.app import create_app
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.ui.main_window import MainWindow


TRANSLATIONS_DIR = Path(__file__).parent / "resources" / "translations"


def main():
    """Launch the application."""
    app = create_app()
    config = ConfigManager()
    i18n = I18n(config.get("language"), translations_dir=TRANSLATIONS_DIR)
    window = MainWindow(i18n=i18n, config=config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
