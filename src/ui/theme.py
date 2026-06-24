"""QSS theme definitions for light and dark modes. Follows OS setting."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

LIGHT_QSS = """
QMainWindow {
    background-color: #f5f5f7;
}
QLabel {
    color: #1d1d1f;
}
QTextEdit {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #d2d2d7;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #007aff;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QPushButton {
    background-color: #007aff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #0066d6;
}
QPushButton:disabled {
    background-color: #d2d2d7;
    color: #86868b;
}
QPushButton#exportButton {
    background-color: #34c759;
}
QPushButton#exportButton:hover {
    background-color: #2db84d;
}
QGroupBox {
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 20px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #86868b;
    font-weight: 600;
    font-size: 12px;
}
QStatusBar {
    color: #86868b;
    font-size: 12px;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
"""

DARK_QSS = """
QMainWindow {
    background-color: #1c1c1e;
}
QLabel {
    color: #f5f5f7;
}
QTextEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
}
QComboBox {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #3a3a3c;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0a84ff;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QPushButton {
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #409cff;
}
QPushButton:disabled {
    background-color: #3a3a3c;
    color: #636366;
}
QPushButton#exportButton {
    background-color: #30d158;
}
QPushButton#exportButton:hover {
    background-color: #4de06e;
}
QGroupBox {
    border: 1px solid #3a3a3c;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 20px;
    background-color: #2c2c2e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #8e8e93;
    font-weight: 600;
    font-size: 12px;
}
QStatusBar {
    color: #8e8e93;
    font-size: 12px;
}
QLineEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
"""


def is_dark_mode() -> bool:
    """Detect whether the OS is in dark mode."""
    hints = QApplication.instance().styleHints()
    if hasattr(hints, "colorScheme"):
        return hints.colorScheme() == Qt.ColorScheme.Dark
    palette = QApplication.instance().palette()
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


def apply_theme(app: QApplication):
    """Apply light or dark QSS based on OS color scheme."""
    qss = DARK_QSS if is_dark_mode() else LIGHT_QSS
    app.setStyleSheet(qss)
