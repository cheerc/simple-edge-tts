"""Wraps edge-tts: list voices, generate audio, format parameters."""

import asyncio
import re
from collections import OrderedDict
from datetime import datetime
from typing import Any

import edge_tts

VOICE_GROUP_ORDER = ["zh-TW", "en-US"]


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

    def get_voices_sync(self) -> list[dict[str, Any]]:
        return asyncio.run(edge_tts.list_voices())

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
