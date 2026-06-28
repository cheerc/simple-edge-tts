"""PyWebView JS API bridge — exposes Python backend to React frontend.

The Api class is passed to webview.create_window(js_api=api). All public
methods become callable from JavaScript via window.pywebview.api.<method>().

PyWebView serializes return values as strings, so all methods return
JSON-encoded strings for structured data. The React frontend (T18) will
call these methods and parse the JSON responses.

Ref: T16 — PyWebView entry point + IPC bridge
Ref: T28 — Use persistent event loop via run_async()
"""

import base64
import json
import logging
import mimetypes
import tempfile
import tempfile as _tempfile_module  # aliased for _is_path_within_allowed_dirs
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
from xml.sax.saxutils import escape as _xml_escape

from src.tts_engine import TTSEngine, format_rate, format_pitch, make_output_filename, run_async

if TYPE_CHECKING:
    from src.audio_player import AudioPlayer
    from src.config_manager import ConfigManager
    from src.i18n import I18n

import functools

logger = logging.getLogger(__name__)

# Ref: #116 — File size limit for get_audio_url() to prevent blocking
# pywebview's IPC bridge thread on unexpectedly large files.
# Preview files are typically <500KB; 5MB provides generous headroom.
MAX_AUDIO_URL_BYTES = 5 * 1024 * 1024  # 5MB


def log_api_call(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        formatted_args = []
        for arg in args:
            if isinstance(arg, str) and len(arg) > 100:
                formatted_args.append(repr(arg[:100] + "..."))
            else:
                formatted_args.append(repr(arg))
        
        formatted_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, str) and len(v) > 100:
                formatted_kwargs[k] = v[:100] + "..."
            else:
                formatted_kwargs[k] = v
        
        arg_str = ", ".join(formatted_args)
        kwarg_str = ", ".join(f"{k}={v!r}" for k, v in formatted_kwargs.items())
        params = ", ".join(filter(None, [arg_str, kwarg_str]))
        
        logger.info("API Call: %s(%s)", func.__name__, params)
        try:
            result = func(self, *args, **kwargs)
            if isinstance(result, str):
                preview = result[:200] + "..." if len(result) > 200 else result
                logger.debug("API Return: %s -> %s", func.__name__, preview)
            else:
                logger.debug("API Return: %s -> %r", func.__name__, result)
            return result
        except Exception as e:
            logger.error("API Error in %s: %s", func.__name__, e, exc_info=True)
            raise
    return wrapper


