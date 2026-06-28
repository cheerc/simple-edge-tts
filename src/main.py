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
from src.logging_config import setup_logging, start_diagnostic_monitor
from src.tts_engine import TTSEngine, shutdown_event_loop, _ensure_selector_policy
from src.system_tray import SystemTrayManager

logger = logging.getLogger(__name__)

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


def execute_quit_shutdown(audio_player, api, tray, window):
    """Execute the tray Quit shutdown sequence.

    Extracted from main() for testability (#112).  All cleanup calls are
    idempotent — safe to call even if the window-closing path has already run.
    """
    audio_player.begin_shutdown()  # Ref: #77 — prevent _eval_js deadlock
    api.cleanup_preview_files()  # Ref: #123 — clean up preview tempfiles
    tray.stop()
    shutdown_event_loop()
    window.destroy()


def execute_window_closing_shutdown(audio_player, api, window):
    """Execute the window closing shutdown sequence.

    Extracted from main() for testability (#112).  Monkey-patches
    window.evaluate_js to prevent pywebview _call threads from deadlocking
    during shutdown.  The monkey-patch guard ensures the patch is applied
    only once even when both shutdown paths fire.
    """
    audio_player.begin_shutdown()  # Ref: #77 — set shutdown flag
    api.cleanup_preview_files()  # Ref: #123 — clean up preview tempfiles
    original = getattr(window, '_original_evaluate_js', None)
    if original is None:  # Only patch once
        window._original_evaluate_js = window.evaluate_js
        def safe_evaluate_js(script, callback=None):
            if audio_player._shutting_down:
                return None
            return window._original_evaluate_js(script, callback)
        window.evaluate_js = safe_evaluate_js


def inject_audio_bridge_js(window, bridge_js_path):
    """Inject the audio player bridge JavaScript into the WebView.

    Extracted from main() for testability (#114).  Reads the bridge JS
    file and evaluates it in the WebView so that window.audioPlayerBridge
    is available for AudioPlayer.play().

    Args:
        window: The pywebview window object.
        bridge_js_path: Path to the audio_player_bridge.js file.

    Returns:
        True if injection succeeded, False otherwise.
    """
    try:
        bridge_js = bridge_js_path.read_text(encoding="utf-8")
        window.evaluate_js(bridge_js)
        return True
    except Exception:
        return False


def main():
    """Launch the application."""
    # Ref: #99 — File-based logging for runtime diagnostics.
    # Must be called before anything else so all subsequent logger output
    # is captured to disk (vital for PyInstaller-frozen builds).
    setup_logging()
    # Ref: #117 — Only run the diagnostic thread monitor in dev mode.
    # In production builds the 5s stack dump fills log rotation with noise.
    if _is_dev_mode():
        start_diagnostic_monitor(interval_seconds=5.0)
    logger.info("Application starting - base_dir=%s, dev_mode=%s", _get_base_dir(), _is_dev_mode())

    # Ref: #95 — Must be called on the main thread before any event loop
    # is created. On Windows this switches the global asyncio policy from
    # ProactorEventLoop (incompatible with aiohttp DNS) to SelectorEventLoop.
    _ensure_selector_policy()

    config = ConfigManager()
    i18n = I18n(config.get("language"), translations_dir=TRANSLATIONS_DIR)
    tts_engine = TTSEngine()
    audio_player = AudioPlayer()

    api = Api(tts_engine, config, audio_player, i18n)

    url = _get_frontend_url()
    logger.info("Loading frontend URL: %s", url)

    theme = config.get("theme") or "dark"
    bg_color = "#fafafa" if theme == "light" else "#1a1a2e"

    # Ref: #73 & #108 — Set background_color dynamically based on the last saved
    # theme to prevent theme flash on startup.
    window = webview.create_window(
        title="Simple Edge TTS",
        url=url,
        js_api=api,
        width=1200,
        height=750,
        min_size=(900, 550),
        background_color=bg_color,
    )

    # Wire AudioPlayer to the webview window for JS bridge communication
    audio_player.set_webview_window(window)

    # Wire Api to the webview window for native file dialogs (folder picker)
    # Ref: #50 — Output folder selector
    api.set_window(window)

    # Ref: T20 — System tray (pystray): Show/Hide window, Quit app
    # Ref: #47 — Quit handler must stop tray + event loop before
    # destroying the window, otherwise daemon threads hang at shutdown.
    # Ref: #112 — Lambda provides late-binding for tray (solves circular dependency).
    tray = SystemTrayManager(
        window=window,
        on_quit=lambda: execute_quit_shutdown(audio_player, api, tray, window),
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
    # Ref: #114 — extracted to module-level inject_audio_bridge_js() for testability.
    _bridge_js_path = _get_base_dir() / "src" / "static" / "js" / "audio_player_bridge.js"

    def _on_loaded():
        logger.info("WebView loaded event triggered")
        ok = inject_audio_bridge_js(window, _bridge_js_path)
        if ok:
            logger.info("Audio player bridge JS successfully injected")
        else:
            logger.warning(
                "Failed to inject audio bridge JS from %s", _bridge_js_path,
                exc_info=True,
            )

    window.events.loaded += _on_loaded

    # Ref: #77 — Monkey-patch window.evaluate_js on close to prevent
    # pywebview's internal _call threads from deadlocking. These threads
    # call evaluate_js() to return JS API results via Cocoa's
    # AppHelper.callAfter() + Semaphore.acquire(). After the window
    # closes and NSRunLoop exits, callAfter never executes and the
    # semaphore never releases → hang. Making evaluate_js a no-op
    # during shutdown lets those threads complete harmlessly.
    # Ref: #112 — Extracted to module-level execute_window_closing_shutdown.
    window.events.closing += lambda: execute_window_closing_shutdown(audio_player, api, window)

    # Ref: #73 — Defer voice prefetch to after the window is displayed.
    # webview.start(func=...) runs the callback in a background thread
    # after the window is shown, so the UI appears instantly while voices
    # are fetched in the background. prefetch_voices() uses the persistent
    # event loop (Ref: #43) which has its own ThreadPoolExecutor, so it's
    # safe to call after the main thread enters webview.start().
    logger.info("Calling webview.start() event loop")
    webview.start(func=tts_engine.prefetch_voices)

    # Ref: #47 — Clean up when webview exits normally (window closed via
    # title-bar X, not via tray Quit). Ensures event loop thread is joined
    # and tray is stopped so Python exits cleanly.
    # All calls are idempotent so safe to run even if _on_quit() already did them.
    logger.info("webview.start() finished. Starting normal exit cleanup...")
    audio_player.begin_shutdown()  # Ref: #77 — prevent _eval_js deadlock
    api.cleanup_preview_files()  # Ref: #123 — clean up preview tempfiles before os._exit(0)
    tray.stop()
    shutdown_event_loop()
    logger.info("Normal exit cleanup complete. Exiting process.")
    os._exit(0)  # Ref: #77 — force-exit to prevent hang from pywebview
                 # _call threads stuck on Semaphore.acquire() during
                 # Python finalization (Py_FinalizeEx thread join)


if __name__ == "__main__":
    main()
