"""Runtime log persistence configuration (Issue #99).

Sets up rotating file logging with cross-platform log directory
resolution. Works in both development (uv run) and frozen (PyInstaller)
modes so diagnostic output is preserved across app sessions.

Usage:
    from src.logging_config import setup_logging
    setup_logging()  # call once at start of main()
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path

# Format shared by file and console handlers.
# Example: "2026-01-15 14:30:02,123 src.tts_engine INFO Voicing..."
LOG_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Rotation: 1 MB per file, keep last 5 backups (~5 MB total max).
_MAX_BYTES = 1_048_576  # 1 MiB
_BACKUP_COUNT = 5

# Module-level logger — used only during setup; modules should use
# logging.getLogger(__name__) for their own loggers.
logging_config_logger = logging.getLogger(__name__)


def _get_log_dir() -> Path:
    """Return the platform-appropriate log directory.

    macOS:    ~/Library/Logs/simple-edge-tts/
    Windows:  If running a frozen build, returns the folder containing the executable (.exe).
              Otherwise, falls back to %LOCALAPPDATA%/simple-edge-tts/logs/
    Linux:    ~/.local/share/simple-edge-tts/logs/
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "simple-edge-tts"

    if sys.platform == "win32":
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA", "")
        if not base:
            # Ultimate fallback — should be rare
            base = str(Path.home() / "AppData" / "Local")
        return Path(base) / "simple-edge-tts" / "logs"

    # Linux / other POSIX: XDG data dir
    xdg_data = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
    return Path(xdg_data) / "simple-edge-tts" / "logs"


def _get_log_level() -> int:
    """Return the log level based on environment.

    When SIMPLE_EDGE_TTS_DEV is set, use DEBUG for maximum visibility
    during development. Otherwise, use INFO — verbose enough for
    post-mortem diagnosis without overwhelming the log file.
    """
    if os.environ.get("SIMPLE_EDGE_TTS_DEV"):
        return logging.DEBUG
    return logging.INFO


def setup_logging() -> None:
    """Configure the root logger with rotating file + console output.

    This should be called once at the start of main(), before any
    logging.getLogger() calls produce output.

    Handlers:
    - RotatingFileHandler: writes to disk with rotation (1 MB × 5 backups)
    - StreamHandler: writes to stderr for console visibility

    The log file path is printed to stderr on first call so users can
    locate the file even when running a PyInstaller-frozen build.

    Idempotent: calling this twice will not add duplicate handlers.
    """
    root = logging.getLogger()

    # Guard against double-init
    already_set_up = any(
        isinstance(h, logging.handlers.RotatingFileHandler)
        for h in root.handlers
    )
    if already_set_up:
        return

    log_dir = _get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Log file name includes the start timestamp so each run has its own file
    # while rotation handles size limits within a run.
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"simple-edge-tts_{timestamp}.log"

    # Format
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        filename=str(log_file),
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)  # File captures everything

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)  # Console stays at INFO

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    level = _get_log_level()
    root.setLevel(level)

    # Print log path so users can find it even in frozen builds
    print(f"[simple-edge-tts] Log: {log_file}", file=sys.stderr)

    logging_config_logger.info("Logging initialised — level=%s, dir=%s",
                               logging.getLevelName(level), log_dir)