class Api:
    """PyWebView JS API class — exposed to frontend via window.pywebview.api.

    All public methods are callable from JavaScript. Return values are
    JSON-encoded strings for structured data exchange.
    """

    def __init__(
        self,
        tts_engine: "TTSEngine",
        config: "ConfigManager",
        audio_player: "AudioPlayer",
        i18n: "I18n",
    ) -> None:
        self._engine = tts_engine
        self._config = config
        self._audio_player = audio_player
        self._i18n = i18n
        self._window: Optional[Any] = None
        # Ref: #123 — Track preview tempfiles for cleanup before os._exit(0)
        # bypasses Python finalization. Protected by lock for concurrent
        # pywebview worker threads (reviewer finding F2).
        self._preview_tempfiles: list[Path] = []
        self._preview_tempfiles_lock = threading.Lock()

    @log_api_call
    def get_voices(self) -> str:
        """Return JSON-encoded voice list from edge-tts.

        Returns:
            JSON array of voice objects with ShortName, Locale, Gender, etc.
        """
        try:
            voices = self._engine.get_voices_sync()
            return json.dumps(voices, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to get voices: %s", e)
            return json.dumps({"error": str(e)})

    @log_api_call
    def generate_tts(self, text: str, voice: str, rate: int, pitch: int) -> str:
        """Generate TTS audio file, return file path or error.

        Args:
            text: Text to synthesize.
            voice: Voice short name (e.g. 'en-US-JennyNeural').
            rate: Speech rate adjustment (-100 to 100).
            pitch: Pitch adjustment in Hz (-100 to 100).

        Returns:
            JSON with 'path' on success or 'error' on failure.
        """
        if not text or not text.strip():
            return json.dumps({"error": "Text cannot be empty"})

        try:
            output_dir = self._get_effective_output_dir()

            output_path = Path(output_dir) / make_output_filename(text)
            rate_str = format_rate(rate)
            pitch_str = format_pitch(pitch)

            sanitized_text = self._sanitize_tts_text(text)

            run_async(
                self._engine.generate(
                    text=sanitized_text,
                    voice=voice,
                    output_path=str(output_path),
                    rate=rate_str,
                    pitch=pitch_str,
                )
            )

            return json.dumps(
                {"path": str(output_path)},
                ensure_ascii=False,
            )
        except Exception as e:
            logger.error("TTS generation failed: %s", e)
            return json.dumps({"error": str(e)})

    @log_api_call
    def preview_tts(self, text: str, voice: str, rate: int, pitch: int) -> str:
        """Generate TTS audio to a temp file for preview playback.

        Unlike generate_tts(), this does NOT save to the user's output
        directory. The temp file is suitable for immediate playback and
        can be cleaned up after use.

        Ref: #52 — Preview should not save files to Desktop.

        Args:
            text: Text to synthesize.
            voice: Voice short name (e.g. 'en-US-JennyNeural').
            rate: Speech rate adjustment (-100 to 100).
            pitch: Pitch adjustment in Hz (-100 to 100).

        Returns:
            JSON with 'path' (temp file) on success or 'error' on failure.
        """
        if not text or not text.strip():
            return json.dumps({"error": "Text cannot be empty"})

        try:
            # Create a temp file that persists until explicitly deleted
            tmp = tempfile.NamedTemporaryFile(
                suffix=".mp3", prefix="set_preview_", delete=False
            )
            tmp_path = tmp.name
            tmp.close()

            sanitized_text = self._sanitize_tts_text(text)

            rate_str = format_rate(rate)
            pitch_str = format_pitch(pitch)

            run_async(
                self._engine.generate(
                    text=sanitized_text,
                    voice=voice,
                    output_path=tmp_path,
                    rate=rate_str,
                    pitch=pitch_str,
                )
            )

            # Ref: #123 — Track tempfile for cleanup at shutdown.
            # os._exit(0) bypasses Python finalization, so we must
            # explicitly clean up before exit.
            with self._preview_tempfiles_lock:
                self._preview_tempfiles.append(Path(tmp_path))

            return json.dumps({"path": tmp_path}, ensure_ascii=False)
        except Exception as e:
            logger.error("TTS preview failed: %s", e)
            return json.dumps({"error": str(e)})

    @log_api_call
    def get_config(self, key: str) -> str:
        """Read a config value.

        Args:
            key: Configuration key to read.

        Returns:
            JSON with 'value' field containing the config value.
        """
        value = self._config.get(key)
        return json.dumps({"value": value}, ensure_ascii=False)

    @log_api_call
    def set_config(self, key: str, value: object) -> str:
        """Write a config value and persist to disk.

        Args:
            key: Configuration key to write.
            value: Value to set.

        Returns:
            JSON with 'success' boolean.
        """
        try:
            if key == "output_dir":
                if not isinstance(value, str):
                    return json.dumps({
                        "success": False,
                        "error": "output_dir must be a string",
                    })
                path = Path(value).resolve()
                # Reject relative paths
                if not Path(value).is_absolute():
                    return json.dumps({
                        "success": False,
                        "error": "output_dir must be an absolute path",
                    })
                # Reject path traversal — resolved path must be under HOME
                home = Path.home().resolve()
                if not path.is_relative_to(home):
                    return json.dumps({
                        "success": False,
                        "error": "output_dir must be within your home directory",
                    })
                # Must exist as a directory
                if not path.is_dir():
                    return json.dumps({
                        "success": False,
                        "error": f"Directory does not exist: {value}",
                    })

            self._config.set(key, value)
            self._config.save()
            # When language changes, update the I18n instance so
            # get_translations() returns the new language immediately
            if key == "language" and isinstance(value, str):
                self._i18n.set_language(value)
            return json.dumps({"success": True})
        except Exception as e:
            logger.error("Failed to set config %s: %s", key, e)
            return json.dumps({"success": False, "error": str(e)})

    @log_api_call
    def get_translations(self) -> str:
        """Return i18n strings for the current language.

        Returns:
            JSON with 'language' and 'strings' fields.
        """
        return json.dumps(
            {
                "language": self._i18n.current_language,
                "strings": self._i18n._strings,
            },
            ensure_ascii=False,
        )

    @log_api_call
    def play_audio(self, file_path: str) -> str:
        """Play an audio file via the AudioPlayer bridge.

        Args:
            file_path: Absolute path to the audio file.

        Returns:
            JSON with 'success' boolean.
        """
        try:
            self._audio_player.play(file_path)
            return json.dumps({"success": True})
        except Exception as e:
            logger.error("Playback failed: %s", e)
            return json.dumps({"success": False, "error": str(e)})

    @log_api_call
    def stop_audio(self) -> str:
        """Stop current audio playback.

        Returns:
            JSON with 'success' boolean.
        """
        try:
            self._audio_player.stop()
            return json.dumps({"success": True})
        except Exception as e:
            logger.error("Stop playback failed: %s", e)
            return json.dumps({"success": False, "error": str(e)})

    @log_api_call
    def get_audio_url(self, file_path: str) -> str:
        """Convert a local file path to a playable data URL.

        WebKit blocks file:// media from HTTP origins (pywebview serves
        pages via localhost HTTP server). Base64 data URLs bypass this
        restriction. TTS preview files are typically <500KB so overhead
        is acceptable.

        Only files within the configured output directory or the
        system temporary directory are accessible — arbitrary file
        paths are rejected (Issue #111).

        Ref: #63 — audio bridge needs URL resolution for HTMLAudioElement.

        Args:
            file_path: Absolute path to the audio file.

        Returns:
            A data:audio/...;base64,... URL string, or empty string if
            file does not exist or is outside allowed directories.
        """
        path = Path(file_path).resolve()
        if not self._is_path_within_allowed_dirs(path):
            return ""
        if not path.exists():
            return ""
        # Ref: #116 — Reject files larger than MAX_AUDIO_URL_BYTES to
        # prevent blocking pywebview's IPC bridge thread on large reads.
        # Wrap stat() in try-except OSError — file may disappear between
        # exists() and stat() (reviewer finding F1).
        try:
            if path.stat().st_size > MAX_AUDIO_URL_BYTES:
                logger.warning(
                    "get_audio_url: file %s exceeds size limit (%d > %d)",
                    path, path.stat().st_size, MAX_AUDIO_URL_BYTES,
                )
                return ""
        except OSError:
            logger.warning("get_audio_url: stat() failed for %s", path, exc_info=True)
            return ""
        mime_type = mimetypes.guess_type(str(path))[0] or "audio/mpeg"
        data = path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime_type};base64,{b64}"

    @log_api_call
    def notify_playback_finished(self) -> None:
        """Called from JS bridge when audio playback ends.

        The JS bridge (audio_player_bridge.js) calls this via
        window.pywebview.api.notify_playback_finished() when the
        HTMLAudioElement 'ended' or 'error' event fires.

        Delegates to AudioPlayer.notify_playback_finished() which
        resets state and dispatches 'audioPlaybackFinished' window
        event for React to reset the speaking button.

        Ref: #63, #74 — playback completion chain.
        """
        self._audio_player.notify_playback_finished()

    @log_api_call
    def check_update(self) -> str:
        """Check GitHub for a newer release.

        Non-blocking from the frontend's perspective (called once on mount).
        Fails silently on network error.

        Returns:
            JSON with {'latest': str, 'url': str} if update available,
            or JSON null if up-to-date / offline / error.
        """
        try:
            from importlib.metadata import version as pkg_version

            from src.update_checker import UpdateChecker

            current = pkg_version("simple-edge-tts")
            skip = self._config.get("skip_version")
            checker = UpdateChecker(current, skip_version=skip)
            result = checker.check()
            return json.dumps(result)
        except Exception as e:
            logger.debug("check_update failed: %s", e)
            return json.dumps(None)

    @log_api_call
    def set_window(self, window: object) -> None:
        """Set the pywebview window reference for native file dialogs."""
        self._window = window

    def cleanup_preview_files(self) -> None:
        """Delete all tracked preview tempfiles and clear the tracking list.

        Idempotent — safe to call multiple times.  Tolerates files that
        have already been deleted (e.g. by an external process).

        Ref: #123 — os._exit(0) bypasses Python finalization, so preview
        tempfiles must be explicitly cleaned up before exit.
        """
        with self._preview_tempfiles_lock:
            for path in self._preview_tempfiles:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    logger.debug(
                        "cleanup_preview_files: could not delete %s",
                        path, exc_info=True,
                    )
            self._preview_tempfiles.clear()

    def _get_effective_output_dir(self) -> str:
        """Return the effective output directory, falling back to Desktop."""
        output_dir = self._config.get("output_dir")
        if output_dir is None:
            output_dir = str(Path.home() / "Desktop")
        return output_dir

    def _is_path_within_allowed_dirs(self, path: Path) -> bool:
        """Check that a resolved path is within an allowed directory.

        Allowed directories: the user's configured output_dir and
        the system temporary directory (used by preview_tts()).

        Returns:
            True if the path is inside an allowed directory.
        """
        allowed = [
            Path(self._get_effective_output_dir()).resolve(),
            Path(_tempfile_module.gettempdir()).resolve(),
        ]
        resolved = path.resolve()
        return any(
            resolved == allowed_dir or resolved.is_relative_to(allowed_dir)
            for allowed_dir in allowed
        )

    @staticmethod
    def _sanitize_tts_text(text: str) -> str:
        """Escape XML/SSML special characters in TTS input text.

        Prevents unintended SSML tag interpretation by the Azure
        TTS backend (Issue #120). The escaped entities are spoken
        as literal characters by the TTS engine.

        Escaped characters: < → &lt;, > → &gt;, & → &amp;
        """
        return _xml_escape(text)

    @log_api_call
    def get_output_dir(self) -> str:
        """Return the current output directory path.

        Returns:
            JSON with 'output_dir' field.
        """
        output_dir = self._get_effective_output_dir()
        return json.dumps({"output_dir": output_dir}, ensure_ascii=False)

    @log_api_call
    def select_output_dir(self) -> str:
        """Open a native folder picker dialog and persist the selection.

        Uses PyWebView's create_file_dialog(FOLDER_DIALOG) for a native
        OS folder selection experience.

        Returns:
            JSON with 'output_dir' (selected or current on cancel),
            or 'error' if window not available.
        """
        if self._window is None:
            return json.dumps({"error": "Window not available"})

        try:
            import webview

            result = self._window.create_file_dialog(
                webview.FileDialog.FOLDER  # type: ignore[arg-type]
            )

            if result and len(result) > 0:
                selected = result[0]
                self._config.set("output_dir", selected)
                self._config.save()
                return json.dumps({"output_dir": selected}, ensure_ascii=False)

            # User cancelled — return current dir
            return self.get_output_dir()
        except Exception as e:
            logger.error("Folder selection failed: %s", e)
            return json.dumps({"error": str(e)})

