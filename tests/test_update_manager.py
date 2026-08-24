"""Tests for update_manager — download, verify, install state machine.

Ref: #179 — Auto-update download & install
"""

import hashlib
import os
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

        with pytest.raises(UpdateError, match="update_install_permission_denied"):
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


class TestMacOSCopyInPlace:
    """Test #191 — _macos_copy in-place replacement for non-/Applications locations."""

    # A realistic-looking .app bundle path for in-place testing
    FAKE_APP = "/Users/test/Downloads/SimpleEdgeTTS.app"

    def _setup_ready_mgr_with_dmg(self):
        """Create an UpdateManager with a fake downloaded DMG ready for copy."""
        mgr = UpdateManager(current_version="0.1.0")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()
        mgr._downloaded_path = Path(tmp.name)
        mgr._macos_app_name = "SimpleEdgeTTS.app"
        self._cleanup_tmp = tmp
        return mgr

    @patch("sys.platform", "darwin")
    @patch("src.update_manager.UpdateManager._app_is_in_applications_dir", return_value=False)
    @patch("src.update_manager.os.access", return_value=True)
    @patch("src.update_manager.UpdateManager._macos_dir_allows_install", return_value=True)
    @patch("src.update_manager.os.rename")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    @patch("tempfile.gettempdir", return_value="/tmp")
    def test_not_in_applications_writable_installs_in_place(
        self, mock_tmpdir, mock_run, mock_rmtree, mock_rename,
        mock_probe, mock_access, mock_in_apps
    ):
        """App not in /Applications + dir writable + TCC probe passes → in-place replace."""
        mgr = self._setup_ready_mgr_with_dmg()

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.glob", return_value=[Path("/tmp/mnt/SimpleEdgeTTS.app")]), \
             patch("sys.executable", self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"):
            mgr._macos_copy()

        # Verify: installed to original location, NOT /Applications
        assert mgr._macos_installed_app is not None
        assert str(mgr._macos_installed_app) != str(Path("/Applications/SimpleEdgeTTS.app"))
        assert mgr._macos_installed_app == Path(self.FAKE_APP)
        # Verify old app was moved aside atomically (Ref #220 — dst has .old suffix)
        rename_dsts = [str(c[0][1]) for c in mock_rename.call_args_list]
        assert any(".old" in d for d in rename_dsts), \
            f"Expected .old backup in rename destinations: {rename_dsts}"

    @patch("sys.platform", "darwin")
    @patch("src.update_manager.UpdateManager._app_is_in_applications_dir", return_value=False)
    @patch("src.update_manager.os.access", return_value=False)
    @patch("src.update_manager.os.rename")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    @patch("tempfile.gettempdir", return_value="/tmp")
    def test_not_writable_parent_raises_localized_error_without_relocation(
        self, mock_tmpdir, mock_run, mock_rmtree, mock_rename, mock_access, mock_in_apps
    ):
        """Issue #233 — non-writable parent → localized permission error;
        the app is NEVER relocated to /Applications."""
        mgr = self._setup_ready_mgr_with_dmg()

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.glob", return_value=[Path("/tmp/mnt/SimpleEdgeTTS.app")]), \
             patch("sys.executable", self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"):
            with pytest.raises(UpdateError) as exc_info:
                mgr._macos_copy()

        assert str(exc_info.value) == "update_install_permission_denied"
        assert mgr._macos_installed_app is None
        rename_targets = [str(c.args[1]) for c in mock_rename.call_args_list if c.args]
        assert not any("/Applications/" in t for t in rename_targets), (
            f"silent relocation attempted: {rename_targets}"
        )

    @patch("sys.platform", "darwin")
    @patch("src.update_manager.UpdateManager._app_is_in_applications_dir", return_value=True)
    @patch("shutil.rmtree")
    @patch("shutil.move")
    @patch("subprocess.run")
    @patch("tempfile.gettempdir", return_value="/tmp")
    def test_in_applications_swap_unchanged(
        self, mock_tmpdir, mock_run, mock_move, mock_rmtree, mock_in_apps
    ):
        """App IS in /Applications → atomic swap behavior unchanged."""
        mgr = self._setup_ready_mgr_with_dmg()

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.glob", return_value=[Path("/tmp/mnt/SimpleEdgeTTS.app")]):
            mgr._macos_copy()

        # Verify: installed to /Applications (existing behavior preserved)
        assert mgr._macos_installed_app == Path("/Applications/SimpleEdgeTTS.app")


