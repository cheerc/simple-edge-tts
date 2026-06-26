"""Wraps edge-tts: list voices, generate audio, format parameters.

Ref: T28 — Persistent event loop thread to avoid asyncio.run() crashes
in PyWebView's threading model.
"""

import asyncio
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import edge_tts

logger = logging.getLogger(__name__)

VOICE_GROUP_ORDER = ["zh-TW", "en-US"]

# Ref: #95 — Network timeout for voice list fetch.
# aiohttp's default ClientTimeout has all fields None (no timeout),
# which can hang indefinitely on Windows behind firewalls/proxies.
_VOICE_FETCH_TIMEOUT = 10  # seconds (asyncio.wait_for)

# Ref: #95 — Reduced from 30s; aiohttp now has its own 10s timeout,
# so Python-level timeout only needs a modest buffer.
_RUN_ASYNC_TIMEOUT = 15  # seconds (future.result)

# --- Persistent event loop (module-level singleton) ---
# PyWebView calls JS API methods from background threads. Using asyncio.run()
# creates and destroys event loops, causing "cannot schedule new futures after
# interpreter shutdown" when the default executor is torn down. Instead, we
# keep one event loop alive in a daemon thread and schedule all coroutines
# onto it via run_coroutine_threadsafe().
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _ensure_selector_policy() -> None:
    """On Windows, switch to SelectorEventLoop policy for aiohttp compat.

    Windows defaults to ProactorEventLoop which is incompatible with
    aiohttp's DNS resolver (used by edge-tts). This causes voice list
    fetches to hang indefinitely on Windows.

    Must be called from the main thread before any event loop is created.
    Ref: #95 — Windows app startup hang due to ProactorEventLoop.
    """
    if sys.platform == "win32":
        # WindowsSelectorEventLoopPolicy only exists on Windows
        policy = asyncio.WindowsSelectorEventLoopPolicy()  # type: ignore[attr-defined]
        asyncio.set_event_loop_policy(policy)


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return the persistent event loop, creating it on first call.

    Sets a custom ThreadPoolExecutor so that Python's atexit handler
    (which shuts down the *default* executor) does not break DNS
    resolution in aiohttp/edge-tts while the loop is still alive.
    Ref: #43 — aiohttp DNS resolve depends on ThreadPoolExecutor.
    Ref: #95 — SelectorEventLoop policy is set by main() before we run.
    """
    global _loop, _thread
    with _lock:
        if _loop is None or _loop.is_closed():
            logger.debug("Creating persistent event loop")
            _loop = asyncio.new_event_loop()
            # Ref: #43 — Use a self-managed executor so atexit doesn't kill it
            _loop.set_default_executor(ThreadPoolExecutor(max_workers=4))
            _thread = threading.Thread(
                target=_loop.run_forever, daemon=True, name="async-event-loop"
            )
            _thread.start()
            logger.debug("Event loop thread started (daemon)")
    return _loop


def run_async(coro):
    """Run an async coroutine on the persistent event loop.

    Thread-safe. Blocks until the coroutine completes or times out.

    Args:
        coro: An awaitable coroutine.

    Returns:
        The coroutine's return value.

    Raises:
        TimeoutError: If the coroutine doesn't complete within the timeout.
    """
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    logger.debug("Waiting for coroutine on event loop (timeout=%ds)", _RUN_ASYNC_TIMEOUT)
    try:
        return future.result(timeout=_RUN_ASYNC_TIMEOUT)
    except TimeoutError:
        logger.warning("run_async timed out after %ds, cancelling coroutine to prevent leakage", _RUN_ASYNC_TIMEOUT)
        future.cancel()
        raise


def shutdown_event_loop(timeout: float = 5.0) -> None:
    """Gracefully stop the persistent event loop and join its thread.

    Must be called during app quit, before Python's finalization attempts
    to join daemon threads. Without this, _Py_Finalize deadlocks on the
    async-event-loop thread blocked in run_forever().

    Safe to call multiple times or when no loop exists.
    Ref: #47 — prevent shutdown hang from daemon thread join.
    """
    global _loop, _thread
    with _lock:
        loop = _loop
        thread = _thread
        _loop = None
        _thread = None

    if loop is not None and loop.is_running():
        loop.call_soon_threadsafe(loop.stop)

    if thread is not None and thread.is_alive():
        thread.join(timeout=timeout)


async def _fetch_voices_with_timeout() -> list[Any]:
    """Fetch voice list with explicit network timeout.

    edge_tts.list_voices() uses aiohttp.ClientSession with no timeout
    by default (ClientTimeout all None), which can hang indefinitely
    on Windows behind firewalls or proxies.

    This wrapper applies two safety measures:
    1. asyncio.wait_for() — cancels the coroutine after _VOICE_FETCH_TIMEOUT
    2. aiohttp.TCPConnector(force_close=True) — avoids connection pool issues

    Ref: #95 — aiohttp ClientTimeout + frozen-env TCP connect/SSL hang.
    """
    connector = aiohttp.TCPConnector(force_close=True)
    return await asyncio.wait_for(
        edge_tts.list_voices(connector=connector),
        timeout=_VOICE_FETCH_TIMEOUT,
    )


def _load_fallback_voices() -> list[Any]:
    """Load the bundled fallback voices JSON file.

    Returns:
        A list of voice dicts, or empty list if the file cannot be loaded.
    """
    try:
        import json
        if getattr(sys, "frozen", False):
            base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        else:
            base_dir = Path(__file__).parent.parent

        fallback_path = base_dir / "src" / "resources" / "fallback_voices.json"
        if fallback_path.exists():
            with open(fallback_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            logger.warning("Fallback voices file not found at %s", fallback_path)
    except Exception as e:
        logger.error("Failed to load fallback voices: %s", e, exc_info=True)
    return []



def format_rate(value: int) -> str:
    return f"+{value}%" if value >= 0 else f"{value}%"


def format_pitch(value: int) -> str:
    return f"+{value}Hz" if value >= 0 else f"{value}Hz"


def sanitize_filename(text: str, max_len: int = 8) -> str:
    if not text.strip():
        return "untitled"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]', "_", text)
    cleaned = cleaned.strip()[:max_len]
    return cleaned if cleaned else "untitled"


def make_output_filename(text: str) -> str:
    prefix = sanitize_filename(text)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.mp3"


class TTSEngine:
    """Synchronous-facing wrapper around async edge-tts."""

    def __init__(self) -> None:
        self._voices_cache: list[Any] | None = None

    def prefetch_voices(self) -> None:
        """Pre-fetch voice list and store in cache.

        Call before webview.start() blocks the main thread, while the
        default ThreadPoolExecutor is still alive.  If the fetch fails
        (e.g. network error), the cache stays None and get_voices_sync()
        will fall back to an online fetch.
        Ref: #43 — pre-fetch voices before executor shutdown.
        Ref: #95 — use _fetch_voices_with_timeout for network-level timeout.
        """
        try:
            self._voices_cache = run_async(_fetch_voices_with_timeout())
        except Exception:
            # Network error — load fallback voices to ensure the dropdown is not empty
            # Ref: #95 — log the failure for diagnostics on Windows.
            logger.warning("Voice prefetch failed, loading fallback voices into cache",
                           exc_info=True)
            self._voices_cache = _load_fallback_voices()

    def get_voices_sync(self) -> list[Any]:
        # Ref: #43 — return cached voices if available (pre-fetched)
        if self._voices_cache is not None:
            return self._voices_cache
        # Ref: #95 — graceful degradation: if online fetch also fails,
        # return empty list so the frontend can show an error state
        # instead of hanging the IPC bridge indefinitely.
        try:
            return run_async(_fetch_voices_with_timeout())
        except Exception:
            logger.error("Voice list fetch failed, falling back to local voice list", exc_info=True)
            return _load_fallback_voices()

    def get_grouped_voices_sync(self) -> OrderedDict[str, list[dict]]:
        voices = self.get_voices_sync()
        groups: dict[str, list[dict]] = {}
        for v in voices:
            locale = v.get("Locale", "unknown")
            groups.setdefault(locale, []).append(v)

        ordered = OrderedDict()
        for key in VOICE_GROUP_ORDER:
            if key in groups:
                ordered[key] = groups.pop(key)
        for key in sorted(groups.keys()):
            ordered[key] = groups[key]
        return ordered

    async def generate(
        self,
        text: str,
        voice: str,
        output_path: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ):
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
