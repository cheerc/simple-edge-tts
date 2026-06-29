"""Tests for update_manager — download, verify, install state machine.

Ref: #179 — Auto-update download & install
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.update_manager import UpdateManager, UpdateState, UpdateError


class TestUpdateState:
    """Test UpdateState enum values."""

    def test_all_states_defined(self):
        assert UpdateState.IDLE.value == "idle"
        assert UpdateState.DOWNLOADING.value == "downloading"
        assert UpdateState.VERIFYING.value == "verifying"
        assert UpdateState.READY.value == "ready"
        assert UpdateState.INSTALLING.value == "installing"
        assert UpdateState.ERROR.value == "error"


class TestUpdateManagerInit:
    """Test UpdateManager initialisation."""

    def test_initial_state_is_idle(self):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr.state == UpdateState.IDLE

    def test_initial_progress_is_zero(self):
        mgr = UpdateManager(current_version="0.1.0")
        info = mgr.get_progress()
        assert info["state"] == "idle"
        assert info["progress"] == 0

    def test_current_version_stored(self):
        mgr = UpdateManager(current_version="0.2.0")
        assert mgr.current_version == "0.2.0"


class TestStateMachine:
    """Test download state machine transitions."""

    def patch_download_deps(self, mgr, *, checksum_ok=True):
        """Patch internal helpers so download() runs without real network."""
        mgr._get_platform_asset = MagicMock(return_value={
            "release": {"tag_name": "v0.2.0", "html_url": "https://example.com"},
            "name": "SimpleEdgeTTS-0.2.0.dmg",
            "browser_download_url": "https://example.com/asset.dmg",
        })
        mgr._fetch_checksums = MagicMock(return_value={
            "SimpleEdgeTTS-0.2.0.dmg": "abc123",
        })

        # Create a real temp file to download to
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()

        mgr._download_asset = MagicMock(return_value=Path(tmp.name))
        if checksum_ok:
            mgr._verify_sha256 = MagicMock()  # no-op
        else:
            mgr._verify_sha256 = MagicMock(side_effect=UpdateError("SHA256 mismatch"))

        self._tmp = tmp  # keep alive

    def test_idle_to_downloading_to_ready(self):
        mgr = UpdateManager(current_version="0.1.0")
        self.patch_download_deps(mgr)

        assert mgr.state == UpdateState.IDLE

        path = mgr.download()

        assert mgr.state == UpdateState.READY
        assert path is not None

    def test_download_sets_progress_callback(self):
        mgr = UpdateManager(current_version="0.1.0")
        self.patch_download_deps(mgr)

        progress_values = []

        # Simulate _download_asset calling the progress callback
        # (on_progress is a positional arg after asset)
        def fake_download(asset, on_progress):
            if on_progress is not None:
                on_progress(50)
                on_progress(100)
            return Path(self._tmp.name)

        mgr._download_asset = fake_download
        mgr._get_platform_asset = MagicMock(return_value={
            "release": {"tag_name": "v0.2.0", "html_url": "https://example.com"},
            "name": "SimpleEdgeTTS-0.2.0.dmg",
            "browser_download_url": "https://example.com/asset.dmg",
        })
        mgr._fetch_checksums = MagicMock(return_value={
            "SimpleEdgeTTS-0.2.0.dmg": "abc123",
        })
        mgr._verify_sha256 = MagicMock()

        mgr.download(on_progress=lambda pct: progress_values.append(pct))
        assert mgr.state == UpdateState.READY
        assert len(progress_values) == 2
        assert progress_values == [50, 100]

    def test_double_download_raises_reentrancy_error(self):
        mgr = UpdateManager(current_version="0.1.0")
        self.patch_download_deps(mgr)

        # First download
        mgr.download()
        assert mgr.state == UpdateState.READY

        # Second download should raise
        with pytest.raises(UpdateError, match="Cannot start download"):
            mgr.download()

    def test_state_error_after_verification_failure(self):
        mgr = UpdateManager(current_version="0.1.0")
        self.patch_download_deps(mgr, checksum_ok=False)

        with pytest.raises(UpdateError, match="SHA256"):
            mgr.download()

        assert mgr.state == UpdateState.ERROR


class TestCancelFlag:
    """Test cancel flag propagation."""

    def test_cancel_sets_flag(self):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr.is_cancelled() is False
        mgr.cancel()
        assert mgr.is_cancelled() is True

    def test_cancel_flag_reset_on_new_download(self):
        mgr = UpdateManager(current_version="0.1.0")
        mgr.cancel()
        assert mgr.is_cancelled() is True

        # Start a download — cancel flag should be cleared
        mgr._get_platform_asset = MagicMock(return_value={
            "release": {"tag_name": "v0.2.0"},
            "name": "test.dmg",
            "browser_download_url": "https://example.com/test.dmg",
        })
        mgr._fetch_checksums = MagicMock(return_value={"test.dmg": "abc"})

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()
        mgr._download_asset = MagicMock(return_value=Path(tmp.name))
        mgr._verify_sha256 = MagicMock()

        mgr.download()
        assert mgr.is_cancelled() is False


class TestSHA256Verification:
    """Test SHA256 checksum verification."""

    def test_valid_checksum_passes(self):
        mgr = UpdateManager(current_version="0.1.0")
        content = b"hello world test content"
        expected = hashlib.sha256(content).hexdigest()

        # Create temp file with a name that matches the checksum key
        tmp_path = Path(tempfile.gettempdir()) / "test_verify.bin"
        tmp_path.write_bytes(content)

        try:
            # Should not raise — key matches path.name
            mgr._verify_sha256(tmp_path, {"test_verify.bin": expected})
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_mismatched_checksum_raises(self):
        mgr = UpdateManager(current_version="0.1.0")
        content = b"hello world test content"

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(content)
        tmp.close()

        with pytest.raises(UpdateError, match="SHA256"):
            mgr._verify_sha256(Path(tmp.name), {"test.bin": "deadbeef" * 8})

    def test_missing_file_entry_raises(self):
        mgr = UpdateManager(current_version="0.1.0")

        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(b"data")
        tmp.close()

        with pytest.raises(UpdateError, match="SHA256"):
            mgr._verify_sha256(Path(tmp.name), {"other_file.bin": "abc123"})


class TestInstallGuard:
    """Test install() guards."""

    def test_install_not_ready_raises(self):
        mgr = UpdateManager(current_version="0.1.0")
        # State is IDLE, not READY
        with pytest.raises(UpdateError, match="No verified update"):
            mgr.install(lambda: None)

    def test_preflight_fails_when_file_missing(self):
        """Preflight must fail before shutdown_handler() is called."""
        mgr = UpdateManager(current_version="0.1.0")
        # Manually set state to READY without a downloaded file
        mgr._state = UpdateState.READY
        shutdown_called = []

        with pytest.raises(UpdateError, match="Downloaded file not found"):
            mgr.install(lambda: shutdown_called.append(1))

        # Shutdown handler must NOT have been called
        assert len(shutdown_called) == 0

    @patch("sys.platform", "darwin")
    @patch("os.access", return_value=False)
    def test_preflight_macos_not_writable_raises(self, mock_access):
        """Preflight must catch unwritable /Applications/ before shutdown."""
        mgr = UpdateManager(current_version="0.1.0")
        # Simulate a ready download
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()
        mgr._downloaded_path = Path(tmp.name)
        mgr._state = UpdateState.READY
        shutdown_called = []

        with pytest.raises(UpdateError, match="Cannot write to /Applications"):
            mgr.install(lambda: shutdown_called.append(1))

        assert len(shutdown_called) == 0

    @patch("sys.platform", "darwin")
    @patch("os.access", return_value=True)
    def test_preflight_macos_writable_proceeds(self, mock_access):
        """Preflight + copy + verify must succeed before shutdown is called."""
        mgr = UpdateManager(current_version="0.1.0")
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()
        mgr._downloaded_path = Path(tmp.name)
        mgr._state = UpdateState.READY
        # Patch copy/verify/restart phases to avoid real system changes
        mgr._copy_files = MagicMock()
        mgr._verify_install = MagicMock()
        mgr._restart = MagicMock()
        shutdown_called = []

        mgr.install(lambda: shutdown_called.append(1))

        assert len(shutdown_called) == 1
        # copy + verify must happen BEFORE shutdown
        mgr._copy_files.assert_called_once()
        mgr._verify_install.assert_called_once()
        mgr._restart.assert_called_once()


class TestMacOSWritableCheck:
    """Test macOS target directory writability detection."""

    @patch("sys.platform", "darwin")
    @patch("os.access", return_value=True)
    def test_applications_writable(self, mock_access):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._macos_target_is_writable() is True

    @patch("sys.platform", "darwin")
    @patch("os.access", return_value=False)
    def test_applications_not_writable(self, mock_access):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._macos_target_is_writable() is False


class TestGetProgress:
    """Test get_progress() dict structure."""

    def test_progress_has_expected_keys(self):
        mgr = UpdateManager(current_version="0.1.0")
        info = mgr.get_progress()
        assert "state" in info
        assert "progress" in info
        assert "error" in info

    def test_progress_error_is_none_when_no_error(self):
        mgr = UpdateManager(current_version="0.1.0")
        info = mgr.get_progress()
        assert info["error"] is None


class TestPlatformDetection:
    """Test platform-specific helpers."""

    @patch("sys.platform", "darwin")
    def test_macos_platform_detected(self):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._is_macos() is True
        assert mgr._is_windows() is False

    @patch("sys.platform", "win32")
    def test_windows_platform_detected(self):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._is_windows() is True
        assert mgr._is_macos() is False

    @patch("sys.platform", "darwin")
    @patch("sys.executable", "/Applications/SimpleEdgeTTS.app/Contents/MacOS/simple-edge-tts")
    def test_macos_app_in_applications(self):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._app_is_in_applications_dir() is True

    @patch("sys.platform", "darwin")
    @patch("sys.executable", "/Users/test/Downloads/SimpleEdgeTTS.app/Contents/MacOS/simple-edge-tts")
    def test_macos_app_not_in_applications(self):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._app_is_in_applications_dir() is False


class TestWindowsWritableCheck:
    """Test Windows install path writable check."""

    @patch("sys.platform", "win32")
    @patch("os.access", return_value=True)
    def test_writable_check_passes(self, mock_access):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._install_dir_is_writable() is True

    @patch("sys.platform", "win32")
    @patch("os.access", return_value=False)
    def test_writable_check_fails(self, mock_access):
        mgr = UpdateManager(current_version="0.1.0")
        assert mgr._install_dir_is_writable() is False
