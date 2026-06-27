# Security Hardening — Wave 2 (Issues #111, #120, #121)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `impl-task-loop` skill to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three security vulnerabilities in the pywebview IPC bridge (`src/api.py`) — path traversal in audio URL generation, SSML injection in TTS text, and missing output directory validation.

**Architecture:** Add defense-in-depth validation at the API boundary (`src/api.py`) before data reaches the filesystem or external TTS service. All three fixes are localized to the `Api` class methods and share a common validation helper for path safety.

**Tech Stack:** Python 3.11+, pytest, unittest.mock

## Global Constraints

- All changes are in `src/api.py` only (plus `src/config_manager.py` for #121 reusable validation)
- Must not break existing `pywebview.api.*` JS bridge contract (return types and JSON structure unchanged)
- Error cases return JSON `{"error": "..."}` or empty string for `get_audio_url()` (existing contract)
- Existing tests in `tests/test_api.py` must continue to pass
- New tests must follow existing mock-based patterns (MagicMock, AsyncMock, pytest fixtures)

## Risk-Flags Hit (PROJECT.md §12)

- **pywebview ↔ Python IPC bridge** (`@js_api` / `window.pywebview.api`) — all three issues
- **Path traversal** — #111

→ Review contract: **D3** (full-tree + runtime evidence), lenses: `correctness` + `security`
→ **second_reviewer required** (security lens + complex+ per lead-dispatching Phase 3 risk trigger)

---

### Task 1: Fix path traversal in `get_audio_url()` (Closes #111)

**Files:**
- Modify: `src/api.py:293-299` (add `_is_path_within_allowed_dirs` helper + guard in `get_audio_url`)
- Test: `tests/test_api.py` (new `TestGetAudioUrl` class)

**Interfaces:**
- Consumes: `self._config.get("output_dir")` via `_get_effective_output_dir()`, `tempfile.gettempdir()`
- Produces: `_is_path_within_allowed_dirs(path: Path) -> bool` (new private helper)
- External: `window.pywebview.api.get_audio_url(file_path)` — return type unchanged (`str`: data URL or empty string)

- [ ] **Step 1: Write failing tests for `get_audio_url()`**

```python
import tempfile
from pathlib import Path
from unittest.mock import patch


class TestGetAudioUrl:
    """Test get_audio_url() — path traversal protection (Issue #111)."""

    def test_returns_data_url_for_valid_audio(self, api, mock_config, tmp_path):
        """get_audio_url() returns base64 data URL for audio in allowed dir."""
        mock_config.get.return_value = str(tmp_path)
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"\xff\xfb\x90\x00")  # valid MP3 header

        result = api.get_audio_url(str(audio))

        assert result.startswith("data:audio/mpeg;base64,")

    def test_blocks_path_outside_allowed_dirs(self, api, mock_config):
        """get_audio_url() returns empty string for paths outside allowed dirs."""
        mock_config.get.return_value = "/tmp/allowed"

        # Try to read /etc/passwd (or /etc/hosts on macOS)
        result = api.get_audio_url("/etc/hosts")

        assert result == ""

    def test_blocks_absolute_path_traversal(self, api, mock_config, tmp_path):
        """get_audio_url() rejects paths with .. traversal escaping allowed dir."""
        mock_config.get.return_value = str(tmp_path)
        # Create a file inside allowed dir
        allowed_file = tmp_path / "safe.mp3"
        allowed_file.write_bytes(b"\xff\xfb\x90\x00")

        # Try to escape via .. traversal
        traversal = str(tmp_path / ".." / "etc" / "hosts")

        result = api.get_audio_url(traversal)

        assert result == ""

    def test_returns_empty_for_nonexistent_file(self, api, mock_config, tmp_path):
        """get_audio_url() returns empty string when file does not exist."""
        mock_config.get.return_value = str(tmp_path)

        result = api.get_audio_url(str(tmp_path / "nonexistent.mp3"))

        assert result == ""

    def test_allows_path_in_temp_dir(self, api, mock_config, tmp_path):
        """get_audio_url() allows paths in system temp directory."""
        mock_config.get.return_value = "/some/other/dir"
        # Use actual tempfile.gettempdir() — create file there
        import tempfile
        tmpdir = Path(tempfile.gettempdir())
        test_file = tmpdir / "simple_edge_tts_test_audio.mp3"
        test_file.write_bytes(b"\xff\xfb\x90\x00")
        try:
            result = api.get_audio_url(str(test_file))
            assert result.startswith("data:audio/mpeg;base64,")
        finally:
            test_file.unlink(missing_ok=True)
```

    def test_returns_empty_for_empty_path(self, api):
        """get_audio_url() returns empty string for empty file_path."""
        result = api.get_audio_url("")
        assert result == ""

    def test_blocks_symlink_pointing_outside(self, api, mock_config, tmp_path):
        """get_audio_url() rejects symlinks that resolve outside allowed dirs."""
        mock_config.get.return_value = str(tmp_path)
        # Create a valid file inside allowed dir
        real_file = tmp_path / "real.mp3"
        real_file.write_bytes(b"\xff\xfb\x90\x00")
        # Create a symlink inside allowed dir pointing to /etc/hosts
        symlink = tmp_path / "evil_link"
        symlink.symlink_to("/etc/hosts")
        try:
            result = api.get_audio_url(str(symlink))
            assert result == ""
        finally:
            symlink.unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && uv run pytest tests/test_api.py::TestGetAudioUrl -v`
Expected: tests FAIL — `test_blocks_path_outside_allowed_dirs`, `test_blocks_absolute_path_traversal`, and `test_blocks_symlink_pointing_outside` should return data URLs (no guard yet). `test_returns_empty_for_empty_path` and `test_returns_empty_for_nonexistent_file` may pass (existing behavior).

- [ ] **Step 3: Implement `_is_path_within_allowed_dirs()` helper + guard in `get_audio_url()`**

Add the helper method to the `Api` class (near `_get_effective_output_dir()` at line ~347):

```python
import tempfile as _tempfile_module  # add at top of file with other imports

# In Api class, after _get_effective_output_dir():

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
        str(resolved).startswith(str(allowed_dir) + "/")
        or str(resolved) == str(allowed_dir)
        for allowed_dir in allowed
    )
