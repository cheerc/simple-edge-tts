---
required_reads:
  - src/main.py
  - src/audio_player.py
  - src/system_tray.py
  - src/api.py
  - tests/test_audio_player.py
  - tests/test_system_tray.py
  - tests/test_api.py
---

# #112 — Shutdown Dual-Entry Reentrancy Regression Test

## Summary

Extract `_on_quit` and `_on_window_closing` from `main()` closures into testable module-level functions, then add an automated regression test for the dual-trigger scenario (Cmd+Q → `_on_quit()` → `window.destroy()` → `_on_window_closing()` re-enters).

**research skipped**: 影響面明確 — shutdown handlers 僅在 `main()` 內定義、僅被 tray/window.events 引用，無外部 consumer。既有測試（`test_audio_player.py::TestShutdownGuard`、`test_system_tray.py`、`test_api.py` 的 `cleanup_preview_files` 測試）已覆蓋個別 component 的 shutdown 行為，獨缺雙觸發整合測試。

## Rationale

Prior escaped defects (#47, #77, #81) all involved shutdown hangs. The current monkey-patch guard at `main.py:191` (`if original is None`) correctly ensures idempotency, but no automated test validates that the dual-trigger scenario does not hang. After Wave 3 (#123) added `cleanup_preview_files()` to all three shutdown paths, there are now more state mutations in the shutdown sequence — a regression test is more valuable than before.

## Design

### Phase A: Extract handlers as testable functions (refactor, no behavior change)

Extract two functions from `main()` closures to module level:

1. **`create_on_quit_handler(audio_player, api, tray, window)`** → returns `Callable[[], None]`
   - Encapsulates the current `_on_quit()` closure body
   - Signature: accepts mockable dependencies instead of capturing them from `main()` scope

2. **`create_on_window_closing_handler(audio_player, api, window)`** → returns `Callable[[], bool]`
   - Encapsulates the current `_on_window_closing()` closure body
   - Returns `False` (cancel native close — existing behavior preserved)

**Design decision**: Factory functions (return closures) rather than plain functions. Rationale:
- The handlers need references to `audio_player`, `api`, `window` which are created in `main()` — factory functions wire these at creation time
- The returned callable has the same signature as the current closures → zero change to how they're wired (`tray = SystemTrayManager(on_quit=handler)`, `window.events.closing += handler`)
- Tests create factories with mocks, then call the returned handler — clean, no global state

### Phase B: Add dual-trigger regression test

New test file `tests/test_shutdown.py`:
- Test: `test_dual_trigger_no_hang` — simulate Cmd+Q → `_on_quit()` → `window.destroy()` → `_on_window_closing()` re-enters
- Verify: all expected calls made exactly once (idempotency), no exceptions raised, monkey-patch guard holds

## Files

| File | Action | Description |
|------|--------|-------------|
| `src/main.py` | Modify | Extract `_on_quit` and `_on_window_closing` to module-level factory functions |
| `tests/test_shutdown.py` | Create | Dual-trigger regression test + individual handler tests |

## Affected Callers

- `src/main.py:148-150` — `SystemTrayManager(on_quit=_on_quit)` → becomes `SystemTrayManager(on_quit=create_on_quit_handler(...))`
- `src/main.py:199` — `window.events.closing += _on_window_closing` → becomes `window.events.closing += create_on_window_closing_handler(...)`
- `src/system_tray.py:121` — `self._on_quit()` — no change (calls the same callable)
- No test files reference `_on_quit` or `_on_window_closing` directly (they're closures, not importable)

## Related Tests

- `tests/test_audio_player.py::TestShutdownGuard` — existing shutdown guard tests (reference pattern)
- `tests/test_system_tray.py` — SystemTrayManager tests (mock pattern for tray)
- `tests/test_api.py` — `cleanup_preview_files` tests (idempotency pattern)

## Verification

1. `uv run pytest tests/test_shutdown.py -v` — new tests pass
2. `uv run pytest tests/ -v` — full suite passes (expect ~162 tests)
3. `./workflow.sh t1` (ruff) clean
4. `./workflow.sh t2` (mypy) clean
5. Manual smoke: `uv run python -c "from src.main import create_on_quit_handler, create_on_window_closing_handler; print('imports OK')"`
