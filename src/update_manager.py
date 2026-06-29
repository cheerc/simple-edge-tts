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
        shutdown_handler()

        # Step 5: switch to new version
        self._restart()

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
                raise UpdateError(
                    "Cannot write to /Applications — please move "
                    "the app to /Applications or check permissions"
                )
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
    def _install_dir_is_writable() -> bool:
        """Return True if the directory containing the executable is writable."""
        return os.access(os.path.dirname(sys.executable), os.W_OK)

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
        import ssl
        from urllib.request import Request, urlopen

        try:
            req = Request(
                GITHUB_API_RELEASES,
                headers={"User-Agent": f"simple-edge-tts/{self.current_version}"},
            )
            with urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
                release = json.loads(resp.read())
        except Exception as e:
            raise UpdateError(f"Failed to fetch release info: {e}") from e

        # Find the platform-appropriate asset
        is_macos = self._is_macos()
        for asset_data in release.get("assets", []):
            name = asset_data.get("name", "")
            if is_macos and name.endswith(".dmg"):
                return {
                    "release": release,
                    "name": name,
                    "browser_download_url": asset_data["browser_download_url"],
                }
            if not is_macos and name.endswith(".zip"):
                return {
                    "release": release,
                    "name": name,
                    "browser_download_url": asset_data["browser_download_url"],
                }

        platform_name = "macOS (.dmg)" if is_macos else "Windows (.zip)"
        raise UpdateError(f"No {platform_name} asset found in latest release")

    def _fetch_checksums(self, release: dict) -> dict[str, str]:
        """Download SHA256SUMS.txt from the release assets and parse it.

        Returns a dict mapping filename → sha256 hex digest.
        """
        import ssl
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
            with urlopen(req, timeout=10, context=ssl.create_default_context()) as resp:
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
        import ssl
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
            with urlopen(req, timeout=60, context=ssl.create_default_context()) as resp:
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
                        if on_progress and total_bytes:
                            pct = min(int(downloaded / total_bytes * 100), 100)
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
                ["ditto", str(apps[0]), str(temp_app)],
                check=True,
                timeout=60,
            )
        finally:
            subprocess.run(
                ["hdiutil", "detach", str(mount_point), "-quiet"],
                timeout=10,
            )

        # Atomic swap into /Applications
        target_app = Path("/Applications") / self._macos_app_name

        if not self._app_is_in_applications_dir():
            if target_app.exists():
                old = Path(str(target_app) + ".old")
                if old.exists():
                    shutil.rmtree(old)
                shutil.move(str(target_app), str(old))
            shutil.move(str(self._macos_temp_app), str(target_app))
        else:
            old_app = Path(str(target_app) + ".old")
            if old_app.exists():
                shutil.rmtree(old_app)
            shutil.move(str(target_app), str(old_app))
            shutil.move(str(self._macos_temp_app), str(target_app))

        self._macos_installed_app = target_app

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

    def _macos_restart(self) -> None:
        """Launch new .app version and exit."""
        import subprocess

        subprocess.Popen(
            ["open", "-n", str(self._macos_installed_app)],
            start_new_session=True,
        )
        self._install_cleanup()
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
        """Write .bat → launch with CREATE_NO_WINDOW → exit."""
        import subprocess as sp
        import tempfile as tmp

        old_exe = sys.executable
        new_exe = self._windows_new_exe

        bat_path = Path(tmp.gettempdir()) / "simple-edge-tts-update" / "install.bat"
        bat_content = (
            f'@echo off\r\n'
            f'timeout /t 2 /nobreak >nul\r\n'
            f'copy /Y "{new_exe}" "{old_exe}"\r\n'
            f'start "" "{old_exe}"\r\n'
            f'del "%~f0"\r\n'
        )
        bat_path.write_text(bat_content)

        sp.Popen(
            ["cmd", "/c", str(bat_path)],
            creationflags=sp.CREATE_NO_WINDOW,
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
