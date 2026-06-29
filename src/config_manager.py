"""Manages persistent application configuration via JSON file."""

import json
import os
import shutil
import sys
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
    "auto_check_update": True,
    "skip_version": None,
}


def _get_config_dir() -> Path:
    """Return the platform-appropriate config directory.

    Uses OS-standard app data locations, separate from log directory.

    macOS:    ~/Library/Application Support/simple-edge-tts/
    Windows:  If running a frozen build, returns the folder containing the
              executable (.exe) when writable.  Otherwise, falls back to
              %APPDATA%/simple-edge-tts/config/
    Linux:    $XDG_CONFIG_HOME/simple-edge-tts/  (default ~/.config/simple-edge-tts/)
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "simple-edge-tts"

    if sys.platform == "win32":
        # Ref: #166 — frozen portable build: prefer exe directory so the
        # .exe can run portably from a USB stick / folder without leaving
        # traces in %APPDATA%.  Mirror _get_log_dir() write-test pattern.
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).parent
            try:
                test_file = exe_dir / ".config_write_test"
                test_file.touch()
                test_file.unlink()
                return exe_dir
            except Exception:
                pass

        base = os.environ.get("APPDATA", "")
        if not base:
            base = str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "simple-edge-tts" / "config"

    # Linux / other POSIX: XDG config dir
    xdg_config = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
    return Path(xdg_config) / "simple-edge-tts"


class ConfigManager:
    """Read/write application config with defaults and corrupt-file recovery."""

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            config_dir = _get_config_dir()
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._data: dict[str, Any] = dict(DEFAULTS)

        # Auto-migrate from legacy location (log dir) if new location is empty
        if not self._config_file.exists():
            self._migrate_from_legacy_log_dir()

        self._load()

    def _migrate_from_legacy_log_dir(self) -> None:
        """Copy config from legacy log-directory location if present.

        Before #148, config.json lived in the log directory.  On first
        run after the migration we detect the legacy file and copy it
        into the new OS app-data location so users don't lose settings.
        """
        try:
            from src.logging_config import _get_log_dir
            legacy_file = _get_log_dir() / "config.json"
        except Exception:
            return
        if not legacy_file.exists():
            return
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_file, self._config_file)
        except OSError:
            pass  # best-effort — _load() will fall back to defaults

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
