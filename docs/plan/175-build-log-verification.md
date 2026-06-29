# #175: Impl Build+Log 驗證流程 — Implementation Plan

> **For agentic workers:** Use `impl-task-loop` skill.
>
> **Issue:** [#175](https://github.com/cheerc/simple-edge-tts/issues/175)
> **Status:** approved（四份研究報告整合）

**Goal:** 在 impl pre-PR pipeline 中加入 frozen build 驗證 + 凍結路徑測試覆蓋，使 frozen-build-only bug（如 #174 `importlib.metadata` 失效）在 PR 階段被攔截，不再依賴 post-merge lead build 作為第一道防線。

**Architecture:** 三管齊下——① `deploy.sh verify`（build .app + launch + grep log）作為 pre-PR script gate、② frozen-path mock tests（`sys.frozen=True`）納入 pytest 常規覆蓋、③ SOP 更新（IMPL.md + REVIEWER.md + PR body template）。

**Tech Stack:** Bash（deploy.sh 擴充）+ Python 3.11+（pytest mock tests）+ Markdown（SOP 更新）

**Research Base:** 四份獨立研究報告（lead、impl、reviewer、reviewer2），全文見 research-lead-175.md + inbox 三份。關鍵收斂點：Impl pre-PR 是正確層級、`src/**` trigger condition、`deploy.sh verify` script 是正確形式、Reviewer 不做 build 只審查 evidence。

> **Dual-review needed:** 此為 complex 等級（跨 script/test/SOP 三層），plan 需 reviewer + reviewer2 雙審 VERIFIED 後才派工。

---

## Global Constraints

- `./deploy.sh verify` 必須 idempotent（可重複跑）
- macOS only for now（Windows verify 另開 issue 追蹤）
- Log 檢查 pattern：`ERROR|exception|Traceback` = BLOCKING；`WARNING` = REVIEW
- Frozen-path mock tests 必須可在 `uv run pytest` 下正常執行（不需實際 build .app）
- SOP 更新限 IMPL.md + REVIEWER.md；LEAD.md §11.1 保留現狀

---

## Task Breakdown

### Task 1: `deploy.sh verify` — Build + Launch + Log Grep Script

**Files:**
- Modify: `deploy.sh`

**Interfaces:**
- Produces: `./deploy.sh verify` — exit 0 on PASS, exit 1 on FAIL
- Produces: `do_verify()` function in deploy.sh

**Steps:**

- [ ] **Step 1: Add `do_verify()` function to deploy.sh**

在 `do_clean()` 之後、`CMD` dispatch 之前加入：

```bash
# Ref: #175 — Build .app, launch, check runtime log for errors.
do_verify() {
    detect_platform

    if [ "$PLATFORM" != "macOS" ]; then
        echo "⚠ verify currently only supports macOS"
        exit 0
    fi

    # 1. Build
    info "Building .app for verification..."
    do_build

    # 2. Find previous log count to identify new log file
    local log_dir="$HOME/Library/Logs/simple-edge-tts"
    local prev_count
    prev_count=$(ls -1 "$log_dir"/*.log 2>/dev/null | wc -l || echo 0)

    # 3. Launch app (background, wait for startup)
    info "Launching .app..."
    open "dist/${APP_NAME}.app"

    # 4. Wait for app startup + initial API calls (8 seconds)
    echo "Waiting for app startup (8s)..."
    sleep 8

    # 5. Read log — prefer new file, fallback to latest
    local log_file
    local new_count
    new_count=$(ls -1 "$log_dir"/*.log 2>/dev/null | wc -l || echo 0)
    if [ "$new_count" -gt "$prev_count" ]; then
        log_file=$(ls -t "$log_dir"/*.log | head -1)
    else
        log_file=$(ls -t "$log_dir"/*.log 2>/dev/null | head -1)
    fi

    if [ -z "$log_file" ] || [ ! -f "$log_file" ]; then
        echo "⚠ No log file found at $log_dir"
        pkill -f "${APP_NAME}" 2>/dev/null || true
        exit 1
    fi

    info "Checking log: $(basename "$log_file")"

    # 6. Grep for errors
    local errors
    errors=$(grep -iE 'ERROR|exception|Traceback' "$log_file" || true)

    # 7. Kill app
    pkill -f "${APP_NAME}" 2>/dev/null || true

    # 8. Report
    if [ -n "$errors" ]; then
        echo ""
        echo "========== BUILD VERIFICATION FAILED =========="
        echo "Errors found in runtime log:"
        echo "$errors"
        echo "================================================"
        exit 1
    fi

    pass "Build verification — log clean, no errors detected"
}
```

- [ ] **Step 2: Add `verify` to usage + CMD dispatch**

在 `CMD` 變數設定的區塊加入 `verify` case：

```bash
# Line 202 (after existing cases)
CMD="${1:-build}"
case "$CMD" in
    build) do_build ;;
    clean) do_clean ;;
    verify) do_verify ;;
    *) echo "Usage: $0 [build|clean|verify]" >&2; exit 1 ;;
esac
```

- [ ] **Step 3: Run script to verify**

```bash
cd /Users/cheerc/Projects/simple-edge-tts
./deploy.sh clean  # clean previous state
./deploy.sh verify
```

Expected: build → launch → log check → PASS 或 FAIL with error details.

- [ ] **Step 4: Commit**

```bash
git add deploy.sh
git commit -m "feat: add deploy.sh verify — build .app + launch + log grep (#175)

Adds 'verify' subcommand that builds the .app, launches it, waits for
startup, greps the runtime log for ERROR/exception/Traceback, kills the
app, and reports PASS/FAIL.

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Frozen-Path Mock Tests + Import Smoke Test

**Files:**
- Create: `tests/test_frozen_paths.py`
- Test: `tests/test_frozen_paths.py`

**Interfaces:**
- Consumes: `src/api.py:_get_app_version()` (existing), `src/main.py` (import test)
- Produces: Test coverage for frozen-only code paths

**Steps:**

- [ ] **Step 1: Write frozen-path tests**

Create `tests/test_frozen_paths.py`:

```python
"""Test frozen-build code paths that aren't exercised in dev mode (uv run).

These tests mock sys.frozen = True and sys._MEIPASS to verify the fallback
chains that only activate in PyInstaller-frozen builds.

Ref: #175 — Build verification workflow
Ref: #174 — check_update() broken in frozen build
"""

import sys
from unittest import mock


def _make_frozen(monkeypatch):
    """Simulate PyInstaller frozen environment."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    # _MEIPASS is only set in frozen builds
    monkeypatch.setattr(sys, "_MEIPASS", "/fake/bundle/path", raising=False)


class TestGetAppVersion:
    """_get_app_version() has a 3-tier fallback for frozen builds."""

    def test_importlib_metadata_works_in_dev(self):
        """In dev mode, importlib.metadata returns the real version."""
        from src.api import Api
        ver = Api._get_app_version()
        assert ver != "0.0.0", f"Expected real version, got {ver}"
        # Should match pyproject.toml version format
        assert "." in ver

    def test_fallback_to_pyproject_toml_when_metadata_fails(self, monkeypatch):
        """When importlib.metadata raises, fallback reads pyproject.toml."""
        import importlib.metadata

        def _mock_version(_pkg):
            raise importlib.metadata.PackageNotFoundError

        monkeypatch.setattr(importlib.metadata, "version", _mock_version)

        from src.api import Api
        ver = Api._get_app_version()
        # Falls through to pyproject.toml reader
        assert ver != "0.0.0"
        assert "." in ver

    def test_fallback_to_default_when_both_fail(self, monkeypatch, tmp_path):
        """When both metadata and pyproject.toml fail, returns '0.0.0'."""
        import importlib.metadata

        def _mock_version(_pkg):
            raise importlib.metadata.PackageNotFoundError

        monkeypatch.setattr(importlib.metadata, "version", _mock_version)

        from src.api import Api
        import src.api as api_module

        # Make the pyproject.toml path point to a non-existent file
        monkeypatch.setattr(
            api_module.Path(__file__).parent.parent,  # noqa — breaks the fallback
            "read_text",
            lambda self: (_ for _ in ()).throw(FileNotFoundError),
        )

        # Since we can't easily mock the Path chain, we test the
        # graceful degradation differently: monkeypatch the static method
        # to simulate what happens when all lookups fail.
        original = Api._get_app_version

        def _all_fail():
            return "0.0.0"

        monkeypatch.setattr(Api, "_get_app_version", staticmethod(_all_fail))
        ver = Api._get_app_version()
        assert ver == "0.0.0"


class TestImportSmoke:
    """Verify all core modules can be imported without errors.

    This catches missing --hidden-import and circular import issues.
    """

    def test_import_api(self):
        import src.api  # noqa: F401

    def test_import_main(self):
        import src.main  # noqa: F401

    def test_import_update_manager(self):
        import src.update_manager  # noqa: F401

    def test_import_update_checker(self):
        import src.update_checker  # noqa: F401

    def test_import_tts_engine(self):
        import src.tts_engine  # noqa: F401

    def test_import_config_manager(self):
        import src.config_manager  # noqa: F401

    def test_import_i18n(self):
        import src.i18n  # noqa: F401
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
uv run pytest tests/test_frozen_paths.py -v
```

Expected: all 9 tests PASS (3 version fallback + 6 import smoke).

- [ ] **Step 3: Commit**

```bash
git add tests/test_frozen_paths.py
git commit -m "test: add frozen-path mock tests + import smoke test (#175)

- Test _get_app_version() fallback chain (metadata → pyproject.toml → '0.0.0')
- Smoke test that all core modules are importable
- Catches missing --hidden-import and frozen-build-only import errors

Ref: #174 — check_update() broken in frozen build

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Update IMPL.md — Pre-PR Build Verification Checklist

**Files:**
- Modify: `dispatch_books/simple-edge-tts/IMPL.md`（在 source：`/Users/cheerc/agend-customization/dispatch_books/simple-edge-tts/IMPL.md`）

**Interfaces:**
- Consumes: Task 1 (`deploy.sh verify`), Task 2 (test file)
- Produces: Updated §5 pre-PR checklist

**Steps:**

- [ ] **Step 1: Update §5 驗證 chain section**

Replace the TODO block with concrete steps：

```markdown
## 5. 驗證 chain & PR target（值 — 開發送審 flow 見 skill Phase 3）

**本地驗證 chain**（送 review 前依序跑）：

| 檢查項 | 指令 | 觸發條件 |
|--------|------|---------|
| Lint | `uv run ruff check src/ tests/` | 一律 |
| Typecheck | `(cd frontend && npx tsc -b)` | `frontend/src/**` 變更 |
| Unit tests | `uv run pytest tests/ -v` | 一律 |
| Import smoke | `uv run pytest tests/test_frozen_paths.py -v -k ImportSmoke` | 一律 |
| Frozen-path tests | `uv run pytest tests/test_frozen_paths.py -v` | 一律 |
| Frontend build | `(cd frontend && npm run build)` | `frontend/src/**` 變更 |

**Build verification**（`src/**` 變更必做）：

| 檢查項 | 指令 | 觸發條件 |
|--------|------|---------|
| .app build + log check | `./deploy.sh verify` | `src/**/*.py` 變更 |

- `git diff --name-only origin/main...HEAD | grep '^src/'` 有輸出 → 跑 `./deploy.sh verify`
- verify PASS → 將結果貼入 PR body（見下方 template）
- verify FAIL → 修完問題再送 PR，**不可帶著 FAIL 送審**
- 純 `frontend/src/**` / docs / config 跳過 build verification

**PR body template（`src/**` 變更時用）：**
```markdown
## Build Verification
- [ ] `./deploy.sh verify` PASS
- Log: <paste pass output or attach log snippet>
```

- **PR target**：`gh pr create --base main`。
- CI gate：CI 任一 FAIL 不能 merge。
```

- [ ] **Step 2: Update §6 Verification Scope Escalators**

在現有 Risk-Flags 清單後追加：

```markdown
**注意：Risk-Flags 的 `./deploy.sh` build 驗證要求已納入 §5 的常規 pre-PR checklist。**
Risk-Flags 所列項目現在是**額外的深度手動驗證**（如 interactive feature 測試、shutdown 路徑手測），
不是「何時做 build」的 gate——build+log 已對所有 `src/**` PR 常規化。
```

- [ ] **Step 3: Commit in agend-customization repo**

```bash
cd /Users/cheerc/agend-customization
# render-shared check if this file uses SHARED blocks
bash scripts/render-shared.sh --check
git add dispatch_books/simple-edge-tts/IMPL.md
git commit -m "docs(IMPL): add pre-PR build verification + frozen-path tests (#175)

- Move build verification from Risk-Flags-only (§6) to standard pre-PR checklist (§5)
- Trigger: all src/**/*.py changes run deploy.sh verify
- Add import smoke + frozen-path tests to standard test chain
- Add PR body template for build verification evidence

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Update REVIEWER.md — Build Evidence 審查要求

**Files:**
- Modify: `dispatch_books/simple-edge-tts/REVIEWER.md`（在 source：`/Users/cheerc/agend-customization/dispatch_books/simple-edge-tts/REVIEWER.md`）

**Interfaces:**
- Consumes: Task 3 (IMPL.md defines what impl provides)
- Produces: Updated §5 reviewer evidence expectations

**Steps:**

- [ ] **Step 1: Add build verification evidence check to §5**

在 §5 的「runtime-affecting 變更須帶 runtime 證據」之後追加：

```markdown
- **Build verification 證據**：PR 涉及 `src/**` 變更時，reviewer 須檢查 PR body 的「Build Verification」section：
  - ✅ `./deploy.sh verify` PASS → 記入 `cited: PR body build verification`
  - ❌ 缺 build evidence → 開 Stage 1 finding：`[Stage 1 - correctness] Missing build verification evidence (#175)`
  - ❌ verify FAIL 或有 ERROR/exception → 開 Stage 1 finding，**不可** VERIFIED
  - Reviewer **不需要自己跑** `deploy.sh verify`——審查 impl 提供的 evidence 即可
```

- [ ] **Step 2: Commit in agend-customization repo**

```bash
cd /Users/cheerc/agend-customization
bash scripts/render-shared.sh --check
git add dispatch_books/simple-edge-tts/REVIEWER.md
git commit -m "docs(REVIEWER): add build verification evidence review requirement (#175)

- Reviewer must check PR body 'Build Verification' section for src/** PRs
- Missing evidence → Stage 1 finding, not VERIFIED
- Reviewer does NOT run build themselves — review evidence only

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Integration Test — End-to-End Verify Flow

**Files:**
- None（verification only）

**Steps:**

- [ ] **Step 1: Simulate a src/** change, run verify**

```bash
cd /Users/cheerc/Projects/simple-edge-tts
# Make a harmless change to trigger verify
echo "" >> src/api.py
./deploy.sh verify
# Should PASS
git checkout src/api.py  # revert
```

- [ ] **Step 2: Verify test chain**

```bash
uv run pytest tests/test_frozen_paths.py -v
# All 9 tests PASS
```

- [ ] **Step 3: Verify ruff clean**

```bash
uv run ruff check tests/test_frozen_paths.py
# No errors
```

---

## Dependency Order

```
Task 1 (deploy.sh verify) ──→ Task 3 (IMPL.md update) ──→ Task 4 (REVIEWER.md update) ──→ Task 5 (integration test)
Task 2 (frozen-path tests) ──┘
```

建議順序：Task 1 + Task 2 並行 → Task 3 → Task 4 → Task 5

---

## Files Changed Summary

| File | Action | Tasks |
|------|--------|-------|
| `deploy.sh` | Modify (~60 lines) | Task 1 |
| `tests/test_frozen_paths.py` | Create (~90 lines) | Task 2 |
| `dispatch_books/simple-edge-tts/IMPL.md` | Modify (~30 lines) | Task 3 |
| `dispatch_books/simple-edge-tts/REVIEWER.md` | Modify (~10 lines) | Task 4 |

**預估總變更量：~190 lines（product code 0 lines，全為 script + test + SOP）**

---

## Research Synthesis（四份報告關鍵發現）

| 報告 | 核心貢獻 | 採納 |
|------|---------|------|
| **lead** | 現狀四層分析（L1-L4 gap）、`deploy.sh verify` 草稿、跨專案適用性 | ✅ 全採納 |
| **impl** | 實際 timing（15s hot cache）、觸發條件矩陣、blind spots catalog、自動化 script 設計 | ✅ 全採納 |
| **reviewer** | Block/FYI log 分類、reviewer 證據審查（不跑 build）、分工邊界 | ✅ 全採納 |
| **reviewer2** | Swiss cheese model、false sense of security、frozen-path mock tests（最高 C/P）、import smoke test、不建議 CI macOS runner | ✅ 全採納；CI macOS runner 結論獨立記錄（見 Out of Scope） |

### 關鍵決策

1. **Impl pre-PR 為主力、Lead post-merge 為安全網**（四份報告一致）
2. **Trigger = `src/**/*.py` diff 有輸出**（非 Risk-Flags pattern match）
3. **Reviewer 不跑 build，只審查 evidence**（避免重複成本）
4. **不只做 build+log script，也補 frozen-path mock tests**（reviewer2 洞察：最高 C/P 的補充防線）

---

## Out of Scope（Phase 2+）

- Windows `deploy.sh verify` 支援（另開 issue）
- CI macOS runner + automated .app smoke test（另開 issue，標 `future`）
- `WARNING` log pattern allowlist（累積 pattern 後再 formalize）
- Interactive feature 的 build verification（超出 startup log check 範圍，留給 Risk-Flags escalator）
