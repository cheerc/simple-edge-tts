# Auto-Update UI (#170, #171, #172): 驗證清單

> Generated: 2026-06-29
> PR: [#173](https://github.com/cheerc/simple-edge-tts/pull/173)
> HEAD: `1b05dbb044e142654ec36ae2968f43027859e269`
> Plan: `docs/plan/auto-update-ui-170-171-172.md`

## How to test

```bash
cd /Users/cheerc/Projects/simple-edge-tts
open dist/simple-edge-tts.app
```

在 macOS `.app` 中手動操作驗證。**不要用 `uv run`**（打包後行為才等於 release）。

---

## §1: Settings — 更新 section 顯示

### 驗證步驟
1. 啟動 app
2. 點右上角齒輪圖示開啟 Settings
3. 捲動查看 File Logging 與 About 之間是否出現「更新」section

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | Settings modal 中 Language → File Logging → **更新** → About，四個 section 依序排列 | |
| 2 | 「更新」section 顯示 toggle「自動檢查更新」（預設 ON） | |
| 3 | Toggle 下方有「檢查更新」按鈕 | |
| 4 | 無略過版本時，不顯示「已略過」行 | |

---

## §2: Settings — Toggle 自動檢查開關

### 驗證步驟
1. 在 Settings 中將「自動檢查更新」toggle 關閉（OFF）
2. 關閉 Settings
3. 關閉 app（Cmd+Q）
4. 重新啟動 app → 開啟 Settings 確認 toggle 狀態

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | Toggle 從 ON 切到 OFF 即時生效（不需重啟） | |
| 2 | 重啟 app 後，toggle 保持 OFF（config 持久化） | |
| 3 | 重啟後不顯示更新通知 toast（因自動檢查已關） | |
| 4 | 將 toggle 切回 ON → 重啟 → 恢復自動檢查 | |

---

## §3: Settings — 手動檢查更新

### 驗證步驟
1. 開啟 Settings → 更新 section
2. 點擊「檢查更新」按鈕
3. 觀察按鈕狀態變化與結果顯示

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | 點擊後按鈕顯示「檢查中...」（loading state），按鈕 disabled | |
| 2 | 連網正常時：顯示「已是最新版本！」或「新版本 X.Y.Z 可用！」 | |
| 3 | 斷網測試：斷開網路 → 點擊 → 顯示紅色錯誤訊息「更新檢查失敗」 | |
| 4 | Loading 結束後按鈕恢復可點擊 | |

---

## §4: Settings — 略過版本管理

### 驗證步驟
1. 如果當前有更新（`skip_version` 有值），Settings 中應顯示「已略過：v{X.Y.Z}」+「清除略過」按鈕
2. 點擊「清除略過」
3. 觀察該行消失

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | `skip_version` 有值時顯示「已略過：v{X}」+ 清除按鈕 | |
| 2 | 點擊「清除略過」後該行消失 | |
| 3 | 清除後重啟 app，若有新版本則再次顯示更新 toast | |

---

## §5: Toast — 純文字向後相容

### 驗證步驟
1. 觸發一般 toast（例如：輸入文字 → 點「匯出 MP3」）
2. 觀察 toast 外觀與行為

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | 一般 toast（success/error/info）外觀與之前完全一致 | |
| 2 | Toast 約 4 秒後自動消失 | |
| 3 | 點擊 toast 可手動關閉 | |
| 4 | 無多餘的按鈕或空白區域 | |

---

## §6: Toast — 更新通知 action buttons

### 驗證步驟
> ⚠️ 需要有一個比 `0.1.0` 更新的 GitHub Release 才會觸發更新 toast。若無，可暫時修改 `pyproject.toml` 版本為 `0.0.1`、rebuild、重測（測完記得改回 `0.1.0`）。

1. 確保「自動檢查更新」toggle 為 ON
2. 重啟 app
3. 觀察更新通知 toast

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | Toast 顯示「新版本 X.Y.Z 可用！」+ 兩個按鈕 | |
| 2 | 第一個按鈕：「前往下載」（primary style，藍底白字） | |
| 3 | 第二個按鈕：「略過」（secondary style，透明＋邊框） | |
| 4 | 點擊「前往下載」→ 在瀏覽器開啟 GitHub Release 頁面 → toast 關閉 | |
| 5 | 點擊「略過」→ toast 關閉 → `skip_version` 寫入 config | |
| 6 | Action toast **不會**在 4 秒內消失（應有較長顯示時間，約 15 秒） | |
| 7 | 點擊 toast 內的按鈕**不會**觸發 toast 本身 dismiss（stopPropagation 生效） | |

---

## §7: 語言切換

### 驗證步驟
1. Settings → Language 切換為 English
2. 觀察更新 section 文字變化
3. 切回 繁體中文

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | English: section 標題為 "Updates"、toggle 為 "Automatically check for updates"、按鈕為 "Check for Updates" | |
| 2 | 繁體中文: section 標題為「更新」、toggle 為「自動檢查更新」、按鈕為「檢查更新」 | |
| 3 | Toast 按鈕文字也跟隨語言切換（"Download"/"Skip" ↔「前往下載」/「略過」） | |

---

## §8: 深色/淺色主題

### 驗證步驟
1. 切換深色/淺色主題
2. 觀察 Settings 更新 section 與 toast 的外觀

### 預期行為
| # | 測試項目 | Pass? |
|---|---------|-------|
| 1 | 深色主題：section 文字、toggle、按鈕可讀、對比足夠 | |
| 2 | 淺色主題：同上、無顏色異常 | |
| 3 | Toast 在兩種主題下都可讀、按鈕顏色正確 | |

---

## Summary

| Section | 測試項目數 |
|---------|----------|
| §1 Settings 顯示 | 4 |
| §2 Toggle 開關 | 4 |
| §3 手動檢查更新 | 4 |
| §4 略過版本管理 | 3 |
| §5 Toast 向後相容 | 4 |
| §6 Toast action buttons | 7 |
| §7 語言切換 | 3 |
| §8 深色/淺色主題 | 3 |
| **合計** | **32** |
