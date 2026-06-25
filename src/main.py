"""Entry point for simple-edge-tts application.

Launches a PyWebView window that loads the React frontend (Vite dev server
in development, built assets in production). Python backend is exposed to
JavaScript via the Api class (window.pywebview.api.*).

System tray icon (pystray) provides Show/Hide + Quit controls.

Ref: T16 — PyWebView entry point + IPC bridge
Ref: T20 — System tray via pystray
"""

import os
from pathlib import Path

import webview

from src.api import Api
from src.audio_player import AudioPlayer
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, shutdown_event_loop
from src.system_tray import SystemTrayManager

TRANSLATIONS_DIR = Path(__file__).parent / "resources" / "translations"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist" / "index.html"
VITE_DEV_URL = "http://localhost:5173"


def _is_dev_mode() -> bool:
    """Detect if running in development mode.

    Development mode is active when:
    - SIMPLE_EDGE_TTS_DEV env var is set, OR
    - The built frontend doesn't exist (fallback to Vite dev server)
    """
    if os.environ.get("SIMPLE_EDGE_TTS_DEV"):
        return True
    return not FRONTEND_DIST.exists()


def _get_frontend_url() -> str:
    """Return the URL or file path for the frontend.

    In dev mode, returns the Vite dev server URL.
    In production, returns the path to the built index.html.
    """
    if _is_dev_mode():
        return VITE_DEV_URL
    return str(FRONTEND_DIST)


def main():
    """Launch the application."""
    config = ConfigManager()
    i18n = I18n(config.get("language"), translations_dir=TRANSLATIONS_DIR)
    tts_engine = TTSEngine()
    audio_player = AudioPlayer()

    api = Api(tts_engine, config, audio_player, i18n)

    url = _get_frontend_url()

    window = webview.create_window(
        title="Simple Edge TTS",
        url=url,
        js_api=api,
        width=1200,
        height=750,
        min_size=(900, 550),
    )

    # Wire AudioPlayer to the webview window for JS bridge communication
    audio_player.set_webview_window(window)

    # Ref: T20 — System tray (pystray): Show/Hide window, Quit app
    # Ref: #47 — Quit handler must stop tray + event loop before
    # destroying the window, otherwise daemon threads hang at shutdown.
    def _on_quit():
        tray.stop()
        shutdown_event_loop()
        window.destroy()

    tray = SystemTrayManager(
        window=window,
        on_quit=_on_quit,
    )

    # Start tray before webview — on macOS, pystray creates NSStatusItem
    # which requires the main thread. webview.start() blocks the main thread,
    # and its `func` callback runs in a worker thread, so tray.start() must
    # come first. pystray runs its own event loop in a background thread.
    tray.start()

    # Ref: #43 — Pre-fetch voice list while the default executor is still
    # alive. After webview.start() blocks the main thread, Python's atexit
    # may shut down the default executor, breaking aiohttp DNS resolution.
    # Cached voices will be served by TTSEngine.get_voices_sync().
    tts_engine.prefetch_voices()

    webview.start()

    # Ref: #47 — Clean up when webview exits normally (window closed via
    # title-bar X, not via tray Quit). Ensures event loop thread is joined
    # and tray is stopped so Python exits cleanly.
    tray.stop()
    shutdown_event_loop()


if __name__ == "__main__":
    main()
