"""Application-level setup: theme, high-DPI, font."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.theme import apply_theme


def create_app(argv=None) -> QApplication:
    """Create and configure the QApplication instance."""
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
