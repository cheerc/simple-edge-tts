# Contributing to simple-edge-tts

感謝你考慮貢獻這個專案！Thank you for considering contributing to this project!

## Code of Conduct

請先閱讀我們的 [Code of Conduct](CODE_OF_CONDUCT.md)。所有參與者都需遵守。

## How to Contribute

### 回報 Bug / Report a Bug

開一個 [GitHub Issue](https://github.com/cheerc/simple-edge-tts/issues/new)，包含：
- 你的作業系統和版本
- 復現步驟
- 預期行為 vs 實際行為

### 建議功能 / Suggest a Feature

開一個 [GitHub Issue](https://github.com/cheerc/simple-edge-tts/issues/new)，說明：
- 你想解決的問題
- 你期望的行為

### 提交 PR / Submit a Pull Request

1. Fork 這個 repo
2. 建立 feature branch: `git checkout -b feat/your-feature`
3. 寫測試先（TDD）
4. 確認通過: `./workflow.sh t6`
5. 開 PR 到 `main`，body 加上 `Closes #N`
6. 填寫 PR template

### 開發環境 / Development Setup

請參考 [README 的 Development 段落](README.md#開發-development)

### 程式碼風格 / Code Style

- 由 `ruff` 自動檢查（CI 會執行）
- Commit messages 使用 [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `chore:`, `docs:`

## 謝謝！Thank you!
