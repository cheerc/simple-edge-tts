"""Tests for src/logging_config.py — runtime log persistence (Issue #99).

This module configures cross-platform file logging with rotation so
diagnostic output is preserved across app sessions, including in
PyInstaller-frozen builds where stderr is invisible.
"""

import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

@pytest.fixture
def clean_logging_after():
    """Restore logging state after each test."""
    yield
    logger = logging.getLogger("simple-edge-tts")
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True
    # Remove all handlers added by setup_logging — both FileHandlers and
    # StreamHandlers — so tests don't accumulate handlers across the run.
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.NOTSET)
    # Reset idempotency flag so tests don't interfere with each other
    import src.logging_config
    src.logging_config._setup_done = False


# ---------------------------------------------------------------------------
# get_log_dir()
# ---------------------------------------------------------------------------

class TestGetLogDir:
    """Tests for _get_log_dir() — cross-platform log directory resolution."""

    def test_macos_log_dir(self):
        """On macOS, log dir is ~/Library/Logs/simple-edge-tts/"""
        from src.logging_config import _get_log_dir
        with patch.object(sys, "platform", "darwin"):
            result = _get_log_dir()
        expected = Path.home() / "Library" / "Logs" / "simple-edge-tts"
        assert result == expected

    def test_windows_log_dir(self):
        """On Windows, log dir is %LOCALAPPDATA%/simple-edge-tts/logs/ when not frozen."""
        from src.logging_config import _get_log_dir
        fake_localappdata = Path(r"C:\Users\test\AppData\Local")
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", False, create=True):
                with patch.dict("os.environ", {"LOCALAPPDATA": str(fake_localappdata)}):
                    result = _get_log_dir()
        expected = fake_localappdata / "simple-edge-tts" / "logs"
        assert result == expected

    def test_windows_fallback_to_appdata(self):
        """On Windows without LOCALAPPDATA, fall back to APPDATA when not frozen."""
        from src.logging_config import _get_log_dir
        fake_appdata = Path(r"C:\Users\test\AppData\Roaming")
        fake_env = {"LOCALAPPDATA": "", "APPDATA": str(fake_appdata)}
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", False, create=True):
                with patch.dict("os.environ", fake_env):
                    result = _get_log_dir()
        expected = fake_appdata / "simple-edge-tts" / "logs"
        assert result == expected

    def test_windows_frozen_writable_log_dir(self):
        """On Windows when frozen and the directory is writable, log dir is the directory of the executable."""
        from src.logging_config import _get_log_dir
        fake_exe = "D:/Program Files/simple-edge-tts/simple-edge-tts.exe"
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", fake_exe):
                    with patch("pathlib.Path.touch") as mock_touch, patch("pathlib.Path.unlink") as mock_unlink:
                        result = _get_log_dir()
                        mock_touch.assert_called_once()
                        mock_unlink.assert_called_once()
        expected = Path("D:/Program Files/simple-edge-tts")
        assert result == expected

    def test_windows_frozen_readonly_fallback(self):
        """On Windows when frozen but the directory is not writable, log dir falls back to LOCALAPPDATA."""
        from src.logging_config import _get_log_dir
        fake_exe = "D:/Program Files/simple-edge-tts/simple-edge-tts.exe"
        fake_localappdata = Path(r"C:\Users\test\AppData\Local")
        with patch.object(sys, "platform", "win32"):
            with patch.object(sys, "frozen", True, create=True):
                with patch.object(sys, "executable", fake_exe):
                    with patch.dict("os.environ", {"LOCALAPPDATA": str(fake_localappdata)}):
                        with patch("pathlib.Path.touch", side_effect=PermissionError()):
                            result = _get_log_dir()
        expected = fake_localappdata / "simple-edge-tts" / "logs"
        assert result == expected

    def test_linux_log_dir(self):
        """On Linux, log dir is ~/.local/share/simple-edge-tts/logs/"""
        from src.logging_config import _get_log_dir
        with patch.object(sys, "platform", "linux"):
            result = _get_log_dir()
        expected = Path.home() / ".local" / "share" / "simple-edge-tts" / "logs"
        assert result == expected


# ---------------------------------------------------------------------------
# _get_log_level()
# ---------------------------------------------------------------------------

class TestGetLogLevel:
    """Tests for _get_log_level() — environment-aware log level."""

    def test_default_is_info(self):
        """Default log level is INFO."""
        from src.logging_config import _get_log_level
        assert _get_log_level() == logging.INFO

    def test_dev_env_sets_debug(self):
        """When SIMPLE_EDGE_TTS_DEV is set, log level is DEBUG."""
        from src.logging_config import _get_log_level
        with patch.dict("os.environ", {"SIMPLE_EDGE_TTS_DEV": "1"}):
            assert _get_log_level() == logging.DEBUG