class TestMacOSTCCProbe:
    """Test #220 — TCC probe before Case 1 in-place replace.

    macOS TCC denies the app's own rmtree/move inside e.g. ~/Downloads
    even though os.access(W_OK) reports True (it only checks POSIX
    permission). A rename-probe detects this before destructive moves.
    """

    FAKE_APP = "/Users/test/Downloads/SimpleEdgeTTS.app"

    def _setup_ready_mgr_with_dmg(self):
        """Create an UpdateManager with a fake downloaded DMG ready for copy."""
        mgr = UpdateManager(current_version="0.1.0")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()
        mgr._downloaded_path = Path(tmp.name)
        mgr._macos_app_name = "SimpleEdgeTTS.app"
        self._cleanup_tmp = tmp
        return mgr

    def test_probe_returns_false_when_rename_denied(self):
        """Rename failure (PermissionError) → probe False despite W_OK True."""
        real_access = os.access
        with patch("os.access", side_effect=lambda p, m: real_access(p, m)), \
             patch.object(Path, "rename", side_effect=PermissionError(1, "Operation not permitted")), \
             patch("pathlib.Path.unlink"):
            mgr = self._setup_ready_mgr_with_dmg()
            assert mgr._macos_dir_allows_install(Path("/Users/test/Downloads")) is False

    def test_probe_cleans_up_probe_file(self):
        """Successful probe removes its temp file and returns True."""
        calls = []

        def fake_rename(self, target):  # noqa: ARG001 — patched method receives self
            calls.append(("rename", str(target)))

        def fake_unlink(self, *args, **kwargs):
            calls.append(("unlink", ""))

        with patch("pathlib.Path.write_text", lambda self, s: None), \
             patch.object(Path, "rename", fake_rename), \
             patch.object(Path, "unlink", fake_unlink):
            mgr = UpdateManager(current_version="0.1.0")
            assert mgr._macos_dir_allows_install(Path("/Users/test/Downloads")) is True
            assert any(op == "unlink" for op, _ in calls)

    @patch("sys.platform", "darwin")
    @patch("src.update_manager.UpdateManager._app_is_in_applications_dir", return_value=False)
    @patch("src.update_manager.os.access", return_value=True)
    @patch("src.update_manager.UpdateManager._macos_dir_allows_install", return_value=False)
    @patch("src.update_manager.os.rename")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    @patch("tempfile.gettempdir", return_value="/tmp")
    def test_tcc_denied_raises_localized_error_without_relocation(
        self, mock_tmpdir, mock_run, mock_rmtree, mock_rename,
        mock_probe, mock_access, mock_in_apps
    ):
        """Issue #233 — W_OK True but TCC probe denied → localized permission
        error; no /Applications relocation is attempted."""
        mgr = self._setup_ready_mgr_with_dmg()

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.glob", return_value=[Path("/tmp/mnt/SimpleEdgeTTS.app")]), \
             patch("sys.executable", self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"):
            with pytest.raises(UpdateError) as exc_info:
                mgr._macos_copy()

        assert str(exc_info.value) == "update_install_permission_denied"
        assert mgr._macos_installed_app is None
        rename_targets = [str(c.args[1]) for c in mock_rename.call_args_list if c.args]
        assert not any("/Applications/" in t for t in rename_targets), (
            f"silent relocation attempted: {rename_targets}"
        )

    @patch("sys.platform", "darwin")
    @patch("src.update_manager.UpdateManager._app_is_in_applications_dir", return_value=False)
    @patch("src.update_manager.os.access", return_value=True)
    @patch("src.update_manager.UpdateManager._macos_dir_allows_install", return_value=True)
    @patch("src.update_manager.os.rename")
    @patch("shutil.rmtree")
    @patch("subprocess.run")
    @patch("tempfile.gettempdir", return_value="/tmp")
    def test_probe_ok_keeps_in_place_replace(
        self, mock_tmpdir, mock_run, mock_rmtree, mock_rename,
        mock_probe, mock_access, mock_in_apps
    ):
        """W_OK True and TCC probe passes → in-place replace preserved."""
        mgr = self._setup_ready_mgr_with_dmg()

        with patch("pathlib.Path.mkdir"), \
             patch("pathlib.Path.glob", return_value=[Path("/tmp/mnt/SimpleEdgeTTS.app")]), \
             patch("sys.executable", self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"):
            mgr._macos_copy()

        assert mgr._macos_installed_app == Path(self.FAKE_APP)


class TestWindowsRestart:
    """Test #202 — Windows restart must not inherit stale _MEIPASS env.

    PyInstaller one-file mode sets _MEIPASS in the parent's environment.
    The update-restart .bat inherits it, so the NEW exe resolves its
    bundled resources against the OLD (deleted) temp dir and crashes.
    Fix: scrub _MEIPASS from the Popen env and reset it inside the bat
    before `start`, plus set PYINSTALLER_RESET_ENVIRONMENT=1 on both.
    """

    # Windows-only subprocess flag; absent on macOS where tests run.
    CREATE_NO_WINDOW = 0x08000000

    def _make_mgr(self):
        mgr = UpdateManager(current_version="0.1.0")
        mgr._windows_new_exe = Path("/tmp/update/simple-edge-tts-new.exe")
        return mgr

    @patch("sys.platform", "win32")
    @patch("subprocess.CREATE_NO_WINDOW", CREATE_NO_WINDOW, create=True)
    @patch("subprocess.Popen")
    @patch("pathlib.Path.write_text")
    @patch("src.update_manager.UpdateManager._install_cleanup")
    @patch("sys.executable", "/app/simple-edge-tts.exe")
    def test_popen_env_scrubs_meipass(
        self, mock_cleanup, mock_write, mock_popen
    ):
        """Popen env: no _MEIPASS, has PYINSTALLER_RESET_ENVIRONMENT=1."""
        mgr = self._make_mgr()

        with patch.dict(os.environ, {"_MEIPASS": "/old/_MEI1234", "PATH": os.environ.get("PATH", "")}):
            with pytest.raises(SystemExit):
                mgr._windows_restart()

        mock_popen.assert_called_once()
        env = mock_popen.call_args.kwargs["env"]
        assert "_MEIPASS" not in env
        assert env["PYINSTALLER_RESET_ENVIRONMENT"] == "1"
        # Other inherited vars survive the scrub
        assert env["PATH"] == os.environ.get("PATH", "")

    @patch("sys.platform", "win32")
    @patch("subprocess.CREATE_NO_WINDOW", CREATE_NO_WINDOW, create=True)
    @patch("subprocess.Popen")
    @patch("pathlib.Path.write_text")
    @patch("src.update_manager.UpdateManager._install_cleanup")
    @patch("sys.executable", "/app/simple-edge-tts.exe")
    def test_bat_content_resets_env_before_start(
        self, mock_cleanup, mock_write, mock_popen
    ):
        """bat content: set lines present AND before the start line."""
        mgr = self._make_mgr()

        with patch.dict(os.environ, {"_MEIPASS": "/old/_MEI1234"}):
            with pytest.raises(SystemExit):
                mgr._windows_restart()

        bat_content = mock_write.call_args.args[0]
        assert 'set _MEIPASS=' in bat_content
        assert 'set PYINSTALLER_RESET_ENVIRONMENT=1' in bat_content
        start_idx = bat_content.index('start ""')
        meipass_idx = bat_content.index('set _MEIPASS=')
        pyreset_idx = bat_content.index('set PYINSTALLER_RESET_ENVIRONMENT=1')
        assert meipass_idx < start_idx
        assert pyreset_idx < start_idx

    @patch("sys.platform", "win32")
    @patch("subprocess.CREATE_NO_WINDOW", CREATE_NO_WINDOW, create=True)
    @patch("subprocess.Popen")
    @patch("pathlib.Path.write_text")
    @patch("src.update_manager.UpdateManager._install_cleanup")
    @patch("sys.executable", "/app/simple-edge-tts.exe")
    def test_restart_exits_after_launch(
        self, mock_cleanup, mock_write, mock_popen
    ):
        """Existing behavior preserved: launch → cleanup → exit(0)."""
        mgr = self._make_mgr()

        with pytest.raises(SystemExit) as exc_info:
            mgr._windows_restart()

        assert exc_info.value.code == 0
        mock_popen.assert_called_once()
        flags = mock_popen.call_args.kwargs["creationflags"]
        assert flags == self.CREATE_NO_WINDOW


class TestMacOSRestartForensics:
    """Test #221 — restart sequence forensic logging.

    User report: new app starts but the old process survives. Each step
    of the macOS restart must log pid + timestamp (INFO) and the log
    must be flushed BEFORE os._exit so the trail survives the hard exit.
    """

    def _make_mgr(self):
        mgr = UpdateManager(current_version="0.1.0")
        mgr._macos_installed_app = Path("/Applications/SimpleEdgeTTS.app")
        return mgr

    @patch("sys.platform", "darwin")
    @patch("subprocess.Popen")
    @patch("src.update_manager.UpdateManager._install_cleanup")
    @patch("src.update_manager.os._exit", side_effect=SystemExit(0))
    def test_restart_logs_pid_and_timestamp_per_step(
        self, mock_exit, mock_cleanup, mock_popen, caplog
    ):
        """_macos_restart emits INFO records containing its own pid."""
        import logging

        with caplog.at_level(logging.INFO, logger="src.update_manager"):
            mgr = self._make_mgr()
            with pytest.raises(SystemExit):
                mgr._macos_restart()

        joined = "\n".join(r.getMessage() for r in caplog.records)
        assert str(os.getpid()) in joined
        # Steps logged: quarantine removal, launch, cleanup+exit
        for marker in ("quarantine", "launching", "exit"):
            assert any(marker in rec.message.lower() for rec in caplog.records), \
                f"Missing forensic step '{marker}' in:\n{joined}"

    @patch("sys.platform", "darwin")
    @patch("subprocess.Popen")
    @patch("src.update_manager.UpdateManager._install_cleanup")
    @patch("src.update_manager.os._exit", side_effect=SystemExit(0))
    def test_logs_flushed_before_hard_exit(self, mock_exit, mock_cleanup, mock_popen):
        """Handlers are flushed before os._exit so logs survive."""
        import logging

        class FlushProbe(logging.StreamHandler):
            def __init__(self):
                super().__init__()
                self.flushed_count = 0

            def emit(self, record):
                pass

            def flush(self):
                self.flushed_count += 1

        probe = FlushProbe()
        root = logging.getLogger()
        root.addHandler(probe)
        try:
            mgr = self._make_mgr()
            with pytest.raises(SystemExit):
                mgr._macos_restart()
        finally:
            root.removeHandler(probe)

        assert probe.flushed_count > 0, "log handlers were not flushed before os._exit"


class TestCertifiContextUsage:
    """Test #228 — all update_manager urlopen calls use the certifi context.

    Frozen builds fail with CERTIFICATE_VERIFY_FAILED when urllib uses
    the bare default context (system CA roots are not in the bundle).
    urlopen is imported inside each method, so patch src.ssl_utils
    and assert every call site received its context.
    """

    def _fake_response(self, payload=b"{}"):
        response = MagicMock()
        response.read.return_value = payload
        response.headers.get.return_value = None
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        return response

    @patch("urllib.request.urlopen")
    @patch("src.ssl_utils.ssl_context")
    def test_get_platform_asset_uses_certifi(self, mock_ctx, mock_urlopen):
        mock_urlopen.return_value = self._fake_response()
        mgr = UpdateManager(current_version="0.1.0")
        with pytest.raises(UpdateError):
            mgr._get_platform_asset()  # empty release → UpdateError after fetch

        ctx = mock_urlopen.call_args.kwargs["context"]
        assert ctx is mock_ctx.return_value
        mock_ctx.assert_called_once()

    @patch("urllib.request.urlopen")
    @patch("src.ssl_utils.ssl_context")
    def test_fetch_checksums_uses_certifi(self, mock_ctx, mock_urlopen):
        mock_urlopen.return_value = self._fake_response(b"abc123  simple-edge-tts.dmg\n")
        mgr = UpdateManager(current_version="0.1.0")
        release = {"assets": [{"name": "SHA256SUMS.txt",
                                "browser_download_url": "https://example.com/SHA256SUMS.txt"}]}
        result = mgr._fetch_checksums(release)
        assert result == {"simple-edge-tts.dmg": "abc123"}

        ctx = mock_urlopen.call_args.kwargs["context"]
        assert ctx is mock_ctx.return_value

    @patch("urllib.request.urlopen")
    @patch("src.ssl_utils.ssl_context")
    def test_download_asset_uses_certifi(self, mock_ctx, mock_urlopen):
        resp = self._fake_response(b"data")
        resp.read.side_effect = [b"data", b""]
        mock_urlopen.return_value = resp
        mgr = UpdateManager(current_version="0.1.0")
        asset = {"browser_download_url": "https://example.com/simple-edge-tts.exe",
                 "name": "simple-edge-tts.exe"}
        out_path = mgr._download_asset(asset)
        assert out_path.exists()
        out_path.unlink()

        ctx = mock_urlopen.call_args.kwargs["context"]
        assert ctx is mock_ctx.return_value

    def test_update_checker_shares_ssl_utils(self):
        """update_checker now delegates to src.ssl_utils (no second copy)."""
        import inspect

        import src.update_checker

        source = inspect.getsource(src.update_checker)
        assert "ssl_utils" in source


class TestInstallRestartHandoff:
    """Test #221 — restart handoff coordination with the main-thread exit path.

    install() tears down the UI (shutdown_handler → window.destroy) on the
    JS bridge thread; pywebview's main loop then returns from webview.start()
    and main() runs its normal-exit os._exit(0). The runtime log showed the
    old process exiting BEFORE _macos_restart ever launched the new app.
    The manager must expose a handoff state so the exit path can defer until
    the restart sequence is done.
    """

    def _ready_mgr(self):
        mgr = UpdateManager(current_version="0.1.0")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 10)
        tmp.close()
        mgr._downloaded_path = Path(tmp.name)
        mgr._state = UpdateState.READY
        return mgr

    def _run_install_macos(self, mgr, shutdown_handler):
        """Drive real install() on darwin with copy/verify stubbed and the
        macOS restart boundaries patched (xattr no-op, Popen recorded,
        os._exit recorded then SystemExit)."""
        def fake_copy():
            mgr._macos_installed_app = Path("/Applications/SimpleEdgeTTS.app")

        with patch("sys.platform", "darwin"), \
             patch("src.update_manager.UpdateManager._preflight_install"), \
             patch("src.update_manager.UpdateManager._copy_files", side_effect=fake_copy), \
             patch("src.update_manager.UpdateManager._verify_install"), \
             patch("subprocess.run"), \
             patch("subprocess.Popen") as mock_popen, \
             patch("src.update_manager.os._exit", side_effect=SystemExit(0)) as mock_exit:
            mock_popen.side_effect = lambda *a, **k: ("launch-new-app",)
            mock_exit.side_effect = lambda code: (_ for _ in ()).throw(SystemExit(code))
            with pytest.raises(SystemExit):
                mgr.install(shutdown_handler)
        return mock_popen, mock_exit

    def test_not_pending_before_install(self):
        mgr = self._ready_mgr()
        assert mgr.restart_in_progress() is False

    def test_pending_by_the_time_shutdown_handler_runs(self):
        observed = {}

        def handler():
            observed["pending_in_handler"] = mgr.restart_in_progress()

        mgr = self._ready_mgr()
        self._run_install_macos(mgr, handler)

        assert observed["pending_in_handler"] is True, (
            "restart handoff must be armed BEFORE shutdown_handler destroys "
            "the window, or the main thread can exit first (Ref #221)"
        )

    def test_not_pending_after_completion(self):
        mgr = self._ready_mgr()
        self._run_install_macos(mgr, lambda: None)
        assert mgr.restart_in_progress() is False

    def test_wait_released_after_restart_sequence(self):
        order = []

        def handler():
            order.append("shutdown")

        mgr = self._ready_mgr()
        self._run_install_macos(mgr, handler)

        # Main thread's bounded wait must return promptly once the restart
        # sequence finished (hard-exit raised through the finally).
        import time
        start = time.monotonic()
        done = mgr.wait_for_restart_completion(timeout_secs=5)
        elapsed = time.monotonic() - start

        assert done is True
        assert elapsed < 5
        assert order == ["shutdown"]

    def test_complete_set_even_when_restart_fails(self):
        """If _restart raises, the main thread must not wait forever."""
        def handler():
            pass

        mgr = self._ready_mgr()
        with patch("sys.platform", "darwin"), \
             patch("src.update_manager.UpdateManager._preflight_install"), \
             patch("src.update_manager.UpdateManager._copy_files"), \
             patch("src.update_manager.UpdateManager._verify_install"), \
             patch(
                 "src.update_manager.UpdateManager._macos_restart",
                 side_effect=RuntimeError("open failed"),
             ):
            with pytest.raises(RuntimeError):
                mgr.install(handler)

        assert mgr.restart_in_progress() is False
        assert mgr.wait_for_restart_completion(timeout_secs=1) is True


