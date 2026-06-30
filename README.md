# simple-edge-tts

[![CI](https://github.com/cheerc/simple-edge-tts/actions/workflows/ci.yml/badge.svg)](https://github.com/cheerc/simple-edge-tts/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](CODE_OF_CONDUCT.md)

跨平台桌面文字轉語音工具 — Cross-platform desktop text-to-speech app

使用 Microsoft Edge TTS API，選擇聲音、輸入文字、即時預聽、匯出 MP3。

<!-- TODO: add screenshot -->

## 下載 Download

👉 [最新版本 Latest Release](https://github.com/cheerc/simple-edge-tts/releases/latest)

| 平台 | 檔案 | 說明 |
|---|---|---|
| Windows | `simple-edge-tts.zip` | 下載後解壓縮執行，免安裝 |
| macOS | `simple-edge-tts.dmg` | 打開 DMG，拖到 Applications |

## ⚠️ 首次開啟說明

simple-edge-tts 是開放原始碼的免費軟體。由於**沒有購買 Apple 付費開發者簽章**，作業系統會在首次開啟時顯示安全性提示。請依照以下步驟操作。

---

### 🖥️ macOS

**為什麼會看到提示？**

macOS Gatekeeper 會檢查應用程式是否有 Apple 認證的開發者簽章。因為我們沒有購買 Apple Developer Program（年費 US$99），系統會顯示「無法驗證開發者」或「已損毀」。

> 💡 **這個提示不代表程式有問題**——它只表示 Apple 無法辨識開發者身分。程式碼完全[開放](https://github.com/cheerc/simple-edge-tts)，任何人都可以檢查。

**方法一：右鍵開啟（最簡單）**

1. 開啟 **Finder**，找到 `simple-edge-tts` app
2. 對著 app 圖示按 **右鍵**（或按住 `Control` 鍵點擊）
3. 在選單中選擇「**開啟**」
4. 跳出對話框時，再按一次「**開啟**」

> ✅ 只要做一次就好，之後可以直接雙擊開啟。

**方法二：使用終端機（若方法一無效）**

1. 打開 **終端機 (Terminal)**：在「啟動台 (Launchpad)」→「其他」檔案夾 →「Terminal」
2. 複製以下指令、貼上、按 `Enter`：
   ```
   xattr -cr /Applications/simple-edge-tts.app
   ```
3. 關閉終端機，再次雙擊開啟 app

> ⚠️ 如果你把 app 放在其他位置（不是 `/Applications`），請把路徑換成你存放的位置。

---

### 🪟 Windows

**為什麼會看到提示？**

Windows SmartScreen 會對不常見的下載檔案顯示警告。

**操作步驟：**

1. 看到「Windows 已保護您的電腦」時，點擊「**其他資訊**」
2. 確認發行者顯示為「未知的發行者」
3. 點擊「**仍要執行**」

> ✅ 只要做一次就好，之後可以直接執行。

## 使用方式

1. **選擇聲音** — 左側面板選擇語言和語音（預設台灣中文）
2. **輸入文字** — 右側面板輸入要轉換的文字
3. **調整語速** — 拖動速度滑桿（0.5× – 2.0×）
4. **預聽或匯出** — 點擊「試聽」預聽，或「匯出 MP3」儲存檔案
5. **設定** — 點擊右上角齒輪圖示，切換介面語言

## 功能 Features

- 🎙️ 300+ 聲音（Microsoft Edge TTS）
- 🇹🇼 繁體中文 & English 介面即時切換
- 🎚️ 語速調整（0.5× – 2.0×）
- 🎵 音調 (Pitch) 調整（-50 ~ +50 Hz）
- 🌗 深色 / 淺色主題（跟隨系統 / 手動切換）
- 🔄 自動檢查更新
- 💾 匯出 MP3
- 📢 系統匣圖示（最小化到系統匣）
- 🖥️ macOS + Windows

## 系統需求

- Windows 10+ 或 macOS 12+
- Python 3.11+（從原始碼執行時）
- Node.js 20+（從原始碼執行時）
- 網路連線（TTS API 需要連線）

## 隱私與資料流 / Privacy & Data Flow

- **資料傳輸**：本程式會將使用者輸入的文字，透過 HTTPS 傳送至 **Microsoft Edge 線上文字轉語音 (TTS) 服務 API** 進行語音合成。
- **Data Transmission**: This application transmits the text entered by the user via HTTPS to the **Microsoft Edge online text-to-speech (TTS) service API** for synthesis.
- **用途**：僅用於產生對應的語音音訊。
- **Purpose**: Strictly for generating the corresponding speech audio.
- **隱私聲明**：本程式為無伺服器/無帳號設計，不包含任何遙測 (Telemetry) 或日誌收集，亦不保存使用者輸入的文字。然而，您的文字在處理時會離開本機並送至 Microsoft 的伺服器。
- **Privacy Notice**: This app is serverless and account-free, containing no telemetry or log collection, and does not save the text you enter. However, your text will leave your local machine and be sent to Microsoft servers during synthesis.

---

## 開發 Development

### 環境設定

```bash
git clone https://github.com/cheerc/simple-edge-tts.git
cd simple-edge-tts

# Backend (Python)
uv sync --all-extras

# Frontend (React)
cd frontend && npm ci && npm run build
cd ..
```

> **Note**: After making changes to the frontend, rebuild the production bundle with `cd frontend && npm run build`. The output in `frontend/dist/` is gitignored and must be rebuilt locally for production mode.

### 測試

```bash
# Python tests
uv run pytest tests/ -v

# Python lint
uv run ruff check src/ tests/

# Frontend lint
cd frontend && npm run lint
```

### 本地執行

```bash
# Production mode (uses built frontend)
uv run simple-edge-tts

# Development mode (uses Vite dev server)
SIMPLE_EDGE_TTS_DEV=1 uv run simple-edge-tts
# In a separate terminal:
cd frontend && npm run dev
```

## 技術架構

- **Frontend**: React + Vite + Tailwind CSS v4 + shadcn/ui
- **Backend**: Python + PyWebView (IPC via `window.pywebview.api`)
- **TTS**: Microsoft Edge TTS API (`edge-tts`)
- **System Tray**: pystray
- **CI**: GitHub Actions (Python lint + test + frontend build + lint)

## License

MIT
