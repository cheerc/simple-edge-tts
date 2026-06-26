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
import threading
import time
import traceback
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
            exe_dir = Path(sys.executable).parent
            try:
                test_file = exe_dir / ".log_write_test"
                test_file.touch()
                test_file.unlink()
                return exe_dir
            except Exception:
                pass

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


def setup_logging(enable_file_logging: bool | None = None) -> None:
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

    if enable_file_logging is None:
        try:
            from src.config_manager import ConfigManager
            config = ConfigManager()
            enable_file_logging = bool(config.get("enable_file_logging"))
        except Exception:
            enable_file_logging = False

    log_dir = _get_log_dir()

    # Format
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    if enable_file_logging:
        log_dir.mkdir(parents=True, exist_ok=True)

        # Log file name includes the start timestamp so each run has its own file
        # while rotation handles size limits within a run.
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"simple-edge-tts_{timestamp}.log"

        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file),
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # File captures everything
        root.addHandler(file_handler)

        # Print log path so users can find it even in frozen builds
        print(f"[simple-edge-tts] Log: {log_file}", file=sys.stderr)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(_get_log_level())  # Console respects env-specific level

    root.addHandler(console_handler)

    # Root logger level set to DEBUG so console/file handlers filter them accordingly.
    root.setLevel(logging.DEBUG)

    logging_config_logger.info("Logging initialised — level=%s, dir=%s, file_logging=%s",
                               logging.getLevelName(_get_log_level()), log_dir, enable_file_logging)


def start_diagnostic_monitor(interval_seconds: float = 5.0) -> None:
    """Start a background daemon thread that periodically prints stack traces of all Python threads."""
    def monitor():
        logging_config_logger.info("Diagnostic thread monitor started with interval %.1fs", interval_seconds)
        while True:
            try:
                time.sleep(interval_seconds)
                frames = sys._current_frames()
                threads = {t.ident: t for t in threading.enumerate()}

                logging_config_logger.info("=== Thread Diagnostic Snapshot ===")
                logging_config_logger.info("Active threads count: %d", len(threads))

                for thread_id, frame in frames.items():
                    thread = threads.get(thread_id)
                    thread_name = thread.name if thread else f"UnknownThread-{thread_id}"
                    thread_alive = thread.is_alive() if thread else False
                    thread_daemon = thread.daemon if thread else False

                    tb = "".join(traceback.format_stack(frame))
                    logging_config_logger.info(
                        "Thread: %s (ID: %s, Daemon: %s, Alive: %s)\nStack:\n%s",
                        thread_name, thread_id, thread_daemon, thread_alive, tb
                    )
                logging_config_logger.info("==================================")
            except Exception as e:
                logging_config_logger.exception("Error in diagnostic thread monitor: %s", e)

    t = threading.Thread(target=monitor, name="diagnostic-monitor", daemon=True)
    t.start()
