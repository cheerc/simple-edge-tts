# Release Process Spec

## Overview

本檔是 simple-edge-tts 發佈新版本的單一 source of truth：從 version bump 到 GitHub Release 驗證的完整操作步驟。描述現狀；build 產物與 workflow 結構見 [build-packaging-spec.md](build-packaging-spec.md)。

以 release v0.1.2（PR #205 → merge commit `33527a4`）為最新實例。

## 前置檢查

發 PR 前在本地跑：

```bash
./deploy.sh verify     # macOS build + launch + log gate（僅 macOS 支援）
./workflow.sh t1       # lint (ruff)
```

- `t2` typecheck（mypy）目前**不是** CI gate，可選擇性跑 `./workflow.sh t2`。
- CI 的完整 gate 見 `.github/workflows/ci.yml`（Lint & Test job：`ruff check`、pytest、workflow YAML 驗證、frontend build/lint/test）。
- **修改打包內容時（add-data / hidden-import / icon / version-file 等），`deploy.sh` 與 `release.yml` 兩處的 PyInstaller 參數必須同步修改**——兩者各自維護一份清單，不同步會導致本地 build 與 CI release build 行為分歧。對齊契約細節見 build-packaging-spec.md 的 Key Constraints。

## Version Bump

- `pyproject.toml` 的 `[project] version` 是唯一版本來源——`release.yml` 從此抽取（Ref #90），Windows 版本資源與 macOS Info.plist 都由此注入。
- 只改這一行，commit message 慣例：`chore: bump version to vX.Y.Z`。
- **CHANGELOG 不維護**：release notes 由 GitHub `generate_release_notes` 自動產生。
- `uv.lock` 不隨 bump 更新（CI 用 `uv sync --all-extras` 安裝，不受 lock 內版本欄位影響）。
- 注意：測試不得硬編碼版本字串——fallback 測試動態解析 pyproject.toml（tests/test_api.py::test_get_app_version_fallback_to_pyproject_toml）。

## PR

- Branch 開到 `main`，PR title 沿用 bump commit message。
- CI（Lint & Test）必須綠。
- Single review 通過後 squash merge。

## Tag + Release

Merge 後在 merge commit 上建 `vX.Y.Z` tag 觸發 `.github/workflows/release.yml`（trigger：push tags `v*`）。兩種等價方式：

```bash
# 方式一：直接 push tag
git tag vX.Y.Z <merge-sha>
git push origin vX.Y.Z

# 方式二：gh release create（無法直接 push 的環境適用）
gh release create vX.Y.Z \
  --target <merge-sha> \
  --generate-notes \
  --title "Release vX.Y.Z" \
  --notes "⚠️ **macOS 使用者**：首次開啟若遇到「已損毀」或「無法驗證開發者」提示，請參考 README 的「首次執行安全說明」。"
```

兩者都會觸發同一個 release.yml；方式二會先建 release 再由 workflow 補上 assets。

## 驗證

```bash
gh run list --workflow=release.yml --limit 1    # 確認 success
gh release view vX.Y.Z                           # 確認 assets 齊全
```

Release assets 應包含四項：

| Asset | 來源 |
|-------|------|
| `simple-edge-tts.dmg` | macOS `--onedir` build |
| `simple-edge-tts-macos.zip` | macOS `.app` 直接下載版 |
| `simple-edge-tts-windows.zip` | Windows `--onefile` exe |
| `SHA256SUMS.txt` | 全部 dmg/zip 的 checksum |

Notes body 應含 macOS Gatekeeper 提示（release.yml 固定附加）+ What's Changed 自動清單。

## Release 後驗證 Checklist

CI 綠與 assets 齊全**不代表** frozen build 功能正常——打包差異只有實際下載、驗證、安裝 CI build 才會暴露。Release 後依序逐項驗證：

### 發佈產物驗證

- [ ] **Release metadata 正確**：`gh release view vX.Y.Z` 顯示 tag 指向本次 merge commit、非 draft / 非 prerelease，notes body 含 What's Changed 自動清單與 macOS Gatekeeper 提示（release.yml 固定附加）。
- [ ] **assets 四項齊全**：dmg / macos.zip / windows.zip / SHA256SUMS.txt（同一 `gh release view` 輸出核對）。
- [ ] **實際下載 dmg/zip assets**：`gh release download vX.Y.Z` 把三個安裝檔抓回本地——只看 assets 列表不算通過；檔案必須存在且大小 > 0。
- [ ] **checksum 驗證**：在下載目錄跑 `shasum -a 256 -c SHA256SUMS.txt`（Linux：`sha256sum -c SHA256SUMS.txt`），全部安裝檔必須 `OK`；任何 mismatch 代表上傳損毀或 assets 不成套。

### 安裝後驗證（install/restart）

安裝該版 build（dmg 拖入 Applications 或解壓 macOS zip / Windows zip）並啟動一次：

- [ ] **版本號正確**：footer 與 Settings → About 顯示 `vX.Y.Z` 且與 pyproject.toml 一致（frozen 版本解析鏈：importlib.metadata → bundled pyproject.toml）
- [ ] **檢查更新可連線**：Settings 的「檢查更新」能成功回應（找到新版或「已是最新版本」），不得出現「更新檢查失敗」（frozen 下 SSL CA 解析依賴 certifi bundle）

為何需要：v0.1.2 實測中，footer 顯示 `0.0.0`（release.yml 缺 bundle pyproject.toml，Ref #215）且「檢查更新」恆失敗（frozen SSL CA 找不到系統根憑證，Ref #216），兩者 CI 都綠、assets 也齊全——只有裝起來用才發現。

## Related

- Build matrix / packaging constraints: [build-packaging-spec.md](build-packaging-spec.md)
- Workflow: `.github/workflows/release.yml`
- 實例：v0.1.2 = PR #205, merge commit `33527a4`, assets 四項齊全
