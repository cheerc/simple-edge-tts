# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proactive Context Loading

Read these files **without being asked** when the task involves:

| Task involves | Read proactively |
|---------------|-----------------|
| Release, version bump, git tag, GitHub Release | `docs/superpowers/specs/release-process-spec.md` |
| Backend modules, frozen paths, IPC bridge | `src/CLAUDE.md` |
| Auto-update detection/download/install flow | `docs/design/auto-update.md` (design-only; current implementation may differ) |

## Project Overview

Simple Edge TTS — cross-platform Edge TTS desktop app (pywebview GUI), v0.1.2 (SSOT: `pyproject.toml` `version`).

**Communication**: 繁體中文 (Traditional Chinese)
**Code**: English (comments, commit messages, docs)

## Repository & Stack

- GitHub repository: `cheerc/simple-edge-tts`; default branch: `main`
- Backend: Python 3.11 + edge-tts + pywebview + pystray; dependencies managed by uv
- Frontend: React + TypeScript + Tailwind CSS v4 + Vite (`frontend/`)

## Commands

```bash
./workflow.sh t1        # lint (ruff)
./workflow.sh t2        # typecheck (mypy) — NOT a CI gate
./workflow.sh t3        # test (pytest)
./workflow.sh t4        # frontend build
./workflow.sh t5        # coverage
./workflow.sh           # all of the above

./deploy.sh build       # full macOS build (.app + .dmg)
./deploy.sh verify      # macOS build + launch + log gate (macOS only)
./deploy.sh build-exe   # trigger CI Windows build, download artifact
./deploy.sh clean       # remove build artifacts

uv run simple-edge-tts  # production mode
SIMPLE_EDGE_TTS_DEV=1 uv run simple-edge-tts   # dev mode (+ frontend: cd frontend && npm run dev)

uv run pytest tests/ -v          # tests
uv run ruff check src/ tests/    # lint
```

## CI Contract

`.github/workflows/ci.yml` — job "Lint & Test", triggers on pull_request and push to main:

1. Lint: `uv run ruff check src/ tests/`
2. Workflow YAML validation (parses every `.github/workflows/*.yml`)
3. pytest with `QT_QPA_PLATFORM=offscreen` (legacy defensive default; PySide6 removed in #45)
4. Frontend: `npm ci`, `tsc -b`, `vite build`, oxlint

mypy is not part of CI.

## Architecture Essentials

- **IPC contract**: `Api` class (`src/api.py`) is exposed via pywebview `js_api` as `window.pywebview.api.*`. Every method returns a JSON-encoded string (PyWebView serialization limitation).
- **Persistent event loop**: `src/tts_engine.py` keeps one asyncio loop alive in a daemon thread (`run_coroutine_threadsafe`); `asyncio.run()` crashes under PyWebView's threading model. On Windows the Selector event-loop policy must be set before any loop exists (aiohttp DNS compat).
- **Frozen path resolution**: `sys.frozen` branches live in `config_manager._get_config_dir()`, `logging_config._get_log_dir()`, and `main._get_base_dir()` (`sys._MEIPASS`). Windows frozen builds use the exe directory for config/log instead of %APPDATA% (Ref #166 portable build). Details: `src/CLAUDE.md`.
- **Version resolution chain**: `importlib.metadata` → pyproject.toml regex fallback (`Api._get_app_version`, Ref #174/#205). pyproject.toml `version` is the single version source; release.yml extracts it (Ref #90).
- **Update flow**: `update_checker` (detect + notify, no GUI deps) → `update_manager` (IDLE → DOWNLOADING → VERIFYING → READY → INSTALLING state machine; macOS ditto `--noqtn` + quarantine xattr removal, Windows `.bat` relaunch with `_MEIPASS` scrub Ref #202).
- **i18n**: `src/resources/translations/{zh-TW,en-US}.json`, live language switching.
- **System tray**: pystray `run_detached()`, imported lazily inside functions (Linux headless import would fail on X display connect).

## Coding Mandates

- Tests must NOT hardcode version strings — parse pyproject.toml dynamically (see `tests/test_api.py::test_get_app_version_fallback_to_pyproject_toml`).
- Heavy imports (`edge_tts`, `aiohttp`, pystray) go inside functions, not module level — startup speed and headless CI safety.
- IPC boundary error handling distinguishes error types via `EdgeTTSException` (imported from `edge_tts.exceptions`, aliased to `Exception` as fallback — see `src/api.py`).
- Frontend always calls backend through the `useApi` hook (`frontend/src/hooks/useApi.ts`), never `window.pywebview.api.*` directly.
- Conventional Commits.

## High-Risk Scope

Touching any of these warrants extra review depth:

- `update_manager` install/restart flow (system-level `ditto`/`xattr`/`.bat`/process exit)
- Frozen path resolution (`config_manager` / `logging_config` / `main._get_base_dir`)
- IPC API signature changes in `src/api.py` (cross frontend/backend impact)
- Release workflow (`.github/workflows/release.yml`)
- Config schema changes (`DEFAULTS` dict in `src/config_manager.py`)

## Git Safety

Never commit directly to `main` — named branch + PR, CI green, review, squash merge.
