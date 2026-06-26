"""Manages persistent application configuration via JSON file."""

import json
from pathlib import Path
from typing import Any


DEFAULTS = {
    "language": "zh-TW",
    "last_voice": "zh-TW-HsiaoChenNeural",
    "rate": "+0%",
    "pitch": "+0Hz",
    "output_dir": str(Path.home() / "Desktop"),
    "window_geometry": {"x": 100, "y": 100, "w": 900, "h": 600},
    "enable_file_logging": False,
    "theme": "dark",
}


class ConfigManager:
    """Read/write application config with defaults and corrupt-file recovery."""

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            from src.logging_config import _get_log_dir
            config_dir = _get_log_dir()
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self):
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass  # corrupt file — keep defaults

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
