# #170 + #171 + #172: Auto-Update UI — Settings + Toast + Design Doc Plan

> **For agentic workers:** Use `impl-task-loop` skill.
>
> **Issue refs:**
> - [#170](https://github.com/cheerc/simple-edge-tts/issues/170) Settings 加入自動更新偏好設定
> - [#171](https://github.com/cheerc/simple-edge-tts/issues/171) 更新通知 Toast 加入「前往下載」和「略過此版本」按鈕
> - [#172](https://github.com/cheerc/simple-edge-tts/issues/172) App 自動更新下載/安裝流程設計（design-only）

**Goal:** 補完 auto-update 的完整 UI 層——從偵測 → 通知 → 使用者行動（下載/略過）→ 偏好管理（開關/手動檢查/略過版本），加上一份未來自我更新機制的設計文件。三個 issue 一起做以確保 UI consistency 和互動流程的連貫性。

**Architecture:** 現有 `update_checker.py`（後端）和 `api.check_update()`（IPC bridge）已完整。變更集中在 React frontend（SettingsModal、Toast、App.tsx）和 Python config（DEFAULTS 補 key）。

**Tech Stack:** React 19 + TypeScript + inline styles (CSS variables) + Lucide icons; Python 3.11+ (config defaults only)

**Risk-Flags:** 無破壞性變更；純 UI 增量 + config key 新增 + design doc

---

## Scope & Expected Outcomes

### In Scope

| Area | Deliverable |
|---|---|
| **Settings — 自動檢查開關** | Toggle `auto_check_update`（預設 true），關閉後 App mount 跳過 `checkUpdate()` |
| **Settings — 手動檢查按鈕** | "Check for Updates" 按鈕，點擊觸發 `checkUpdate()`，結果以 toast 呈現（有更新 / 已是最新 / 網路錯誤） |
| **Settings — 略過版本管理** | 若 `skip_version` 有值，顯示略過的版本號 +「清除略過」按鈕 |
| **Toast — 可點擊按鈕** | Toast 擴充支援 optional `actions` prop（`{label, onClick}[]`），不破壞現有純文字 toast |
| **App.tsx — 更新 toast 按鈕** | 更新通知 toast 加入「前往下載」（`window.open`）和「略過此版本」（`setConfig("skip_version", version)`） |
| **Config — 預設值補入** | `config_manager.py` DEFAULTS 加入 `auto_check_update: true`、`skip_version: null` |
| **Design doc** | `docs/design/auto-update.md` — 未來自我更新機制的完整設計（策略、平台差異、下載/驗證/替換/重啟 flow） |
| **i18n** | 新增 key：`update_checking`、`update_check_now`、`update_up_to_date`、`update_auto_check`、`update_auto_check_desc`、`update_skipped_version`、`update_clear_skip`（en-US + zh-TW） |

### Out of Scope

- 自動下載/安裝 binary（#172 design-only，不實作）
- 背景定時檢查（目前僅 mount 時檢查一次）
- Linux 平台的自動更新
- Code signing / notarization

### Expected Outcomes

1. 使用者在 Settings 可控制是否自動檢查更新
2. 使用者在 Settings 可手動觸發檢查，即時看到結果
3. 有新版本時 toast 顯示兩個可點擊按鈕（下載 / 略過）
4. 略過的版本會被持久化，下次啟動不再提示
5. 一份可供未來實作參考的 auto-update 設計文件

---

## Global Constraints

- **不改變現有 CSS variable 系統**：沿用 `var(--primary)`、`var(--color-surface)`、`var(--border)` 等 token
- **不改變 SettingsModal 現有結構**：在 Language / File Logging / About 三個 section 之間插入「更新」section
- **Toast 向後相容**：`actions` prop 為 optional，現有純文字 toast 不受影響
- **不引入新 npm dependency**：Lucide icons 已存在、只用既有 icon
- **i18n key 必須 en-US + zh-TW 雙語完整**

---

## UI Design Rationale（ui-ux-pro-max 原則）

### Style Consistency (§4)
- 新 UI 元素完全遵循 SettingsModal 既有的 section pattern：`h3` 標題（16px / 600 weight）→ 控制項 → 描述文字（12px / secondary color）
- Toggle switch 複用現有 File Logging toggle 的實作（44×24px pill + 18px circle）
- 按鈕樣式沿用 modal 內既有 button pattern

### Interaction (§2, §7)
- **手動檢查按鈕**：點擊後顯示 loading 狀態（disabled + 文字變「檢查中...」），避免重複點擊
- **Toast actions**：按鈕 minimum 44px height、8px spacing between actions
- **Toast enter/exit**：沿用現有 `animate-toast-in` animation（約 300ms），不改變 timing

### Progressive Disclosure (§8)
- Settings「更新」section 預設只顯示 toggle + 檢查按鈕
- 僅在 `skip_version` 有值時才顯示「略過的版本」行（避免空白 clutter）
- 手動檢查結果直接顯示在按鈕下方（inline），而非額外 popup

### Accessibility (§1)
- Toggle 使用 `role="switch"` + `aria-checked`（與現有 File Logging toggle 一致）
- Icon-only 按鈕（清除略過）加入 `aria-label`
- Toast 使用 `aria-live="polite"`（若現有未加則補上）

---

## Task Breakdown

### Task 1: Config DEFAULTS 補入 auto-update keys（Python）

**Files:**
- Modify: `src/config_manager.py`

**Changes:**

```python
# DEFAULTS dict 新增兩 key
DEFAULTS = {
    ...
    "auto_check_update": True,    # 新增
    "skip_version": None,          # 新增
}
```

無需 migration 邏輯——#167 的 config version migration 會處理舊使用者自動補入。

**Verification:**
- `uv run python -c "from src.config_manager import ConfigManager; c = ConfigManager(); assert c.get('auto_check_update') is True; assert c.get('skip_version') is None"`

**Complexity:** trivial

---

### Task 2: Toast 擴充 action buttons（React）

**Files:**
- Modify: `frontend/src/components/Toast.tsx`

**Current state:** Toast 接收 `{toasts, onRemove}`，每個 toast 是 `{id, message, type}`。

**Changes:**

1. **擴充 `ToastMessage` type**（在 `useToast.ts` 或 `Toast.tsx`）：
   ```typescript
   interface ToastAction {
     label: string;
     onClick: () => void;
   }
   
   interface ToastMessage {
     id: number;
     message: string;
     type: "success" | "error" | "info";
     actions?: ToastAction[];  // 新增 optional
   }
   ```

2. **Toast component 渲染 actions**：
   - 若 `toast.actions` 存在，在 message 下方渲染一排按鈕
   - 按鈕樣式：
     - Primary action（第一個）：`var(--primary)` background + white text
     - Secondary action（第二個）：transparent + `var(--color-text-secondary)` + border
   - 按鈕高度 ≥36px、padding 8-16px、font-size 13px
   - 每個按鈕 `onClick` 執行後自動 dismiss toast

3. **Accessibility**：Toast container 加 `role="status" aria-live="polite"`

**Verification:**
- 現有純文字 toast（success/error/info）行為不變
- 新帶 `actions` 的 toast 正確渲染按鈕且可點擊
- 點擊任一 action 後 toast dismiss

**Complexity:** simple

---

### Task 3: Settings 加入「更新」section（React）

**Files:**
- Modify: `frontend/src/components/SettingsModal.tsx`

**Design spec:**

在「File Logging」section 與「About」section 之間插入「更新」section：

```
┌─ Settings ─────────────────────────┐
│ Language          [English ▾]      │
│                                    │
│ File Logging      [toggle]         │
│   description text                  │
│                                    │
│ 🆕 Updates                         │  ← h3: {t("update_section_title")}
│                                    │
│ Auto-check        [toggle]         │  ← role="switch", aria-checked
│   description text                  │
│                                    │
│ [🔄 Check for Updates]             │  ← button, loading state
│   ↳ "已是最新版本" or "發現新版本"      │  ← inline result text
│                                    │
│ Skipped: v0.1.0  [✕ Clear]        │  ← 僅 skip_version 有值時顯示
│                                    │
│ About                              │
│   Simple Edge TTS                  │
│   description                       │
└────────────────────────────────────┘
```

**State variables (new):**
```typescript
const [autoCheck, setAutoCheck] = useState(true);
const [checking, setChecking] = useState(false);
const [checkResult, setCheckResult] = useState<{latest?: string; upToDate?: boolean} | null>(null);
const [skippedVersion, setSkippedVersion] = useState<string | null>(null);
```

**Behaviors:**

1. **Mount 時讀取 config**：
   - `api.getConfig("auto_check_update")` → set `autoCheck`
   - `api.getConfig("skip_version")` → set `skippedVersion`

2. **Toggle auto-check**：
   - `onClick` → toggle `autoCheck` state → `api.setConfig("auto_check_update", newValue)`
   - 無需 restart（立即生效，下次 mount 時 `App.tsx` 讀 config 決定是否跳過 `checkUpdate()`）

3. **Check for Updates 按鈕**：
   - 點擊 → `setChecking(true)` → `api.checkUpdate()`
   - 有更新 → `setCheckResult({latest: update.latest})` → 顯示「新版本 {latest} 可用！」
   - 無更新 → `setCheckResult({upToDate: true})` → 顯示「已是最新版本」
   - 錯誤 → `setCheckResult(null)` + toast error
   - Always → `setChecking(false)`
   - 按鈕 disabled 時顯示「檢查中...」

4. **Skipped version 行**：
   - 僅 `skippedVersion` 非 null 時渲染
   - 顯示文字：「已略過：v{version}」
   - 「清除略過」按鈕（X icon）→ `api.setConfig("skip_version", null)` → `setSkippedVersion(null)`

**Icon 選擇（Lucide，已安裝）：**
- Check for Updates：`RefreshCw`（旋轉動畫表示 checking）
- Clear skip：`X`（同 modal close button）

**Verification:**
- Toggle 開關可正常切換，config 持久化
- 手動檢查按鈕：loading state → 結果顯示正確
- 有略過版本時顯示該行，清除後消失
- 無略過版本時該行不渲染

**Complexity:** simple

---

### Task 4: App.tsx 更新檢查整合（React）

**Files:**
- Modify: `frontend/src/App.tsx`

**Changes:**

1. **讀取 `auto_check_update` config**：
   - Mount 時先讀 `api.getConfig("auto_check_update")`
   - 僅在 value !== false 時才執行 `checkUpdate()`
   - 若 key 不存在（舊 config）→ 預設 true，執行檢查

2. **更新 toast 加入 actions**：
   - 將 `addToast(...)` 改為帶 `actions` 的版本：
   ```typescript
   addToast(
     t("update_available").replace("{version}", update.latest),
     "info",
     [
       {
         label: t("update_download"),
         onClick: () => window.open(update.url, "_blank"),
       },
       {
         label: t("update_skip"),
         onClick: async () => {
           await api.setConfig("skip_version", update.latest);
         },
       },
     ]
   );
   ```

3. **`addToast` signature 擴充**（若需要）：
   - `useToast.ts` 的 `addToast` 需支援 optional `actions` 參數

**Verification:**
- `auto_check_update: false` 時 mount 不呼叫 `checkUpdate()`
- `auto_check_update: true`（或未設定）時行為與現在相同
- 更新 toast 顯示兩個按鈕，點擊「前往下載」開瀏覽器、點擊「略過」寫入 config

**Complexity:** simple

---

### Task 5: i18n 補入新 translation key

**Files:**
- Modify: `src/resources/translations/en-US.json`
- Modify: `src/resources/translations/zh-TW.json`

**New keys:**

| Key | en-US | zh-TW |
|-----|-------|-------|
| `update_section_title` | "Updates" | "更新" |
| `update_auto_check` | "Automatically check for updates" | "自動檢查更新" |
| `update_auto_check_desc` | "Check for new versions when the app starts" | "啟動應用程式時自動檢查新版本" |
| `update_check_now` | "Check for Updates" | "檢查更新" |
| `update_checking` | "Checking..." | "檢查中..." |
| `update_up_to_date` | "You're up to date!" | "已是最新版本！" |
| `update_new_version` | "Version {version} available!" | "新版本 {version} 可用！" |
| `update_skipped_version` | "Skipped: v{version}" | "已略過：v{version}" |
| `update_clear_skip` | "Clear" | "清除略過" |
| `update_error` | "Update check failed" | "更新檢查失敗" |

**Complexity:** trivial

---

### Task 6: Design doc — 未來自我更新機制（docs only）

**Files:**
- Create: `docs/design/auto-update.md`

**Document structure:**

```
# Auto-Update Design — simple-edge-tts

## 1. Current State（現況）
- detect-only via GitHub Releases API
- toast notification, no download/install

## 2. Strategy Options（策略選擇）
- A. 純通知（現況）
- B. 背景下載 + 通知安裝
- C. 全自動 silent update
- Recommendation: B first, C later (needs code signing)

## 3. Platform Matrix（平台差異）
| Concern | macOS | Windows |
|---|---|---|
| Binary format | .dmg (drag-to-install) | .zip → .exe |
| Self-replace | .app bundle can be swapped | .exe needs helper script |
| Restart mechanism | NSWorkspace / open -n | batch script + taskkill |
| Signing | Apple notarization | EV code signing |

## 4. Download & Verify Flow
- GitHub Releases API → get asset URL
- Download to temp dir with progress
- SHA256 verification against SHA256SUMS.txt

## 5. Install & Restart Flow
- macOS: swap .app bundle → relaunch via open
- Windows: write .bat → exit → replace .exe → relaunch

## 6. User Experience
- Download progress in system tray or toast
- "Install & Restart" button
- Rollback on failure

## 7. Out of Scope / Future
- Linux support
- Delta updates
- App Store distribution
```

**Complexity:** N/A（design only，不實作）

---

## Dependency Order

```
Task 1 (config DEFAULTS)  ──┐
                             ├──→ Task 3 (Settings UI) ──┐
Task 5 (i18n keys) ─────────┘                            │
                                                          ├──→ 整合測試
Task 2 (Toast actions) ──────┐                            │
                             ├──→ Task 4 (App.tsx) ──────┘
Task 5 (i18n keys) ─────────┘

Task 6 (design doc) — 獨立，無依賴
```

建議實作順序：Task 1 → Task 5 → Task 2 + Task 3（可並行）→ Task 4 → Task 6

---

## Verification Checklist（dual-review 前）

### Backend
- [ ] `config_manager.py` DEFAULTS 含 `auto_check_update` + `skip_version`
- [ ] `uv run pytest tests/ -v` 全 pass
- [ ] `ruff check src/` 無新增警告

### Frontend
- [ ] `npm run build`（在 frontend/）成功
- [ ] `npx tsc --noEmit` 無型別錯誤
- [ ] Toast 向後相容：現有純文字 toast 行為不變
- [ ] Settings 新 section 在 light + dark theme 下顯示正確
- [ ] Toggle 開關正常運作、config 持久化
- [ ] 手動檢查按鈕：loading → 有更新 / 已最新 / 錯誤三態正確
- [ ] 略過版本行僅在 `skip_version` 有值時顯示、清除功能正常

### Integration
- [ ] `auto_check_update: false` 時 App mount 不呼叫 `checkUpdate()`
- [ ] 更新 toast 顯示兩個按鈕、點擊行為正確
- [ ] 略過版本後重啟 App 不再提示同一版本

### Design Doc
- [ ] `docs/design/auto-update.md` 內容完整、涵蓋所有設計問題

---

## Files Changed Summary

| File | Action | Tasks |
|------|--------|-------|
| `src/config_manager.py` | Modify (2 lines) | Task 1 |
| `frontend/src/components/Toast.tsx` | Modify (~30 lines) | Task 2 |
| `frontend/src/hooks/useToast.ts` | Modify (~10 lines) | Task 2 |
| `frontend/src/components/SettingsModal.tsx` | Modify (~80 lines) | Task 3 |
| `frontend/src/App.tsx` | Modify (~20 lines) | Task 4 |
| `src/resources/translations/en-US.json` | Modify (~10 lines) | Task 5 |
| `src/resources/translations/zh-TW.json` | Modify (~10 lines) | Task 5 |
| `docs/design/auto-update.md` | Create (~150 lines) | Task 6 |

預估總變更量：~300 lines（不含 design doc）。

---

## Estimated Complexity

| Task | Complexity |
|------|-----------|
| Task 1: Config DEFAULTS | trivial |
| Task 2: Toast actions | simple |
| Task 3: Settings UI | simple |
| Task 4: App.tsx integration | simple |
| Task 5: i18n keys | trivial |
| Task 6: Design doc | N/A |
| **Overall** | **simple**（多檔案但每檔案變更小、無新邏輯） |