```

Modify `get_audio_url()` to add the guard before reading:

```python
@log_api_call
def get_audio_url(self, file_path: str) -> str:
    """Return a base64 data URL for a local audio file.

    Only files within the configured output directory or the
    system temporary directory are accessible — arbitrary file
    paths are rejected (Issue #111).

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
    mime_type = mimetypes.guess_type(str(path))[0] or "audio/mpeg"
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{b64}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/test_api.py::TestGetAudioUrl -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `cd <worktree> && uv run pytest tests/ -v`
Expected: all existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "fix: add path traversal guard to get_audio_url() (Closes #111)

Add _is_path_within_allowed_dirs() helper that restricts file access
to the configured output_dir and system temp directory. Reject paths
escaping via .. traversal.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Escape SSML/XML in TTS text input (Closes #120)

**Files:**
- Modify: `src/api.py:105,131-136` (escape text in `generate_tts()`), `src/api.py` preview_tts method
- Test: `tests/test_api.py` (add to existing `TestGenerateTts` and preview test classes)

**Interfaces:**
- Consumes: `xml.sax.saxutils.escape()` (stdlib)
- Produces: sanitized text passed to `self._engine.generate(text=...)`
- External: `window.pywebview.api.generate_tts(text, voice, rate, pitch)` — behavior change: `<` `>` `&` in text are now escaped

- [ ] **Step 1: Write failing tests for SSML escaping**

Add to `tests/test_api.py`:

```python
class TestSSMLSanitization:
    """Test SSML/XML escaping in TTS text input (Issue #120)."""

    def test_generate_tts_escapes_xml_tags(self, api, mock_tts_engine):
        """generate_tts() escapes < and > in text before passing to engine."""
        api.generate_tts("<speak>Hello</speak>", "en-US-JennyNeural", 0, 0)

        call_args = mock_tts_engine.generate.call_args
        assert call_args is not None
        text_passed = call_args.kwargs.get("text") or call_args.args[0]
        assert "<" not in text_passed
        assert ">" not in text_passed
        assert "&lt;" in text_passed

    def test_generate_tts_escapes_ampersand(self, api, mock_tts_engine):
        """generate_tts() escapes & in text."""
        api.generate_tts("Rock & Roll", "en-US-JennyNeural", 0, 0)

        call_args = mock_tts_engine.generate.call_args
        text_passed = call_args.kwargs.get("text") or call_args.args[0]
        assert "&amp;" in text_passed
        assert "& " not in text_passed  # raw & not followed by amp;

    def test_generate_tts_preserves_normal_text(self, api, mock_tts_engine):
        """generate_tts() does not modify text without XML special chars."""
        api.generate_tts("Hello world", "en-US-JennyNeural", 0, 0)

        call_args = mock_tts_engine.generate.call_args
        text_passed = call_args.kwargs.get("text") or call_args.args[0]
        assert text_passed == "Hello world"


class TestSSMLSanitizationPreview:
    """Test SSML/XML escaping in preview_tts() (Issue #120)."""

    def test_preview_tts_escapes_xml_tags(self, api, mock_tts_engine):
        """preview_tts() escapes < and > in text."""
        # Need to patch tempfile to avoid actual temp dir usage
        import tempfile
        with patch.object(tempfile, 'NamedTemporaryFile'):
            try:
                api.preview_tts("<voice>Test</voice>", "en-US-JennyNeural", 0, 0)
            except Exception:
                pass  # may fail due to mocked tempfile, but call should have happened

            call_args = mock_tts_engine.generate.call_args
            if call_args:
                text_passed = call_args.kwargs.get("text") or call_args.args[0]
                assert "<" not in text_passed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && uv run pytest tests/test_api.py::TestSSMLSanitization -v`
Expected: `test_generate_tts_escapes_xml_tags` FAILS — `<speak>` passed raw to engine

- [ ] **Step 3: Implement SSML escaping**

Add import at top of `src/api.py`:

```python
from xml.sax.saxutils import escape as _xml_escape
```

Add a private helper in the `Api` class:

```python
@staticmethod
def _sanitize_tts_text(text: str) -> str:
    """Escape XML/SSML special characters in TTS input text.

    Prevents unintended SSML tag interpretation by the Azure
    TTS backend (Issue #120). The escaped entities are spoken
    as literal characters by the TTS engine.

    Escaped characters: < → &lt;, > → &gt;, & → &amp;
    """
    return _xml_escape(text)
```

Apply escaping in `generate_tts()`:

```python
# After text validation, before engine.generate() call:
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
```

Also apply in `preview_tts()` (find the similar `self._engine.generate()` call and wrap `text` with `self._sanitize_tts_text(text)`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/test_api.py::TestSSMLSanitization tests/test_api.py::TestSSMLSanitizationPreview -v`
Expected: all tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd <worktree> && uv run pytest tests/ -v`
Expected: all tests PASS (existing tests should not be affected — mock-based tests don't check exact text values)

- [ ] **Step 6: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "fix: escape SSML/XML special chars in TTS text input (Closes #120)

Add _sanitize_tts_text() helper using xml.sax.saxutils.escape()
to prevent unintended SSML tag interpretation by Azure TTS backend.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Validate output_dir in set_config() (Closes #121)

**Files:**
- Modify: `src/api.py:207-227` (add validation in `set_config()`)
- Modify: `src/config_manager.py:45-46` (optional — add reusable `validate_path()` static method)
- Test: `tests/test_api.py` (add to existing `TestConfig` class + new `TestOutputDirValidation`)

**Interfaces:**
- Consumes: `pathlib.Path`, `os.path.isabs()`
- Produces: validated `output_dir` stored via `ConfigManager.set()`
- External: `window.pywebview.api.set_config(key, value)` — return type unchanged; invalid `output_dir` returns `{"success": false, "error": "..."}`

- [ ] **Step 1: Write failing tests for output_dir validation**

Add to `tests/test_api.py`:

```python
class TestOutputDirValidation:
    """Test output_dir path validation in set_config() (Issue #121)."""

    def test_set_config_rejects_relative_output_dir(self, api, mock_config):
        """set_config() rejects relative paths for output_dir."""
        result = api.set_config("output_dir", "relative/path")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "error" in parsed
        # Config must NOT be saved with invalid value
        mock_config.set.assert_not_called()

    def test_set_config_rejects_path_traversal_output_dir(self, api, mock_config):
        """set_config() rejects output_dir containing .. traversal."""
        result = api.set_config("output_dir", "/Users/cheerc/../../etc")
        parsed = json.loads(result)
        assert parsed["success"] is False

    def test_set_config_accepts_valid_absolute_path(self, api, mock_config):
        """set_config() accepts a valid absolute path for output_dir."""
        result = api.set_config("output_dir", "/Users/cheerc/Desktop")
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_config.set.assert_called_with("output_dir", "/Users/cheerc/Desktop")
        mock_config.save.assert_called_once()

    def test_set_config_accepts_other_keys_unchanged(self, api, mock_config):
        """set_config() does not validate non-output_dir keys."""
        result = api.set_config("language", "ja-JP")
        parsed = json.loads(result)
        assert parsed["success"] is True
        mock_config.set.assert_called_with("language", "ja-JP")

    def test_set_config_rejects_nonexistent_directory(self, api, mock_config):
        """set_config() rejects output_dir that does not exist on disk."""
        result = api.set_config("output_dir", "/nonexistent/path/xyz")
        parsed = json.loads(result)
        assert parsed["success"] is False

    def test_set_config_rejects_empty_output_dir(self, api, mock_config):
        """set_config() rejects empty string for output_dir."""
        result = api.set_config("output_dir", "")
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "error" in parsed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd <worktree> && uv run pytest tests/test_api.py::TestOutputDirValidation -v`
Expected: `test_set_config_rejects_relative_output_dir` and `test_set_config_rejects_path_traversal_output_dir` FAIL — any value accepted currently

- [ ] **Step 3: Implement output_dir validation**

Modify `set_config()` in `src/api.py`:

```python
@log_api_call
def set_config(self, key: str, value: object) -> str:
    """Write a config value and persist to disk.

    When key is 'output_dir', the value is validated:
    - Must be an absolute path
    - Must resolve to within the user's home directory
    - Must exist on disk as a directory

    Args:
        key: Configuration key to write.
        value: Value to set.

    Returns:
        JSON with 'success' boolean and optional 'error' string.
    """
    try:
        if key == "output_dir":
            if not isinstance(value, str):
                return json.dumps({
                    "success": False,
                    "error": "output_dir must be a string",
                })
            path = Path(value).resolve()
            # Reject relative paths (use Path.is_absolute(), Python 3.9+)
            if not Path(value).is_absolute():
                return json.dumps({
                    "success": False,
                    "error": "output_dir must be an absolute path",
                })
            # Reject path traversal — resolved path must be under HOME
            # Use is_relative_to() for robust boundary check (Python 3.9+)
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
        # When language changes, update the I18n instance
        if key == "language" and isinstance(value, str):
            self._i18n.set_language(value)
        return json.dumps({"success": True})
    except Exception as e:
        logger.error("Failed to set config %s: %s", key, e)
        return json.dumps({"success": False, "error": str(e)})
```

Add `import os` at the top of `src/api.py` if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd <worktree> && uv run pytest tests/test_api.py::TestOutputDirValidation tests/test_api.py::TestConfig -v`
Expected: all tests PASS

- [ ] **Step 5: Run full test suite**

Run: `cd <worktree> && uv run pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api.py tests/test_api.py
git commit -m "fix: validate output_dir path in set_config() (Closes #121)

Add path validation for output_dir config key: must be absolute,
within HOME, and exist as a directory. Rejects relative paths
and .. traversal to prevent file writes outside expected location.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Pre-Implementation Checklist

- [ ] `uv sync --all-extras` completes successfully
- [ ] `(cd frontend && npm ci)` completes successfully
- [ ] `uv run pytest tests/ -v` — all existing tests pass BEFORE changes
- [ ] Each task's tests verified FAIL before implementation
- [ ] Each task's tests verified PASS after implementation
- [ ] Full `uv run pytest tests/ -v` passes after all tasks

## Affected Tests

- `tests/test_api.py` — new test classes: `TestGetAudioUrl`, `TestSSMLSanitization`, `TestSSMLSanitizationPreview`, `TestOutputDirValidation`
- `tests/test_api.py` — existing classes NOT affected (mock-based, no behavioral regression expected): `TestGetVoices`, `TestGenerateTts`, `TestConfig`, `TestGetTranslations`

## Verification Checklist

After all tasks complete, verify manually:
1. Open the app (`./deploy.sh` build + run `.app`)
2. Generate TTS with text containing `<tag>` — audio should speak "tag" literally
3. Change output directory to a valid path — should work
4. Attempt to set output_dir to `../../etc` via config — should be rejected (UI may not expose this; verify via API)
5. Preview audio — should work normally (temp dir path allowed)
