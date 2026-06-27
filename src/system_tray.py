"""System tray icon manager using pystray.

Replaces PySide6 QSystemTrayIcon with cross-platform pystray.
Runs in a detached background thread via pystray's run_detached().

pystray imports are deferred to runtime (not module level) because pystray
attempts to connect to an X display at import time on Linux, which fails
in headless CI environments.

Ref: T20 — Replace PySide6 QSystemTrayIcon with pystray
"""

import threading
from pathlib import Path
from typing import Any, Callable, Optional


def _create_default_icon(size: int = 64):
    """Create a simple default tray icon when no icon file is available.

    Draws a blue circle with a white inner accent to represent Simple Edge TTS.

    Returns:
        A PIL Image (RGBA).
    """
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    # Blue circle background
    draw.ellipse([2, 2, size - 2, size - 2], fill=(66, 133, 244, 255))
    # White inner accent
    inner = size // 4
    draw.ellipse(
        [inner, inner, size - inner, size - inner],
        fill=(255, 255, 255, 255),
    )
    return image


def _load_icon():
    """Load the app icon from resources, falling back to a generated icon.

    Returns:
        A PIL Image.
    """
    from PIL import Image

    icon_path = Path(__file__).parent.parent / "resources" / "icons" / "icon.png"
    if icon_path.exists():
        return Image.open(icon_path)
    return _create_default_icon()


class SystemTrayManager:
    """Manages pystray system tray icon lifecycle and interactions.

    Args:
        window: A pywebview window object with show()/hide() methods.
        on_quit: Optional callback invoked when user selects Quit.
    """

    def __init__(
        self,
        window: Any,
        on_quit: Optional[Callable[[], None]] = None,
    ) -> None:
        self._window = window
        self._on_quit = on_quit
        self._visible = True
        self._icon: Optional[Any] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Create and start the tray icon in a detached thread.

        pystray is imported here (not at module level) to avoid X display
        connection errors on headless CI.
        """
        from pystray import Icon, Menu, MenuItem

        image = _load_icon()
        menu = Menu(
            MenuItem("Show/Hide", self._toggle_window, default=True),
            Menu.SEPARATOR,
            MenuItem("Quit", self._quit),
        )
        self._icon = Icon(
            name="simple-edge-tts",
            icon=image,
            title="Simple Edge TTS",
            menu=menu,
        )
        self._icon.run_detached()

    def stop(self) -> None:
        """Stop and remove the tray icon."""
        with self._lock:
            if self._icon is not None:
                self._icon.stop()
                self._icon = None

    def is_visible(self) -> bool:
        """Return whether the tray icon is currently running."""
        with self._lock:
            return self._icon is not None

    def _toggle_window(self, icon, item) -> None:
        """Toggle the PyWebView window visibility."""
        if self._visible:
            self._window.hide()
            self._visible = False
        else:
            self._window.show()
            self._visible = True

    def _quit(self, icon, item) -> None:
        """Quit the application gracefully."""
        self.stop()
        if self._on_quit is not None:
            self._on_quit()
