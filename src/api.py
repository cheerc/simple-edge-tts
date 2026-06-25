"""PyWebView JS API bridge — exposes Python backend to React frontend.

The Api class is passed to webview.create_window(js_api=api). All public
methods become callable from JavaScript via window.pywebview.api.<method>().

PyWebView serializes return values as strings, so all methods return
JSON-encoded strings for structured data. The React frontend (T18) will
call these methods and parse the JSON responses.

Ref: T16 — PyWebView entry point + IPC bridge
Ref: T28 — Use persistent event loop via run_async()
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.tts_engine import TTSEngine, format_rate, format_pitch, make_output_filename, run_async

if TYPE_CHECKING:
    from src.audio_player import AudioPlayer
    from src.config_manager import ConfigManager
    from src.i18n import I18n

logger = logging.getLogger(__name__)


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
        self._window: Optional[object] = None

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
            output_dir = self._config.get("output_dir")
            if output_dir is None:
                output_dir = str(Path.home() / "Desktop")

            output_path = Path(output_dir) / make_output_filename(text)
            rate_str = format_rate(rate)
            pitch_str = format_pitch(pitch)

            run_async(
                self._engine.generate(
                    text=text,
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

            rate_str = format_rate(rate)
            pitch_str = format_pitch(pitch)

            run_async(
                self._engine.generate(
                    text=text,
                    voice=voice,
                    output_path=tmp_path,
                    rate=rate_str,
                    pitch=pitch_str,
                )
            )

            return json.dumps({"path": tmp_path}, ensure_ascii=False)
        except Exception as e:
            logger.error("TTS preview failed: %s", e)
            return json.dumps({"error": str(e)})

    def get_config(self, key: str) -> str:
        """Read a config value.

        Args:
            key: Configuration key to read.

        Returns:
            JSON with 'value' field containing the config value.
        """
        value = self._config.get(key)
        return json.dumps({"value": value}, ensure_ascii=False)

    def set_config(self, key: str, value: object) -> str:
        """Write a config value and persist to disk.

        Args:
            key: Configuration key to write.
            value: Value to set.

        Returns:
            JSON with 'success' boolean.
        """
        try:
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

    def set_window(self, window: object) -> None:
        """Set the pywebview window reference for native file dialogs."""
        self._window = window

    def get_output_dir(self) -> str:
        """Return the current output directory path.

        Returns:
            JSON with 'output_dir' field.
        """
        output_dir = self._config.get("output_dir")
        if output_dir is None:
            output_dir = str(Path.home() / "Desktop")
        return json.dumps({"output_dir": output_dir}, ensure_ascii=False)

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

