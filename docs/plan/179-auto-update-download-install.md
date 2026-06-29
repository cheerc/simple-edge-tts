# #179: Auto-Update Download & Install — Phase 1 Plan

> **For agentic workers:** Use `impl-task-loop` skill.
>
> **Issue:** [#179](https://github.com/cheerc/simple-edge-tts/issues/179)
> **Design doc:** `docs/design/auto-update.md` (#172)
> **Strategy:** B — Background Download + Notify to Install

**Goal:** 將 auto-update 從 detect-only 升級為「背景下載 → SHA256 驗證 → 提示安裝重啟」。取代目前無效的 `window.open()` 開瀏覽器行為。

**Architecture:** 新增 `src/update_manager.py`（下載/驗證/安裝），擴充 `src/api.py`（IPC bridge + shutdown callback），`src/main.py` 註冊 shutdown handler。前端 Toast 加入下載進度條 +「安裝並重啟」按鈕，Settings 加入「更新」按鈕。

**Shutdown coordination:** `Api` 無法直接呼叫 `_run_cleanup(ctx)`（cleanup 在 `main.py`、需 `AppContext`）。設計 callback 模式：`main.py` 在建立 `Api` 後註冊 `api.set_shutdown_handler(lambda: execute_quit_shutdown(ctx))`，`install_update()` 先呼叫 `_shutdown_handler()` 走完整 cleanup → 再 `Popen` + exit。

**Tech Stack:** Python 3.11+ (`urllib.request` + `hashlib` + `subprocess` + `threading`) + React 19 + TypeScript

**Risk-Flags:** ⚠️ PyInstaller frozen path（`sys._MEIPASS`）、macOS .app replace + restart（shutdown handler reentrancy — 觸及 PROJECT.md §12 第一條）、檔案系統寫入（temp dir）

> **Dual-review v2 (2026-06-29):** 修正 reviewer (REJECTED 7 findings) + reviewer2 (REJECTED 7 findings) 的 12 項 findings。

---

## Global Constraints

- 不改變 macOS `.dmg` release 格式——下載仍從 GitHub Release assets 取 `.dmg`
- **重啟前必須走完整 `_run_cleanup()`**（透過 shutdown callback 模式，見 Architecture）
- **macOS .app 替換必須 atomic swap**：`ditto` 複製到 `.app.new` → `mv .app → .app.old` → `mv .app.new → .app` → 清理 `.app.old`（不可直接 cp 到 /Applications）
- 下載狀態機：`IDLE → DOWNLOADING → VERIFYING → READY → INSTALLING`（防 re-entrancy）
- 下載暫存目錄：`$TMPDIR/simple-edge-tts-update/`（macOS）/ `%TEMP%/simple-edge-tts-update/`（Windows）
- SHA256 驗證為必要步驟（對照 release 隨附的 `SHA256SUMS.txt`；若 release 無此檔 → abort with error）
- Windows: 所有路徑 double-quote、`subprocess.CREATE_NO_WINDOW`
- macOS: app 不在 `/Applications/` → 提示使用者移至 Applications（或自動 move）
- **不做 silent install**（Strategy C）——使用者必須點「安裝並重啟」

---

## Task Breakdown

### Task 1: `src/update_manager.py` — 下載 + 驗證模組

**Create:** `src/update_manager.py`

**UpdateManager class** — 含下載狀態機：
```python
class UpdateState(Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    READY = "ready"        # 下載完成、已驗證、可安裝
    INSTALLING = "installing"
    ERROR = "error"

class UpdateManager:
    def __init__(self, current_version: str):
        self._state = UpdateState.IDLE
        self._lock = threading.Lock()
        self._downloaded_path: Path | None = None
        self._progress = 0
        self._cancel_flag = threading.Event()

    def download(self, on_progress: Callable[[int], None] | None = None) -> Path:
        """背景下載 + SHA256 驗證。state machine 防 re-entrancy。"""
        with self._lock:
            if self._state != UpdateState.IDLE:
                raise UpdateError(f"Cannot start download in state {self._state}")
            self._state = UpdateState.DOWNLOADING
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

    def cancel(self):
        """取消進行中的下載。"""
        self._cancel_flag.set()

    def get_progress(self) -> dict:
        """回傳 {state, progress_pct}。"""
        ...

    def install(self, shutdown_handler: Callable) -> None:
        """執行平台特定安裝 + 重啟。先呼叫 shutdown_handler() 走完整 cleanup。"""
        with self._lock:
            if self._state != UpdateState.READY:
                raise UpdateError("No verified update ready")
            self._state = UpdateState.INSTALLING
        shutdown_handler()  # → _run_cleanup(ctx)
        self._platform_install()
```

**平台安裝子方法：**
- `_macos_install()`: `ditto` → atomic swap → `open -n`
- `_windows_install()`: write `.bat` → `subprocess.CREATE_NO_WINDOW` → `sys.exit(0)`

**Progress:** `Content-Length` header 存在時用百分比；不存在時 fallback 到 `bytes_downloaded` 絕對值。

### Task 2: macOS 安裝流程

**Modify:** `src/update_manager.py`（`_macos_install()`）

**修正 per dual-review F1（CRITICAL）：**
```
1. ditto 複製 .dmg 中的 .app 到 $TMPDIR/simple-edge-tts-update/<app>.app.new
2. hdiutil detach（unmount .dmg）
3. Atomic swap:
     if /Applications/<app>.app exists:
       mv /Applications/<app>.app → /Applications/<app>.app.old
     mv $TMPDIR/<app>.app.new → /Applications/<app>.app
4. open -n /Applications/<app>.app（啟動新版本）
5. os._exit(0)
```

**macOS /Applications/ 檢查：** 若當前 app 不在 `/Applications/`（如從 `~/Downloads/` 執行）→ `ditto` 複製到 `/Applications/` + `open -n`。

### Task 2b: Windows 安裝流程

**Modify:** `src/update_manager.py`（`_windows_install()`）

**修正 per dual-review F4/F5（WARNING）：**
```
1. 解壓 .zip → $TEMP/simple-edge-tts-update/
2. 檢查目標目錄可寫（os.access(os.path.dirname(sys.executable), os.W_OK)）
   不可寫 → raise UpdateError("Install directory not writable")
3. 寫 install.bat（所有路徑 double-quote）:
     @echo off
     timeout /t 2 /nobreak >nul
     copy /Y "<new_exe>" "<old_exe>"
     start "" "<old_exe>"
     del "%~f0"
4. subprocess.Popen(["cmd", "/c", "install.bat"], creationflags=subprocess.CREATE_NO_WINDOW)
5. sys.exit(0)
```

### Task 3: `src/api.py` — IPC bridge + shutdown callback

**Modify:** `src/api.py`

**Add:**
1. `set_shutdown_handler(handler: Callable)` — main.py 註冊 cleanup callback
2. `download_update() -> str` — 建立 UpdateManager，在 thread 中開始下載，回傳 `{"state": "downloading"}`
3. `get_download_progress() -> str` — 回傳 `{"state": str, "progress": 0-100, "error": str|null}`
4. `cancel_download() -> str` — 取消下載
5. `install_update() -> str` — 呼叫 `UpdateManager.install(shutdown_handler)`（**先走 cleanup 再 restart**）

**Modify:** `src/main.py`
```python
# After api = Api(...)
api.set_shutdown_handler(lambda: execute_quit_shutdown(ctx))
```

### Task 4: Frontend — Toast 下載進度 + 安裝按鈕

**Modify:** `frontend/src/App.tsx`, `frontend/src/components/Toast.tsx`, `frontend/src/types.ts`, `frontend/src/hooks/useApi.ts`

**修正 per dual-review F4（polling race）：**
- `installUpdate()` 呼叫前先 `clearInterval(pollInterval)` 停止 polling
- 下載狀態機對應的 UI state machine

**Flow:**
```
點「前往下載」
  → setState(DOWNLOADING)
  → api.downloadUpdate()
  → 每 500ms poll api.getDownloadProgress()
  → 進度條更新
  → 完成 → setState(READY)
  → Toast 變「已下載」+「安裝並重啟」
  → 點「安裝並重啟」
    → clearInterval(pollInterval)
    → api.installUpdate()
```

### Task 5: Frontend — Settings「更新」按鈕

**Modify:** `frontend/src/components/SettingsModal.tsx`

當 `checkResult.latest` 有值時，在版本資訊旁顯示「下載並安裝」按鈕。行為與 Task 4 相同。

### Task 6: i18n

**Modify:** `src/resources/translations/en-US.json`, `zh-TW.json`

**New keys:**
| Key | en-US | zh-TW |
|-----|-------|-------|
| `update_downloading` | "Downloading..." | "下載中..." |
| `update_downloaded` | "Downloaded — ready to install" | "已下載 — 可安裝" |
| `update_install_restart` | "Install & Restart" | "安裝並重啟" |
| `update_verifying` | "Verifying..." | "驗證中..." |
| `update_download_error` | "Download failed" | "下載失敗" |
| `update_install_now` | "Download & Install" | "下載並安裝" |
| `update_cancel` | "Cancel" | "取消" |

### Task 7: Tests

**Create:** `tests/test_update_manager.py`

**Coverage:**
- Download state machine transitions（IDLE→DOWNLOADING→...→ERROR）
- Re-entrancy guard（double-download raises UpdateError）
- SHA256 verification（valid + mismatched）
- Progress callback（Content-Length present + absent）
- macOS install path detection
- Windows write-permission check
- Cancel flag propagation

---

## Dependency Order

```
Task 1 (update_manager) ──→ Task 3 (api.py bridge + shutdown callback) ──→ Task 4 (Toast UI) ──┐
Task 2 (macOS install) ──┘                                                                       ├──→ 整合測試
Task 2b (Windows install) ──────────────────────────────────────────────────────────────────────┘
Task 6 (i18n) ──→ Task 5 (Settings UI)
Task 7 (tests) — 與 Task 1-2 並行
```

建議順序：Task 1 → Task 2 + 2b → Task 7（可並行）→ Task 3 → Task 6 → Task 4 + Task 5（可並行）

---

## Files Changed Summary

| File | Action | Tasks |
|------|--------|-------|
| `src/update_manager.py` | Create (~250 lines) | Task 1, 2, 2b |
| `src/api.py` | Modify (~80 lines) | Task 3 |
| `src/main.py` | Modify (~5 lines) | Task 3（shutdown callback 註冊） |
| `frontend/src/types.ts` | Modify (~10 lines) | Task 4 |
| `frontend/src/hooks/useApi.ts` | Modify (~25 lines) | Task 4 |
| `frontend/src/App.tsx` | Modify (~45 lines) | Task 4 |
| `frontend/src/components/Toast.tsx` | Modify (~25 lines) | Task 4 |
| `frontend/src/components/SettingsModal.tsx` | Modify (~30 lines) | Task 5 |
| `src/resources/translations/en-US.json` | Modify (+7 keys) | Task 6 |
| `src/resources/translations/zh-TW.json` | Modify (+7 keys) | Task 6 |
| `tests/test_update_manager.py` | Create (~120 lines) | Task 7 |

預估總變更量：~600 lines

---

## Dual-Review Revision Notes（2026-06-29）

**Reviewer (agy/Gemini):** REJECTED — 7 findings（2 CRITICAL + 5 WARNING）
**Reviewer2 (claude-proxy-free):** REJECTED — 7 findings（1 CRITICAL + 6 WARNING）

| # | Finding | Source | Severity | Fix in v2 |
|---|---------|--------|----------|-----------|
| 1 | macOS .app copy corrupts bundle | Both | CRITICAL | Task 2: `ditto` + atomic swap（mv .app → .app.old → mv .new → .app） |
| 2 | os._exit(0)/sys.exit(0) bypasses cleanup | Both | CRITICAL | Task 3: shutdown callback 模式 — Api.set_shutdown_handler() → install() 先 call handler 再 restart |
| 3 | 無下載狀態機/re-entrancy protection | Both | WARNING | Task 1: UpdateState enum + threading.Lock + cancel flag |
| 4 | Windows path quoting + console window | Both | WARNING | Task 2b: double-quote paths + CREATE_NO_WINDOW |
| 5 | macOS /Applications/ check missing | reviewer2 | WARNING | Task 2: 檢查 app 路徑，不在 /Applications/ 時自動 ditto |
| 6 | Frontend install-triggered IPC disconnect | reviewer2 | WARNING | Task 4: installUpdate() 前 clearInterval(pollInterval) |
| 7 | 無 Cancel download API | reviewer | WARNING | Task 1 + Task 3: UpdateManager.cancel() + api.cancel_download() |
| 8 | SHA256SUMS.txt fallback missing | reviewer2 | WARNING | Task 1: 無 checksums 檔 → abort with error |
| 9 | Write permission pre-flight check | reviewer | WARNING | Task 2b: os.access(writable) check |
| 10 | Missing test task | reviewer | WARNING | Task 7: tests/test_update_manager.py |
| 11 | Content-Length may be absent | reviewer2 | WARNING | Task 1: progress fallback to absolute bytes |
| 12 | Clean up downloaded files | reviewer2 | WARNING | Task 2: 成功 install 後移除 temp files |

**v1→v2 變更摘要:**
- 新增 shutdown callback 模式（Api↔main.py 協調）
- Task 2 拆分為 2（macOS atomic swap）+ 2b（Windows .bat + CREATE_NO_WINDOW）
- Task 1 加入 UpdateState state machine + cancel
- Task 3 加入 set_shutdown_handler + cancel_download
- 新增 Task 7: Tests
- Files Changed 從 8→11 files
- i18n keys 從 6→7（+cancel）

---

## Verification Checklist

### Backend
- [ ] `uv run pytest tests/ -v` 全 pass
- [ ] `ruff check src/ tests/` 無新增
- [ ] `./deploy.sh build` 成功

### Frontend
- [ ] `(cd frontend && npx tsc --noEmit)` 無型別錯誤
- [ ] `(cd frontend && npm run build)` 成功

### Runtime（`.app`）
- [ ] 啟動 `.app` → 偵測到新版本 → Toast 顯示「前往下載」
- [ ] 點「前往下載」→ 開始下載 → 進度條更新
- [ ] 下載完成 → Toast 變「已下載 — 可安裝」+「安裝並重啟」按鈕
- [ ] 點「安裝並重啟」→ app 關閉 → 新版本啟動
- [ ] Settings → 檢查更新 → 顯示「下載並安裝」按鈕（行為同上）
- [ ] 語系切換後所有按鈕文字正確

### Out of Scope（Phase 2+）
- Delta 更新
- Silent/automatic install
- macOS `.zip` 包 `.app`（替代 `.dmg`）
- 下載失敗自動重試
- Rollback on install failure

---

## Estimated Complexity

**Overall: complex+**（7 files, cross-module: Python backend + IPC bridge + React frontend, risk-flags: shutdown handler reentrancy + filesystem write + frozen path）