class TestMacOSTCCBundleDenial:
    """Test #220 field evidence — the rename PROBE passes but moving the
    signed .app bundle itself is TCC-denied (Errno 1 on CodeResources).

    v0.1.5 log: probe-created dotfile renames fine in ~/Downloads, yet
    shutil.move of SimpleEdgeTTS.app → .app.old failed mid-rmtree and left
    a half-copied .old behind. Case 1 must therefore attempt an ATOMIC
    bundle rename and fall back to /Applications (or raise the localized
    permission error) WITHOUT any destructive mutation of the original.
    """

    FAKE_APP = "/Users/test/Downloads/SimpleEdgeTTS.app"
    DENY_MARK = "/Downloads/SimpleEdgeTTS.app"

    def _setup_ready_mgr_with_dmg(self):
        mgr = UpdateManager(current_version="0.1.0")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".dmg")
        tmp.write(b"\x00" * 100)
        tmp.close()
        mgr._downloaded_path = Path(tmp.name)
        mgr._macos_app_name = "SimpleEdgeTTS.app"
        return mgr

    @staticmethod
    def _make_fs_policy(successful_mutations, denied_calls, deny_marks):
        """Build rename/move/rmtree doubles that deny every operation whose
        src or dst touches a deny_mark (the TCC-protected bundles) and
        record everything else as a successful mutation."""

        def hits_mark(*parts):
            joined = " ".join(str(p) for p in parts)
            return any(mark in joined for mark in deny_marks)

        def fake_rename(src, dst):
            if hits_mark(src, dst):
                denied_calls.append(("rename", str(src), str(dst)))
                raise PermissionError(1, "Operation not permitted")
            successful_mutations.append(("rename", str(src), str(dst)))

        def fake_move(src, dst):
            if hits_mark(src, dst):
                denied_calls.append(("move", str(src), str(dst)))
                raise PermissionError(1, "Operation not permitted")
            successful_mutations.append(("move", str(src), str(dst)))

        def fake_rmtree(path, *args, **kwargs):
            if hits_mark(path):
                denied_calls.append(("rmtree", str(path)))
                raise PermissionError(1, "Operation not permitted")
            successful_mutations.append(("rmtree", str(path)))

        return fake_rename, fake_move, fake_rmtree

    def _patch_common(self):
        return [
            patch("sys.platform", "darwin"),
            patch("src.update_manager.UpdateManager._app_is_in_applications_dir", return_value=False),
            patch("src.update_manager.os.access", return_value=True),
            patch("src.update_manager.UpdateManager._macos_dir_allows_install", return_value=True),
            patch("subprocess.run"),
            patch("tempfile.gettempdir", return_value="/tmp"),
        ]

    def _with_copy_env(self, sys_executable_app):
        return [
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.glob", return_value=[Path("/tmp/mnt/SimpleEdgeTTS.app")]),
            patch("sys.executable", sys_executable_app),
        ]

    def test_probe_passes_but_bundle_denied_raises_localized_error(self):
        """Issue #233 field evidence — the probe passes yet moving the signed
        bundle itself is TCC-denied. The updater must raise the localized
        permission error WITHOUT relocating to /Applications and WITHOUT any
        successful mutation of the original bundle."""
        successful, denied = [], []
        fake_rename, fake_move, fake_rmtree = self._make_fs_policy(
            successful, denied, [self.DENY_MARK]
        )
        mgr = self._setup_ready_mgr_with_dmg()

        stacks = self._patch_common() + self._with_copy_env(
            self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"
        ) + [
            patch("src.update_manager.os.rename", side_effect=fake_rename),
            patch("shutil.move", side_effect=fake_move),
            patch("shutil.rmtree", side_effect=fake_rmtree),
        ]
        for stack in stacks:
            stack.start()
        try:
            with pytest.raises(UpdateError) as exc_info:
                mgr._macos_copy()
        finally:
            for stack in stacks:
                stack.stop()

        assert str(exc_info.value) == "update_install_permission_denied"
        # No second installation was created anywhere…
        relocated = [
            m for m in successful if "/Applications/" in " ".join(m)
        ]
        assert not relocated, f"Silent /Applications install attempted: {relocated}"
        # …and no destructive operation against the Downloads bundle succeeded.
        leaked = [m for m in successful if self.DENY_MARK in " ".join(m)]
        assert not leaked, f"Destructive mutation escaped TCC denial: {leaked}"
        assert denied, "Expected at least one denied bundle operation"
        assert mgr._macos_installed_app is None

    def test_in_place_success_when_permitted(self):
        """Issue #233 — with permissions available, a non-/Applications app
        is replaced IN PLACE at its original path; /Applications is never
        touched."""
        successful, denied = [], []
        fake_rename, fake_move, fake_rmtree = self._make_fs_policy(
            successful, denied, []  # nothing denied — fully permitted host
        )
        mgr = self._setup_ready_mgr_with_dmg()

        stacks = self._patch_common() + self._with_copy_env(
            self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"
        ) + [
            patch("src.update_manager.os.rename", side_effect=fake_rename),
            patch("shutil.move", side_effect=fake_move),
            patch("shutil.rmtree", side_effect=fake_rmtree),
        ]
        for stack in stacks:
            stack.start()
        try:
            mgr._macos_copy()
        finally:
            for stack in stacks:
                stack.stop()

        # Installed at the ORIGINAL running location (location-preserving)
        assert mgr._macos_installed_app == Path(self.FAKE_APP)
        rename_dsts = [str(m[2]) for m in successful if m[0] == "rename"]
        assert any(".old" in d for d in rename_dsts), (
            f"Expected atomic .old backup rename: {successful}"
        )
        apps_touched = [m for m in successful if "/Applications/" in " ".join(m)]
        assert not apps_touched, f"/Applications must not be touched: {apps_touched}"

    def test_total_denial_raises_localized_permission_error(self):
        """Neither ~/Downloads nor /Applications updatable → localized
        UpdateError before any irreversible step; never a raw Errno 1."""
        successful, denied = [], []
        deny_marks = [
            self.DENY_MARK,
            "/Applications/SimpleEdgeTTS.app",
        ]
        fake_rename, fake_move, fake_rmtree = self._make_fs_policy(
            successful, denied, deny_marks
        )
        mgr = self._setup_ready_mgr_with_dmg()

        stacks = self._patch_common() + self._with_copy_env(
            self.FAKE_APP + "/Contents/MacOS/simple-edge-tts"
        ) + [
            patch("src.update_manager.os.rename", side_effect=fake_rename),
            patch("shutil.move", side_effect=fake_move),
            patch("shutil.rmtree", side_effect=fake_rmtree),
        ]
        for stack in stacks:
            stack.start()
        try:
            with pytest.raises(UpdateError) as exc_info:
                mgr._macos_copy()
        finally:
            for stack in stacks:
                stack.stop()

        # Localized i18n key — NOT the raw "[Errno 1] Operation not permitted"
        assert str(exc_info.value) == "update_install_permission_denied"
        # Nothing was irreversibly mutated anywhere.
        leaked = [
            m for m in successful
            if any(mark in " ".join(m) for mark in deny_marks)
        ]
        assert not leaked, f"Irreversible mutation under total denial: {leaked}"


