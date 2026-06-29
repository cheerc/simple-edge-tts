# #179: Auto-Update Download & Install — Phase 1 Plan

> **For agentic workers:** Use `impl-task-loop` skill.
>
> **Issue:** [#179](https://github.com/cheerc/simple-edge-tts/issues/179)
> **Design doc:** `docs/design/auto-update.md` (#172)
> **Strategy:** B — Background Download + Notify to Install

**Goal:** 將 auto-update 從 detect-only 升級為「背景下載 → SHA256 驗證 → 提示安裝重啟」。取代目前無效的 `window.open()` 開瀏覽器行為。

**Architecture:** 新增 `src/update_manager.py`（下載/驗證/安裝），擴充 `src/api.py`（IPC bridge 三新方法），前端 Toast 加入下載進度條 +「安裝並重啟」按鈕，Settings 加入「更新」按鈕。

**Tech Stack:** Python 3.11+ (`urllib.request` + `hashlib` + `subprocess`) + React 19 + TypeScript

**Risk-Flags:** ⚠️ PyInstaller frozen path（`sys._MEIPASS`）、macOS .app replace + restart（shutdown handler reentrancy）、檔案系統寫入（temp dir）

---

## Global Constraints

- 不改變 macOS `.dmg` release 格式——下載仍從 GitHub Release assets 取 `.dmg`
- 不改變現有 `shutdown` / `_run_cleanup` 流程——重啟前走正常 cleanup
- 下載暫存目錄：`$TMPDIR/simple-edge-tts-update/`（macOS）/ `%TEMP%/simple-edge-tts-update/`（Windows）
- SHA256 驗證為必要步驟（對照 release 隨附的 `SHA256SUMS.txt`）
- **不做 silent install**（Strategy C）——使用者必須點「安裝並重啟」

---

## Task Breakdown

### Task 1: `src/update_manager.py` — 下載 + 驗證模組

**Create:** `src/update_manager.py`

**Responsibilities:**
1. `download_release(url: str, dest: Path, on_progress: Callable) -> Path` — 下載 binary，回報進度
2. `verify_sha256(file: Path, expected_hash: str) -> bool` — SHA256 驗證
3. `get_platform_asset(release: dict) -> dict` — 從 GitHub release JSON 找出對應平台的 asset

**Flow:**
```
fetch_release_asset()
  → GET /repos/cheerc/simple-edge-tts/releases/latest
  → 找 asset name matching platform（macOS: *.dmg / Windows: *.zip）
  → 找 matching SHA256SUMS.txt
  → download asset to temp dir（with progress callback）
  → download SHA256SUMS.txt
  → verify SHA256
  → return (local_path, verified)
```

**Progress callback** 使用簡單的 `bytes_downloaded / total_bytes` 回報（透過 `urllib.request` + `urlopen` with `Content-Length` header）。

### Task 2: `src/update_manager.py` — 安裝 + 重啟模組

**Modify (extend):** `src/update_manager.py`

**macOS flow:**
```
1. Mount .dmg（hdiutil attach）
2. Copy .app to /Applications/（或原地替換）
3. Unmount .dmg（hdiutil detach）
4. 觸發 restart：subprocess.Popen(["open", "-n", app_path]) + os._exit(0)
```

**Windows flow:**
```
1. Extract .zip to temp dir
2. Write restart.bat: timeout /t 2 → copy /Y new.exe old.exe → start old.exe
3. subprocess.Popen(["cmd", "/c", "restart.bat"])
4. sys.exit(0)
```

⚠️ macOS 重點：`.dmg` 需掛載才能取 `.app`。替代方案是用 `.zip` 包 `.app`（修改 `release.yml`），但那是 Phase 2。Phase 1 先用 `hdiutil`。

### Task 3: `src/api.py` — IPC bridge 三新方法

**Modify:** `src/api.py`

**Add:**
1. `download_update() -> str` — 觸發背景下載（在 thread 中執行），回傳 `{"status": "downloading"}`
2. `get_download_progress() -> str` — 回傳 `{"status": "downloading"|"verifying"|"ready"|"error", "progress": 0-100, "error": "..."}`
3. `install_update() -> str` — 驗證 + 安裝 + 重啟，回傳 `{"status": "installing"}`（實際上 call 完就重啟了）

**Thread safety:** Download 在 `threading.Thread` 中跑，progress 用 `threading.Lock` 保護 shared state。

### Task 4: Frontend — Toast 下載進度 + 安裝按鈕

**Modify:** `frontend/src/App.tsx`, `frontend/src/components/Toast.tsx`

**Download flow (App.tsx):**
```
點「前往下載」
  → api.downloadUpdate()
  → 每 500ms poll api.getDownloadProgress()
  → Toast 顯示進度條 + 百分比
  → download complete → Toast 變為「已下載」+「安裝並重啟」按鈕
  → 點「安裝並重啟」→ api.installUpdate()
```

**Toast 進度條**：擴充 Toast 支援 optional `progress?: number`（0-100），渲染簡單進度條。

### Task 5: Frontend — Settings「更新」按鈕

**Modify:** `frontend/src/components/SettingsModal.tsx`

當 `checkResult.latest` 有值（新版本可用）時，在版本資訊旁顯示「下載並安裝」按鈕。行為與 Task 4 相同（觸發 download → progress → install flow）。

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

---

## Dependency Order

```
Task 1 (update_manager download) ──┐
                                   ├──→ Task 3 (api.py bridge) ──→ Task 4 (Toast UI) ──┐
Task 2 (update_manager install) ──┘                                                       ├──→ 整合測試
Task 6 (i18n) ───────────────────────────────────────────────────→ Task 5 (Settings UI) ──┘
```

建議順序：Task 1 → Task 2 → Task 3 → Task 6 → Task 4 + Task 5（可並行）

---

## Files Changed Summary

| File | Action | Tasks |
|------|--------|-------|
| `src/update_manager.py` | Create (~150 lines) | Task 1, 2 |
| `src/api.py` | Modify (~60 lines) | Task 3 |
| `frontend/src/App.tsx` | Modify (~40 lines) | Task 4 |
| `frontend/src/components/Toast.tsx` | Modify (~20 lines) | Task 4 |
| `frontend/src/components/SettingsModal.tsx` | Modify (~25 lines) | Task 5 |
| `src/resources/translations/en-US.json` | Modify (+6 keys) | Task 6 |
| `src/resources/translations/zh-TW.json` | Modify (+6 keys) | Task 6 |
| `tests/test_update_manager.py` | Create (~80 lines) | Task 1, 2 |

預估總變更量：~380 lines

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