# ---------------------------------------------------------------------------
# setup_logging()
# ---------------------------------------------------------------------------

class TestSetupLogging:
    """Tests for setup_logging() — main entry point (Issue #99)."""

    def test_creates_log_directory(self, tmp_path, clean_logging_after):
        """setup_logging() creates the log directory if it doesn't exist."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "nonexistent" / "logs"
        assert not log_dir.exists()

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=True)

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_adds_file_handler(self, tmp_path, clean_logging_after):
        """setup_logging() adds a RotatingFileHandler to the root logger."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=True)

        # Verify a FileHandler was added to the root logger
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) == 1
        handler = file_handlers[0]

        # Verify the log file path is inside the log directory
        assert str(handler.baseFilename).startswith(str(log_dir))
        assert handler.baseFilename.endswith(".log")

    def test_formatter_includes_timestamp_module_level_message(
        self, tmp_path, clean_logging_after
    ):
        """The log formatter includes timestamp, module, level, and message."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=True)

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        handler = file_handlers[0]
        fmt = handler.formatter._fmt

        assert "%(asctime)s" in fmt
        assert "%(name)s" in fmt
        assert "%(levelname)s" in fmt
        assert "%(message)s" in fmt

    def test_log_level_is_set(self, tmp_path, clean_logging_after):
        """setup_logging() sets the log level on the root logger to DEBUG."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                with patch("src.logging_config._get_log_level", return_value=logging.INFO):
                    setup_logging(enable_file_logging=True)

        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_prints_log_path_to_stderr(self, tmp_path, clean_logging_after):
        """setup_logging() prints the log file path to stderr."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        mock_stderr = MagicMock()
        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                with patch("sys.stderr", mock_stderr):
                    setup_logging(enable_file_logging=True)

        # Verify stderr.write was called at least once with the log path
        stderr_calls = "".join(
            str(c.args[0]) if c.args else ""
            for c in mock_stderr.write.call_args_list
        )
        assert str(log_dir) in stderr_calls

    def test_rotation_settings(self, tmp_path, clean_logging_after):
        """The RotatingFileHandler has maxBytes and backupCount set for rotation."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=True)

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        handler = file_handlers[0]

        assert handler.maxBytes > 0
        assert handler.backupCount > 0

    def test_idempotent_does_not_add_duplicate_handlers(
        self, tmp_path, clean_logging_after
    ):
        """Calling setup_logging() twice does not add duplicate file handlers."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=True)
                setup_logging(enable_file_logging=True)

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) == 1

    def test_console_handler_still_added(self, tmp_path, clean_logging_after):
        """setup_logging() also adds a StreamHandler for stderr output."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=False)

        root = logging.getLogger()
        stream_handlers = [h for h in root.handlers
                           if isinstance(h, logging.StreamHandler)
                           and not isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(stream_handlers) >= 1

    def test_no_file_handler_when_disabled(self, tmp_path, clean_logging_after):
        """setup_logging(enable_file_logging=False) does not add a RotatingFileHandler."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=False)

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) == 0

    def test_setup_logging_idempotent_when_file_logging_disabled(
        self, tmp_path, clean_logging_after
    ):
        """Calling setup_logging(enable_file_logging=False) twice must not add
        duplicate StreamHandlers — only one console handler should exist."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                setup_logging(enable_file_logging=False)
                setup_logging(enable_file_logging=False)

        root = logging.getLogger()
        # Use strict type() check to exclude pytest's LogCaptureHandler
        # (a StreamHandler subclass) and RotatingFileHandler.
        stream_handlers = [h for h in root.handlers
                           if type(h) is logging.StreamHandler]
        assert len(stream_handlers) == 1, (
            f"Expected 1 StreamHandler, got {len(stream_handlers)}: "
            f"{[type(h).__name__ for h in root.handlers]}"
        )

    def test_setup_logging_reads_from_config(self, tmp_path, clean_logging_after):
        """setup_logging() with no arguments reads enable_file_logging from ConfigManager."""
        from src.logging_config import setup_logging
        log_dir = tmp_path / "logs"
        log_dir.mkdir(parents=True)

        with patch("src.logging_config._get_log_dir", return_value=log_dir):
            with patch("src.logging_config.logging_config_logger"):
                # ConfigManager is lazily imported from src.config_manager,
                # so we patch it at its real home.
                with patch("src.config_manager.ConfigManager") as MockCM:
                    mock_instance = MockCM.return_value
                    mock_instance.get.return_value = True
                    setup_logging()

        root = logging.getLogger()
        file_handlers = [h for h in root.handlers
                         if isinstance(h, logging.handlers.RotatingFileHandler)]
        assert len(file_handlers) == 1, (
            f"Expected 1 RotatingFileHandler when config says True, got {len(file_handlers)}"
        )
