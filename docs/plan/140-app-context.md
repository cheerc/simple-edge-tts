# #140: AppContext — Tight Coupling Refactor Plan

> **For agentic workers:** Use `impl-task-loop` skill.

**Goal:** 降低 `execute_quit_shutdown()` 的參數耦合——從 4 個獨立物件（audio_player, api, tray, window）改為單一 AppContext，簡化生命週期管理並降低維護成本。

**Architecture:** 引入 `AppContext` dataclass，持有 core 物件的 reference。Shutdown 函數簽名從 4 params → 1 param。不改變任何行為邏輯，純重構。

**Tech Stack:** Python 3.14, dataclasses

**Risk-Flags:** shutdown / cleanup handler + window close / quit → D3 review 建議（但本次為純重構、行為不變）

## Global Constraints

- 不改變 shutdown 的執行順序或行為
- `test_main.py` 現有 5 個 shutdown 測試必須全部通過
- 不影響 tray.start() / webview.start() 的時序

---

### Task 1: Introduce AppContext dataclass

**Files:**
- Create: `src/app_context.py`
- Modify: `src/main.py`

**Step 1: Create AppContext**

```python
# src/app_context.py
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppContext:
    """Holds references to core application objects for lifecycle management.

    Replaces the 4-parameter lambda in SystemTrayManager shutdown with
    a single context object, reducing coupling and simplifying future
    component additions.
    """
    audio_player: Any = None
    api: Any = None
    tray: Any = None
    window: Any = None
```

**Step 2: Update main.py**

- `execute_quit_shutdown(ctx: AppContext)` — 從 ctx 取值
- `execute_window_closing_shutdown(ctx: AppContext)` — 同上
- `_run_cleanup(ctx: AppContext)` — 同 #139 的統一 cleanup
- `SystemTrayManager(on_quit=lambda: execute_quit_shutdown(ctx))` — 1 param
- 所有 call sites 更新

### Verification

1. `ruff check src/ tests/` 通過
2. `uv run pytest tests/test_main.py -v` — 5 shutdown tests passed
3. `uv run pytest tests/ -v` — 211 passed
4. Code review 重點：確認 `ctx` 的 lazy binding 不受 lambda capture 影響

### Complexity

此 task 為 simple（純重構、行為不變、無新邏輯）。若與 #138 合併則整體 complex+。
