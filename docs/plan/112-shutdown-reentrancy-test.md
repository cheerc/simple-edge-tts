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

Extract the shutdown logic into module-level functions, wired via `lambda` in `main()`:

1. **`execute_quit_shutdown(audio_player, api, tray, window)`** — module-level function (新增)
   - Encapsulates the current `_on_quit()` closure body: `begin_shutdown()` → `cleanup_preview_files()` → `tray.stop()` → `shutdown_event_loop()` → `window.destroy()`
   - Directly testable with mocks — no factory needed
   - Wired in `main()` as: `on_quit=lambda: execute_quit_shutdown(audio_player, api, tray, window)`
   - The `lambda` resolves `tray` via Python late-binding at call time — no circular dependency (Reviewer2 finding F1, Path B)

2. **`execute_window_closing_shutdown(audio_player, api, window)`** — module-level function (新增)
   - Encapsulates the current `_on_window_closing()` closure body: `begin_shutdown()` → `cleanup_preview_files()` → monkey-patch `evaluate_js`
   - Returns `None` (implicit) — allows window to close normally. **Must NOT return `False`**: in pywebview, returning `False` from the `closing` event handler **cancels** the close. (Reviewer finding F1)
   - Wired in `main()` as: `window.events.closing += lambda: execute_window_closing_shutdown(audio_player, api, window)`

**Design decision**: Plain module-level functions + `lambda` wiring (Reviewer2 Path B). Rationale:
- Module-level functions are directly importable and testable — no factory function indirection
- `lambda` in `main()` provides late-binding for `tray` (solves the circular dependency cleanly)
- `_on_window_closing` doesn't need `tray` — only `audio_player`, `api`, `window`
- Same pattern for both handlers: extract logic → wire with `lambda`

### Phase B: Add dual-trigger regression test

New test file `tests/test_shutdown.py`:

**`test_dual_trigger_no_hang`** — simulate Cmd+Q → `_on_quit()` → `window.destroy()` → `_on_window_closing()` re-enters.

**Mock wiring for reentrancy** (reviewer finding F2): A mock `window` will NOT automatically trigger `window.events.closing` when `window.destroy()` is called. The test must explicitly wire `mock_window.destroy.side_effect` to invoke the closing handler to correctly simulate the reentrancy path:
```python
# Wire reentrancy: window.destroy() triggers the closing handler
mock_window.destroy.side_effect = on_window_closing
```

**Idempotency assertions** (reviewer finding F2): `api.cleanup_preview_files` and `audio_player.begin_shutdown` are called from multiple shutdown entry points. Do NOT use `assert_called_once` — verify they are called at least once, and verify idempotency by checking the monkey-patch guard (`window._original_evaluate_js is not None` after first call) and that no exceptions are raised on re-entry.

Verify:
- `audio_player.begin_shutdown()` called (at least once)
- `api.cleanup_preview_files()` called (at least once)
- `tray.stop()` called (at least once)
- `shutdown_event_loop()` called (at least once)
- Monkey-patch guard holds: `window._original_evaluate_js` set exactly once
- No exceptions raised during dual trigger

## Files

| File | Action | Description |
|------|--------|-------------|
| `src/main.py` | Modify | Extract `execute_quit_shutdown` + `execute_window_closing_shutdown` to module level; wire via `lambda` in `main()` |
| `tests/test_shutdown.py` | Create | Dual-trigger regression test + individual handler tests |

## Affected Callers

- `src/main.py:148-150` — `SystemTrayManager(on_quit=_on_quit)` → becomes `SystemTrayManager(on_quit=lambda: execute_quit_shutdown(audio_player, api, tray, window))`
- `src/main.py:199` — `window.events.closing += _on_window_closing` → becomes `window.events.closing += lambda: execute_window_closing_shutdown(audio_player, api, window)`
- `src/system_tray.py:121` — `self._on_quit()` — no change (calls the same callable)
- No test files reference `_on_quit` or `_on_window_closing` directly (they're closures, not importable)

## Related Tests

- `tests/test_audio_player.py::TestShutdownGuard` — existing shutdown guard tests (reference pattern)
- `tests/test_system_tray.py` — SystemTrayManager tests (mock pattern for tray)
- `tests/test_api.py` — `cleanup_preview_files` tests (idempotency pattern)

## Deferred (out of scope for this PR)

- **Normal-exit path** (`main.py:214-218`): The post-`webview.start()` cleanup sequence duplicates `_on_quit` logic but is not consolidated into the extracted handlers. Consolidation would require restructuring the normal-exit flow (which also calls `os._exit(0)`) — deferred to avoid scope creep. The extracted handlers are only for the event-driven paths (tray Quit + window closing). (Reviewer2 finding F2)
- **`_on_quit` reentrancy after window destruction**: If tray Quit is invoked after X-button already closed the window, `_on_quit()` calls `window.destroy()` on an already-destroyed window. This is an existing behavior (not introduced by this refactor) and is mitigated by all cleanup calls being idempotent. Deferred to a separate issue. (Reviewer2 finding F3)

## Verification

1. `uv run pytest tests/test_shutdown.py -v` — new tests pass
2. `uv run pytest tests/ -v` — full suite passes (expect ~162 tests)
3. `./workflow.sh t1` (ruff) clean
4. `./workflow.sh t2` (mypy) clean
5. Manual smoke: `uv run python -c "from src.main import execute_quit_shutdown, execute_window_closing_shutdown; print('imports OK')"`
