"""Update download, verify, and install manager.

Background download with SHA256 verification, state machine with
re-entrancy guard, and platform-specific install (macOS atomic swap,
Windows .bat with CREATE_NO_WINDOW).

Ref: #179 — Auto-update download & install
"""

import hashlib
import logging
import os
import sys
import tempfile
import threading
from enum import Enum
from pathlib import Path
from typing import Callable

from src import ssl_utils

logger = logging.getLogger(__name__)

# GitHub API
GITHUB_API_RELEASES = "https://api.github.com/repos/cheerc/simple-edge-tts/releases/latest"


class UpdateState(Enum):
    """Download-and-install state machine states."""
    IDLE = "idle"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    READY = "ready"
    INSTALLING = "installing"
    ERROR = "error"


class UpdateError(Exception):
    """Raised when an update operation fails."""


class UpdateManager:
    """Manages background download, SHA256 verification, and install.

    State machine: IDLE → DOWNLOADING → VERIFYING → READY → INSTALLING
    Re-entrancy is prevented by a threading.Lock guarding state transitions.
    """

    def __init__(self, current_version: str) -> None:
        self.current_version = current_version
        self._state = UpdateState.IDLE
        self._lock = threading.Lock()
        self._downloaded_path: Path | None = None
        self._progress = 0
        self._cancel_flag = threading.Event()
        self._error_message: str | None = None
        # Ref: #221 — handoff coordination with the main-thread exit path.
        # install() arms the handoff before tearing down the UI; the
        # post-webview.start() block defers its os._exit until the restart
        # sequence finishes (or the bounded wait lapses).
        self._restart_handoff_started = threading.Event()
        self._restart_complete = threading.Event()
        # Ref: #233 — install target stays None until a copy actually
        # succeeded; a permission denial must leave no installed-app state.
        self._macos_installed_app: Path | None = None

    @property
    def state(self) -> UpdateState:
        return self._state

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(self, on_progress: Callable[[int], None] | None = None) -> Path:
        """Download latest release asset in background, then verify SHA256.

        Raises UpdateError if already in progress or verification fails.
        Returns the path to the downloaded + verified file.
        """
        with self._lock:
            if self._state != UpdateState.IDLE:
                raise UpdateError(f"Cannot start download in state {self._state.value}")
            self._state = UpdateState.DOWNLOADING
            self._error_message = None
            self._cancel_flag.clear()

        try:
            asset = self._get_platform_asset()
            checksums = self._fetch_checksums(asset["release"])
            path = self._download_asset(asset, on_progress)

            with self._lock:
                self._state = UpdateState.VERIFYING

            self._verify_sha256(path, checksums)

            with self._lock:
                self._downloaded_path = path
                self._state = UpdateState.READY

            return path
        except Exception:
            with self._lock:
                self._state = UpdateState.ERROR
            raise

    def cancel(self) -> None:
        """Cancel an in-progress download."""
        self._cancel_flag.set()

    def is_cancelled(self) -> bool:
        """Return True if cancel has been requested."""
        return self._cancel_flag.is_set()

    def get_progress(self) -> dict:
        """Return current download state and progress."""
        return {
            "state": self._state.value,
            "progress": self._progress,
            "error": self._error_message,
        }

    def install(self, shutdown_handler: Callable[[], None]) -> None:
        """Run platform-specific install, then restart.

        Order is deliberate (Ref: #179 reviewer findings F2/F3):
        1. Preflight — permission checks, file existence (fail = clean error)
        2. Copy files — ditto/extract BEFORE shutdown (fail = app stays open)
        3. Verify copy — confirm the new bundle is valid
        4. Shutdown — only NOW tear down the UI (copy succeeded)
        5. Restart — launch new version + exit
        """
        with self._lock:
            if self._state != UpdateState.READY:
                raise UpdateError("No verified update ready to install")
            self._state = UpdateState.INSTALLING

        # Steps 1-3: all reversible — app stays open on failure
        self._preflight_install()
        self._copy_files()
        self._verify_install()

        # Step 4: now safe to tear down — copy succeeded
        # Ref: #221 — arm the handoff BEFORE the UI teardown: window.destroy()
        # makes webview.start() return on the main thread, and that thread's
        # normal-exit os._exit(0) must not win the race against step 5.
        self._restart_handoff_started.set()
        try:
            shutdown_handler()
        except Exception:
            # Ref: #221 reopened — a teardown failure must NOT skip the
            # restart: the new app still has to launch and this process
            # still has to exit, or the user is left with "updated but
            # did not restart". The handler already ran the idempotent
            # cleanup steps before failing; log and proceed to step 5.
            logger.exception(
                "Shutdown handler failed during update install — "
                "continuing with restart"
            )

        # Step 5: switch to new version
        try:
            self._restart()
        finally:
            # macOS success hard-exits inside _restart; this release covers
            # failure paths and Windows sys.exit so a waiting main thread
            # never blocks forever.
            self._restart_complete.set()

    def restart_in_progress(self) -> bool:
        """True while install() is between UI teardown and restart completion.

        Ref: #221 — lets main()'s exit path defer os._exit until the
        restart sequence has launched the new app and terminated us.
        """
        return (
            self._restart_handoff_started.is_set()
            and not self._restart_complete.is_set()
        )

    def wait_for_restart_completion(self, timeout_secs: float) -> bool:
        """Block until the restart sequence completes; False on timeout."""
        return self._restart_complete.wait(timeout_secs)

    def _preflight_install(self) -> None:
        """Run platform-specific checks BEFORE shutting down the UI.

        These checks must succeed before we tear down the frontend,
        so any failure can be returned to the user as a clean error
        toast instead of crashing a dying process.

        Ref: #179 reviewer findings F2/F3.
        """
        if self._downloaded_path is None or not self._downloaded_path.exists():
            raise UpdateError("Downloaded file not found — cannot install")

        if self._is_macos():
            if not self._macos_target_is_writable():
                # Ref: #220 — i18n key the frontend maps to a localized guide
                raise UpdateError("update_install_permission_denied")
        elif self._is_windows():
            if not self._install_dir_is_writable():
                raise UpdateError("Install directory is not writable")
        else:
            raise UpdateError(f"Unsupported platform: {sys.platform}")

    # ------------------------------------------------------------------
    # Platform detection helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_macos() -> bool:
        return sys.platform == "darwin"

    @staticmethod
    def _is_windows() -> bool:
        return sys.platform == "win32"

    @staticmethod
    def _app_is_in_applications_dir() -> bool:
        """Return True if the current executable lives under /Applications/."""
        return Path(sys.executable).resolve().parts[:2] == ("/", "Applications")

    @staticmethod
    def _macos_dir_allows_install(directory: Path) -> bool:
        """Return True if the app may rename entries inside `directory`.

        Ref: #220 — os.access(W_OK) only checks POSIX permission; macOS TCC
        denies the app's own file operations in e.g. ~/Downloads (App
        Management) while W_OK still reports True. Probe with a real rename,
        which is exactly what the in-place replace needs.
        """
        probe = directory / f".simple-edge-tts-install-probe-{os.getpid()}"
        try:
            probe.write_text("")
            probe.rename(probe.with_suffix(".probe2"))
        except Exception as e:
            logger.info("TCC install probe denied for %s: %s", directory, e)
            return False
        finally:
            try:
                probe.with_suffix(".probe2").unlink(missing_ok=True)
                probe.unlink(missing_ok=True)
            except Exception:
                pass  # Best-effort cleanup of whichever name remains
        return True

    @staticmethod
    def _install_dir_is_writable() -> bool:
        """Return True if the directory containing the executable accepts a
        real create+delete probe.

        Ref: #236 — os.access(W_OK) alone over-reports writability for
        ACL-restricted or shared/UNC-backed install locations; gate the
        preflight on an actual file operation instead.
        """
        return UpdateManager._dir_allows_write(Path(os.path.dirname(sys.executable)))

    @staticmethod
    def _dir_allows_write(directory: Path) -> bool:
        """Probe `directory` with a real create+delete, not just W_OK.

        Ref: #220 (macOS TCC) showed permission bits can lie in both
        directions; the same applies to Windows ACL / UNC shares.
        """
        try:
            with tempfile.NamedTemporaryFile(
                dir=directory, prefix=".set-write-probe-", delete=False
            ) as probe:
                probe_path = Path(probe.name)
            probe_path.unlink()
            return True
        except Exception as e:
            logger.info("Write probe denied for %s: %s", directory, e)
            return False

    @staticmethod
    def _macos_target_is_writable() -> bool:
        """Return True if the macOS install target directory is writable.

        Checks /Applications/ if the app is already there, otherwise
        checks the parent directory of the current .app bundle.
        """
        target = Path("/Applications")
        if not UpdateManager._app_is_in_applications_dir():
            # App running from elsewhere — check parent of current bundle
            target = Path(sys.executable).resolve().parent.parent.parent
        return os.access(target, os.W_OK)

    # ------------------------------------------------------------------
    # Internal: GitHub Releases asset discovery
    # ------------------------------------------------------------------

    def _get_platform_asset(self) -> dict:
        """Fetch the latest release metadata and pick the platform asset.

        Returns a dict with keys: release, name, browser_download_url.
        """
        import json
        from urllib.request import Request, urlopen

        try:
            req = Request(
                GITHUB_API_RELEASES,
                headers={"User-Agent": f"simple-edge-tts/{self.current_version}"},
            )
            with urlopen(req, timeout=10, context=ssl_utils.ssl_context()) as resp:
                release = json.loads(resp.read())
        except Exception as e:
            raise UpdateError(f"Failed to fetch release info: {e}") from e

        # Find the platform-appropriate asset.
        # Ref: #234 — match the platform-specific suffix emitted by
        # release.yml; a first-.zip-wins loop downloads the macOS archive
        # on Windows (macos.zip sorts before windows.zip).
        is_macos = self._is_macos()
        for asset_data in release.get("assets", []):
            name = asset_data.get("name", "")
            if is_macos and name.endswith(".dmg"):
                return {
                    "release": release,
                    "name": name,
                    "browser_download_url": asset_data["browser_download_url"],
                }
            if not is_macos and name.endswith("-windows.zip"):
                return {
                    "release": release,
                    "name": name,
                    "browser_download_url": asset_data["browser_download_url"],
                }

        # Ref: #234 — fail closed with the available names so the mismatch
        # is actionable instead of silently installing the wrong archive.
        platform_name = "macOS (.dmg)" if is_macos else "Windows (-windows.zip)"
        available = ", ".join(
            a.get("name", "") for a in release.get("assets", [])
        )
        raise UpdateError(
            f"No {platform_name} asset found in latest release "
            f"(available assets: {available})"
        )

    def _fetch_checksums(self, release: dict) -> dict[str, str]:
        """Download SHA256SUMS.txt from the release assets and parse it.

        Returns a dict mapping filename → sha256 hex digest.
        """
        from urllib.request import Request, urlopen

        # Find SHA256SUMS.txt asset
        checksum_url = None
        for asset in release.get("assets", []):
            name = asset.get("name", "")
            if name.lower() in ("sha256sums.txt", "sha256sums"):
                checksum_url = asset["browser_download_url"]
                break

        if checksum_url is None:
            raise UpdateError("No SHA256SUMS.txt found in release assets — cannot verify download")

        try:
            req = Request(
                checksum_url,
                headers={"User-Agent": f"simple-edge-tts/{self.current_version}"},
            )
            with urlopen(req, timeout=10, context=ssl_utils.ssl_context()) as resp:
                content = resp.read().decode("utf-8")
        except Exception as e:
            raise UpdateError(f"Failed to fetch checksums: {e}") from e

        # Parse: <sha256>  <filename>  or  <sha256> *<filename>
        result: dict[str, str] = {}
        for line in content.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                digest = parts[0]
                filename = parts[-1].lstrip("*")
                result[filename] = digest

        if not result:
            raise UpdateError("SHA256SUMS.txt is empty or unparseable")

        return result

    def _download_asset(
        self, asset: dict, on_progress: Callable[[int], None] | None = None
    ) -> Path:
        """Download the release asset to a temp file.

        Reports progress via on_progress(percent) when Content-Length is known.
        Checks _cancel_flag periodically to support cancellation.
        """
        from urllib.request import Request, urlopen

        url = asset["browser_download_url"]
        filename = asset["name"]
        out_dir = Path(tempfile.gettempdir()) / "simple-edge-tts-update"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / filename

        try:
            req = Request(
                url,
                headers={"User-Agent": f"simple-edge-tts/{self.current_version}"},
            )
            with urlopen(req, timeout=60, context=ssl_utils.ssl_context()) as resp:
                total = resp.headers.get("Content-Length")
                total_bytes = int(total) if total else None
                downloaded = 0

                with open(out_path, "wb") as f:
                    while True:
                        if self._cancel_flag.is_set():
                            raise UpdateError("Download cancelled")
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes:
                            pct = min(int(downloaded / total_bytes * 100), 100)
                            self._progress = pct
                            if on_progress:
                                on_progress(pct)
        except UpdateError:
            # Clean up partial download on cancel
            if out_path.exists():
                out_path.unlink(missing_ok=True)
            raise
        except Exception as e:
            if out_path.exists():
                out_path.unlink(missing_ok=True)
            raise UpdateError(f"Download failed: {e}") from e

        return out_path

    # ------------------------------------------------------------------
    # SHA256 verification
    # ------------------------------------------------------------------

    def _verify_sha256(self, path: Path, checksums: dict[str, str]) -> None:
        """Verify the downloaded file against the expected SHA256 digest.

        Raises UpdateError if the file's hash doesn't match or the file
        is not listed in checksums.
        """
        filename = path.name
        if filename not in checksums:
            raise UpdateError(
                f"SHA256 checksum not found for {filename} in SHA256SUMS.txt"
            )

        expected = checksums[filename].lower()
        actual = hashlib.sha256(path.read_bytes()).hexdigest()

        if actual != expected:
            raise UpdateError(
                f"SHA256 mismatch for {filename}: expected {expected[:16]}..., got {actual[:16]}..."
            )

    # ------------------------------------------------------------------
    # Platform install — split into copy / verify / restart phases
    #
    # Ref: #179 reviewer finding F2 — copy + verify happen BEFORE
    # shutdown_handler() so that any failure can be returned as a clean
    # error toast. Restart happens AFTER shutdown.
    # ------------------------------------------------------------------

    def _copy_files(self) -> None:
        """Copy the downloaded files to the install target.

        macOS: mount .dmg, ditto .app → temp, unmount, atomic swap.
        Windows: extract .zip to temp, place .exe alongside current exe.
        Runs BEFORE shutdown_handler() — failure keeps the app open.
        """
        if self._is_macos():
            self._macos_copy()
        elif self._is_windows():
            self._windows_copy()
        else:
            raise UpdateError(f"Unsupported platform: {sys.platform}")

    def _verify_install(self) -> None:
        """Verify the copied files are valid before committing to restart.

        Runs AFTER _copy_files(), BEFORE shutdown_handler().
        """
        if self._is_macos():
            self._macos_verify()
        elif self._is_windows():
            self._windows_verify()
        # else unreachable (already caught in _copy_files)

    def _restart(self) -> None:
        """Launch the new version and exit.

        Runs AFTER shutdown_handler() — the UI is already torn down.
        """
        if self._is_macos():
            self._macos_restart()
        elif self._is_windows():
            self._windows_restart()
        # else unreachable

    # ---- macOS ---------------------------------------------------------

    def _macos_copy(self) -> None:
        """macOS: ditto .app out of .dmg → atomic swap into /Applications."""
        import shutil
        import subprocess

        dmg_path = self._downloaded_path
        if dmg_path is None or not dmg_path.exists():
            raise UpdateError("Downloaded .dmg not found")

        # Mount .dmg
        mount_point = Path(tempfile.gettempdir()) / "simple-edge-tts-update-mount"
        mount_point.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                ["hdiutil", "attach", str(dmg_path), "-mountpoint", str(mount_point),
                 "-nobrowse", "-quiet"],
                check=True,
                timeout=30,
            )

            apps = list(mount_point.glob("*.app"))
            if not apps:
                raise UpdateError("No .app bundle found in .dmg")
            self._macos_app_name = apps[0].name

            # Copy .app to temp with ditto
            temp_app = Path(tempfile.gettempdir()) / "simple-edge-tts-update" / f"{self._macos_app_name}.new"
            if temp_app.exists():
                shutil.rmtree(temp_app)
            self._macos_temp_app = temp_app

            subprocess.run(
                ["ditto", "--noqtn", str(apps[0]), str(temp_app)],
                check=True,
                timeout=60,
            )
        finally:
            subprocess.run(
                ["hdiutil", "detach", str(mount_point), "-quiet"],
                timeout=10,
            )

        # Ref: #191 — In-place replacement for non-/Applications locations
        target_app = Path("/Applications") / self._macos_app_name

        if self._app_is_in_applications_dir():
            # Case 3: App in /Applications → atomic swap (unchanged)
            old_app = Path(str(target_app) + ".old")
            if old_app.exists():
                shutil.rmtree(old_app)
            shutil.move(str(target_app), str(old_app))
            shutil.move(str(self._macos_temp_app), str(target_app))
            self._macos_installed_app = target_app
        else:
            # App NOT in /Applications (Ref: #191) — location-preserving
            # contract (Ref: #233): the target is the bundle that is
            # currently running, wherever it lives.
            original_app = Path(sys.executable).resolve().parents[2]
            # Ref: #220/#233 — W_OK alone is insufficient under macOS TCC;
            # probe an actual rename, and treat ANY denial (probe or atomic
            # bundle replace) as a permission error instead of silently
            # relocating the app to /Applications. In-place self-replace
            # requires the App Management grant; without it the localized
            # guidance tells the user what to do.
            tcc_allows = (
                os.access(original_app.parent, os.W_OK)
                and self._macos_dir_allows_install(original_app.parent)
            )
            if not tcc_allows or not self._macos_try_in_place_replace(original_app):
                logger.info(
                    "In-place update of %s denied by macOS permissions; "
                    "not relocating the app",
                    original_app,
                )
                raise UpdateError("update_install_permission_denied")
            self._macos_installed_app = original_app

    def _macos_try_in_place_replace(self, original_app: Path) -> bool:
        """Atomically swap the updated bundle into the app's current home.

        Ref: #220 — every bundle operation starts as an atomic os.rename so
        a TCC denial leaves NO half-copied .old and NO moved-away original.
        Returns False when the environment denies the replacement; raises a
        clean UpdateError only after restoring the original placement if the
        new-bundle placement fails.
        """
        import shutil

        old_app = Path(str(original_app) + ".old")
        try:
            if old_app.exists():
                shutil.rmtree(old_app)
            os.rename(original_app, old_app)
        except OSError as e:
            logger.info("Bundle replace denied for %s: %s", original_app, e)
            return False

        try:
            shutil.move(str(self._macos_temp_app), str(original_app))
        except OSError as e:
            # Roll back so the running app keeps a valid home, then surface
            # a clean error instead of a raw errno.
            try:
                os.rename(old_app, original_app)
            except OSError:
                logger.exception("Rollback of %s failed", original_app)
            raise UpdateError(f"Failed to place updated app at {original_app}") from e
        return True

    def _macos_verify(self) -> None:
        """Verify the swapped .app bundle is valid."""
        target = self._macos_installed_app
        if target is None or not target.exists():
            raise UpdateError("Install verification failed: .app not found after copy")
        # Check for a valid bundle marker
        info_plist = target / "Contents" / "Info.plist"
        if not info_plist.exists():
            raise UpdateError(
                "Install verification failed: .app bundle appears corrupt (no Info.plist)"
            )

    @staticmethod
    def _flush_logs() -> None:
        """Flush all log handlers so records survive os._exit."""
        import logging

        for h in logging.getLogger().handlers:
            try:
                h.flush()
            except Exception:
                pass

    def _log_running_app_processes(self, phase: str) -> None:
        """Log every running instance of the app bundle (pid + start time).

        Ref: #221 reopened — field logs previously proved the launch
        happened but never that the OLD process terminated. A pgrep-based
        census at each restart phase gives the runtime evidence needed to
        confirm (or refute) single-instance semantics without a debugger.
        Best-effort: any failure here must never block the restart.
        """
        import subprocess

        app_name = None
        if self._macos_installed_app is not None:
            app_name = self._macos_installed_app.name
        pattern = app_name if app_name else "simple-edge-tts"
        result = subprocess.run(
            ["pgrep", "-fl", pattern],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = [line for line in result.stdout.strip().splitlines() if line]
        logger.info(
            "[restart pid=%s] process census (%s): %d instance(s)%s",
            os.getpid(),
            phase,
            len(lines),
            " -> " + "; ".join(lines) if lines else "",
        )

    def _macos_restart(self) -> None:
        """Launch new .app version and exit.

        Ref: #221 — every step logs pid + timestamp (forensics for the
        "old process survives" report), and handlers are flushed BEFORE
        the unconditional hard exit.
        """
        import subprocess

        logger.info(
            "[restart pid=%s] removing quarantine from %s",
            os.getpid(), self._macos_installed_app,
        )
        # Ref: #198 — Remove quarantine from installed app before launch
        # so Gatekeeper does not block the auto-updated bundle.
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(self._macos_installed_app)],
                timeout=5,
            )
        except Exception:
            pass  # Best-effort; quarantine may not exist

        logger.info("[restart pid=%s] launching new app via open -n", os.getpid())
        # Ref: #221 reopened — record the running-instance census BEFORE
        # launch so the field log carries process-count evidence: the
        # expected post-restart state is exactly one app instance (the
        # newly launched one) and this pid gone.
        try:
            self._log_running_app_processes("before-launch")
        except Exception:
            logger.exception(
                "[restart pid=%s] process census failed (non-fatal)", os.getpid()
            )
        subprocess.Popen(
            ["open", "-n", str(self._macos_installed_app)],
            start_new_session=True,
        )
        # Ref: #221 — nothing after the launch may prevent the hard exit.
        # Cleanup and logging failures are swallowed: the old process MUST
        # terminate now that the new one is launched.
        try:
            self._install_cleanup()
            logger.info(
                "[restart pid=%s] cleanup done, exiting old process now", os.getpid()
            )
        except Exception:
            logger.exception("[restart pid=%s] post-launch cleanup failed", os.getpid())
        finally:
            try:
                self._flush_logs()
            except Exception:
                pass
            os._exit(0)

    # ---- Windows -------------------------------------------------------

    def _windows_copy(self) -> None:
        """Windows: extract .zip → find .exe."""
        import shutil
        import tempfile as tmp

        downloaded = self._downloaded_path
        if downloaded is None or not downloaded.exists():
            raise UpdateError("Downloaded .zip not found")

        extract_dir = Path(tmp.gettempdir()) / "simple-edge-tts-update" / "extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(str(downloaded), str(extract_dir))

        exes = list(extract_dir.glob("*.exe"))
        if not exes:
            raise UpdateError("No .exe found in downloaded archive")
        self._windows_new_exe = exes[0]

    def _windows_verify(self) -> None:
        """Verify the extracted .exe exists and is non-empty."""
        new_exe = self._windows_new_exe
        if new_exe is None or not new_exe.is_file():
            raise UpdateError("Install verification failed: .exe not found")
        if new_exe.stat().st_size == 0:
            raise UpdateError("Install verification failed: .exe is empty")

    def _windows_restart(self) -> None:
        """Write .bat → launch with CREATE_NO_WINDOW → exit.

        Ref: #202 — scrub _MEIPASS from the child environment. PyInstaller
        one-file mode exports _MEIPASS; if the .bat inherits it, the NEW
        exe resolves bundled resources against the OLD (soon-deleted)
        temp dir and crashes on startup.
        Ref: #236 — the relaunch is gated: copy /Y failure aborts, and
        the installed target is byte-compared (fc /b) against the
        downloaded exe BEFORE start. A failed or unchanged replacement
        writes an update-failure marker and exits non-zero instead of
        silently relaunching the old binary.
        """
        import subprocess as sp
        import tempfile as tmp

        old_exe = sys.executable
        new_exe = self._windows_new_exe

        # Clean env for the cmd.exe that runs the bat (and everything it starts).
        restart_env = os.environ.copy()
        restart_env.pop("_MEIPASS", None)
        restart_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"

        bat_path = Path(tmp.gettempdir()) / "simple-edge-tts-update" / "install.bat"
        fail_marker = Path(tmp.gettempdir()) / "simple-edge-tts-update" / "update-failed.flag"
        bat_content = (
            f'@echo off\r\n'
            f'timeout /t 2 /nobreak >nul\r\n'
            f'copy /Y "{new_exe}" "{old_exe}"\r\n'
            f'if errorlevel 1 (\r\n'
            f'  echo update replace failed > "{fail_marker}"\r\n'
            f'  exit /b 1\r\n'
            f')\r\n'
            f'fc /b "{old_exe}" "{new_exe}" >nul\r\n'
            f'if errorlevel 1 (\r\n'
            f'  echo update verify failed > "{fail_marker}"\r\n'
            f'  exit /b 1\r\n'
            f')\r\n'
            f'set _MEIPASS=\r\n'
            f'set PYINSTALLER_RESET_ENVIRONMENT=1\r\n'
            f'start "" "{old_exe}"\r\n'
            f'del "%~f0"\r\n'
        )
        bat_path.write_text(bat_content)

        sp.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=sp.CREATE_NO_WINDOW,
            env=restart_env,
        )
        self._install_cleanup()
        sys.exit(0)

    # ---- Shared cleanup -----------------------------------------------

    def _install_cleanup(self) -> None:
        """Remove downloaded temp files after successful install."""
        try:
            if self._downloaded_path and self._downloaded_path.exists():
                self._downloaded_path.unlink(missing_ok=True)
        except Exception:
            logger.debug("Failed to clean up downloaded file", exc_info=True)
