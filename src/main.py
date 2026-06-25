"""Entry point for simple-edge-tts application.

Launches a PyWebView window that loads the React frontend (Vite dev server
in development, built assets in production). Python backend is exposed to
JavaScript via the Api class (window.pywebview.api.*).

System tray icon (pystray) provides Show/Hide + Quit controls.

Ref: T16 — PyWebView entry point + IPC bridge
Ref: T20 — System tray via pystray
"""

import logging
import os
import sys
from pathlib import Path

import webview

from src.api import Api
from src.audio_player import AudioPlayer
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, shutdown_event_loop
from src.system_tray import SystemTrayManager

VITE_DEV_URL = "http://localhost:5173"


def _get_base_dir() -> Path:
    """Get base path for bundled data files.

    Ref: #66 — PyInstaller strips the src/ prefix from the entry point,
    so __file__ = _internal/main.py (not _internal/src/main.py).
    Path(__file__).parent.parent goes one level too high, making
    FRONTEND_DIST.exists() = False → fallback to dev mode → white screen.

    In frozen mode, sys._MEIPASS points to the correct data root
    (_internal/ for onedir, Contents/Resources/ for .app).
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).parent.parent


TRANSLATIONS_DIR = _get_base_dir() / "src" / "resources" / "translations"
FRONTEND_DIST = _get_base_dir() / "frontend" / "dist" / "index.html"


def _is_dev_mode() -> bool:
    """Detect if running in development mode.

    Development mode is active when:
    - SIMPLE_EDGE_TTS_DEV env var is set, OR
    - The built frontend doesn't exist (fallback to Vite dev server)

    In frozen (PyInstaller) mode, missing frontend is a packaging error
    and raises RuntimeError instead of silently falling back to dev server.
    Ref: #66 — silent fallback hid the broken path resolution.
    """
    if os.environ.get("SIMPLE_EDGE_TTS_DEV"):
        return True
    if getattr(sys, "frozen", False):
        if not FRONTEND_DIST.exists():
            raise RuntimeError(
                f"Packaged frontend not found at {FRONTEND_DIST}. "
                f"This is a packaging error. "
                f"_MEIPASS={getattr(sys, '_MEIPASS', 'N/A')}"
            )
        return False
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

    # Wire Api to the webview window for native file dialogs (folder picker)
    # Ref: #50 — Output folder selector
    api.set_window(window)

    # Ref: T20 — System tray (pystray): Show/Hide window, Quit app
    # Ref: #47 — Quit handler must stop tray + event loop before
    # destroying the window, otherwise daemon threads hang at shutdown.
    def _on_quit():
        audio_player.begin_shutdown()  # Ref: #77 — prevent _eval_js deadlock
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

    # Ref: #63 — Inject audio player bridge JS into WebView on page load.
    # audio_player_bridge.js defines window.audioPlayerBridge (IIFE) which
    # AudioPlayer.play() calls via evaluate_js(). Without injection, the
    # bridge global is undefined and playAudio() silently fails.
    _bridge_js_path = _get_base_dir() / "src" / "static" / "js" / "audio_player_bridge.js"

    def _on_loaded():
        try:
            bridge_js = _bridge_js_path.read_text(encoding="utf-8")
            window.evaluate_js(bridge_js)
        except Exception:
            logging.getLogger(__name__).warning(
                "Failed to inject audio bridge JS from %s", _bridge_js_path,
                exc_info=True,
            )

    window.events.loaded += _on_loaded

    # Ref: #43 — Pre-fetch voice list while the default executor is still
    # alive. After webview.start() blocks the main thread, Python's atexit
    # may shut down the default executor, breaking aiohttp DNS resolution.
    # Cached voices will be served by TTSEngine.get_voices_sync().
    tts_engine.prefetch_voices()

    webview.start()

    # Ref: #47 — Clean up when webview exits normally (window closed via
    # title-bar X, not via tray Quit). Ensures event loop thread is joined
    # and tray is stopped so Python exits cleanly.
    audio_player.begin_shutdown()  # Ref: #77 — prevent _eval_js deadlock
    tray.stop()
    shutdown_event_loop()


if __name__ == "__main__":
    main()
