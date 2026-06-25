"""Wraps edge-tts: list voices, generate audio, format parameters.

Ref: T28 — Persistent event loop thread to avoid asyncio.run() crashes
in PyWebView's threading model.
"""

import asyncio
import re
import threading
from collections import OrderedDict
from datetime import datetime
from typing import Any

import edge_tts

VOICE_GROUP_ORDER = ["zh-TW", "en-US"]

# --- Persistent event loop (module-level singleton) ---
# PyWebView calls JS API methods from background threads. Using asyncio.run()
# creates and destroys event loops, causing "cannot schedule new futures after
# interpreter shutdown" when the default executor is torn down. Instead, we
# keep one event loop alive in a daemon thread and schedule all coroutines
# onto it via run_coroutine_threadsafe().
_loop: asyncio.AbstractEventLoop | None = None
_thread: threading.Thread | None = None
_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return the persistent event loop, creating it on first call."""
    global _loop, _thread
    with _lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _thread = threading.Thread(
                target=_loop.run_forever, daemon=True, name="async-event-loop"
            )
            _thread.start()
    return _loop


def run_async(coro):
    """Run an async coroutine on the persistent event loop.

    Thread-safe. Blocks until the coroutine completes or times out.

    Args:
        coro: An awaitable coroutine.

    Returns:
        The coroutine's return value.

    Raises:
        TimeoutError: If the coroutine doesn't complete within 30 seconds.
    """
    loop = _get_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result(timeout=30)


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

    def get_voices_sync(self) -> list[Any]:
        return run_async(edge_tts.list_voices())

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
