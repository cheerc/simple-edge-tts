---
required_reads:
  - src/api.py
  - src/main.py
  - src/logging_config.py
  - tests/test_api.py
  - tests/test_logging_config.py
---

# Wave 3: Performance + Architecture Fixes (#116, #117, #123)

## Summary

Three fixes addressing IPC bridge blocking, production diagnostic overhead, and shutdown tempfile cleanup.

## Issue #117 — Gate diagnostic_monitor behind dev mode (simple)

**Change**: Only start `start_diagnostic_monitor()` when `_is_dev_mode()` is true.

**Rationale**: The diagnostic monitor dumps full thread stack traces every 5 seconds. In production builds with file logging enabled, this fills the 1MB log rotation quickly. Development mode (`SIMPLE_EDGE_TTS_DEV` env var or missing `frontend/dist`) already gates DEBUG log level — the monitor should follow the same gate.

**Files**:
- `src/main.py:94`: Wrap `start_diagnostic_monitor(interval_seconds=5.0)` in `if _is_dev_mode():`
- `tests/test_logging_config.py`: Add test verifying monitor is NOT started in production mode (or verify existing tests still pass)

**Affected callers**: None — `start_diagnostic_monitor` is called only from `main()`. The monitor thread is a daemon thread, so skipping it has no side effects on shutdown.

**Related tests**: `tests/test_logging_config.py` (existing tests for `start_diagnostic_monitor`)

**Verification**:
1. `uv run pytest tests/test_logging_config.py -v` — all existing tests pass
2. `uv run pytest tests/ -v` — full suite passes (152 tests)
3. `./workflow.sh t1` (ruff) clean
4. `./workflow.sh t2` (mypy) clean

---

## Issue #116 — get_audio_url() synchronous base64 blocks IPC bridge thread (complex+)

⚠️ **Risk-flag**: pywebview ↔ Python IPC bridge (§12)

**Change**: Add a file size guard to `get_audio_url()` to prevent blocking the IPC bridge thread on large files. If the file exceeds a reasonable threshold, return an empty string (or error) instead of reading+encoding synchronously.

**Rationale**: `get_audio_url()` at `api.py:336-338` reads the entire file and base64-encodes it synchronously on pywebview's internal `_call` thread. While preview files are typically <500KB, there is no upper bound. A size guard prevents accidental blocking on unexpectedly large files. The existing path traversal protection (#111) already restricts access to allowed directories, so this is a defense-in-depth measure.

**Design decision**: Use a **file size limit** (suggested: 5MB, verify against codebase) rather than switching to pywebview's HTTP server or async encoding. Rationale:
- pywebview's built-in HTTP server requires a different architecture (registering routes before `webview.start()`) and would need the audio player bridge JS rewritten — disproportionate for <500KB preview files
- Async chunked encoding is not feasible on the synchronous `_call` thread
- A size guard is simple, effective, and matches the existing guard pattern (path validation, existence check)

**Files**:
- `src/api.py:330-338`: Add size check before `path.read_bytes()`. If `path.stat().st_size > MAX_AUDIO_URL_BYTES`, log warning and return `""`.
- `src/api.py` (module level): Define `MAX_AUDIO_URL_BYTES = 5 * 1024 * 1024  # 5MB`

**Affected callers**: `get_audio_url()` is called from the JS bridge (`window.pywebview.api.get_audio_url()`). Callers already handle empty-string return (the existing code returns `""` for missing/invalid files).

**Related tests**: `tests/test_api.py` — `TestGetAudioUrl` class (L250-322) already has comprehensive tests for path traversal, missing files, empty paths, symlinks. Add `test_get_audio_url_rejects_oversized_file`.

**Verification**:
1. `uv run pytest tests/test_api.py -v` — all existing + new tests pass
2. `uv run pytest tests/ -v` — full suite passes
3. `./workflow.sh t1` (ruff) clean
4. `./workflow.sh t2` (mypy) clean

---

## Issue #123 — os._exit(0) bypasses Python cleanup — preview tempfile leak (complex+)

⚠️ **Risk-flag**: Shutdown / cleanup paths (§12)

**Change**: Track preview tempfiles created by `preview_tts()` and delete them before `os._exit(0)` in the shutdown path.

**Rationale**: `preview_tts()` at `api.py:173` creates tempfiles with `delete=False` (so they survive for playback). These files are never cleaned up because `os._exit(0)` at `main.py:214` bypasses all Python finalization (`atexit`, `__del__`, context managers). The `os._exit(0)` itself is a necessary workaround for pywebview shutdown hangs (#77) and must remain — but we can clean up before calling it.

**Design**:
1. Add a `_preview_tempfiles: list[Path]` list to the `Api` class
2. In `preview_tts()`, append `Path(tmp_path)` to `_preview_tempfiles` after successful creation
3. Add a `cleanup_preview_files()` method to `Api` that deletes all tracked tempfiles (with error suppression — file may already be gone)
4. In `main.py`, call `api.cleanup_preview_files()` in all three shutdown paths:
   - `_on_quit()` (L137-142) — before `window.destroy()`
   - `_on_window_closing()` (L182-193) — before `begin_shutdown()`
   - Normal exit path (L209-214) — before `os._exit(0)`

**Files**:
- `src/api.py`: Add `_preview_tempfiles` list, append in `preview_tts()`, add `cleanup_preview_files()` method
- `src/main.py`: Call `api.cleanup_preview_files()` in all three shutdown paths

**Affected callers**: `preview_tts()` is called from the JS bridge. The cleanup is internal to shutdown — no external API change.

**Related tests**:
- `tests/test_api.py`: `TestPreviewTts` class (L213-242) — add `test_preview_tts_tracks_tempfile` and `test_cleanup_preview_files_removes_tracked_files`
- `tests/test_main.py` (if exists) or manual verification of shutdown paths

**Verification**:
1. `uv run pytest tests/test_api.py -v` — all existing + new tests pass
2. `uv run pytest tests/ -v` — full suite passes
3. `./workflow.sh t1` (ruff) clean
4. `./workflow.sh t2` (mypy) clean
5. Manual: run app, preview TTS, quit — verify no `.mp3` files left in system temp dir

---

## Implementation Order

1. **#117 first** (simple, independent) — gate diagnostic_monitor
2. **#116 + #123 together** (both touch `api.py`, share shutdown/IPC context) — size guard + tempfile cleanup