class TestGetPlatformAssetSelection:
    """Issue #234 — Windows must select simple-edge-tts-windows.zip.

    The v0.1.7 release exposes BOTH simple-edge-tts-macos.zip and
    simple-edge-tts-windows.zip; a first-.zip-wins loop downloads the
    macOS bundle archive on Windows and install fails with
    "No .exe found in downloaded archive". Selection must match the
    platform-specific suffix emitted by release.yml, and a missing
    platform asset must fail closed with the available names listed.
    """

    RELEASE_ASSETS = [
        {"name": "SHA256SUMS.txt", "browser_download_url": "u/SUMS"},
        {"name": "simple-edge-tts-macos.zip", "browser_download_url": "u/macos"},
        {"name": "simple-edge-tts-windows.zip", "browser_download_url": "u/win"},
        {"name": "simple-edge-tts.dmg", "browser_download_url": "u/dmg"},
    ]

    def _mgr(self):
        return UpdateManager(current_version="0.1.7")

    def _release_json(self, assets):
        import json

        return json.dumps({"assets": assets}).encode()

    @patch("sys.platform", "win32")
    @patch("urllib.request.urlopen")
    def test_windows_selects_windows_zip_among_both_zips(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = self._release_json(self.RELEASE_ASSETS)
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        asset = self._mgr()._get_platform_asset()

        assert asset["name"] == "simple-edge-tts-windows.zip"
        assert asset["browser_download_url"] == "u/win"

    @patch("sys.platform", "darwin")
    @patch("urllib.request.urlopen")
    def test_macos_still_selects_dmg(self, mock_urlopen):
        resp = MagicMock()
        resp.read.return_value = self._release_json(self.RELEASE_ASSETS)
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        asset = self._mgr()._get_platform_asset()

        assert asset["name"] == "simple-edge-tts.dmg"

    @patch("urllib.request.urlopen")
    def test_missing_platform_asset_fails_closed_listing_available(self, mock_urlopen):
        """No windows zip in the release → actionable error naming assets."""
        resp = MagicMock()
        resp.read.return_value = self._release_json(
            [a for a in self.RELEASE_ASSETS if a["name"] != "simple-edge-tts-windows.zip"]
        )
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = resp

        mgr = self._mgr()
        with patch("sys.platform", "win32"):
            with pytest.raises(UpdateError) as exc_info:
                mgr._get_platform_asset()

        message = str(exc_info.value)
        assert "simple-edge-tts-macos.zip" in message, (
            f"error must list available assets for triage: {message}"
        )
