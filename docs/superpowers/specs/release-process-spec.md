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

## Related

- Build matrix / packaging constraints: [build-packaging-spec.md](build-packaging-spec.md)
- Workflow: `.github/workflows/release.yml`
- 實例：v0.1.2 = PR #205, merge commit `33527a4`, assets 四項齊全
