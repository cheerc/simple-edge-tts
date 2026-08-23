# src/ — Backend Module Map

## Modules

| File | Role |
|------|------|
| `main.py` | Entry point (`src.main:main`). Startup order, dev-mode detection, tray-before-webview ordering (macOS NSStatusItem constraint), shutdown paths via `AppContext`. |
| `api.py` | IPC bridge surface exposed as `window.pywebview.api.*`. Public methods: `get_voices`, `generate_tts`, `preview_tts`, `get_config`, `set_config`, `get_translations`, `play_audio`, `stop_audio`, `get_audio_url`, `notify_playback_finished`, `check_update`, `set_window`, `download_update`, `get_download_progress`, `cancel_download`, `install_update`, `get_output_dir`, `select_output_dir`. All return JSON-encoded strings. |
| `tts_engine.py` | Wraps edge-tts: voice list, audio generation. Owns the persistent event-loop thread (module-level singleton; see root CLAUDE.md). Windows Selector policy setup. |
| `audio_player.py` | Playback control via HTML5 `<audio>` in WebView (no native player). `PlayerState` enum + state-changed signal; actual playback happens in frontend JS. |
| `config_manager.py` | Config read/write with defaults and corrupt-file recovery. `DEFAULTS` dict is the config schema SSOT. Auto-migrates from legacy log-dir location. |
| `logging_config.py` | Rotating file logging; resolves log dir per platform/frozen mode. Note: isinstance checks on handlers must exclude `RotatingFileHandler` when testing for plain `StreamHandler`. |
| `i18n.py` | Loads `resources/translations/{zh-TW,en-US}.json`; live language switching. |
| `system_tray.py` | pystray tray icon, `run_detached()`. pystray/PIL imported lazily inside methods (headless-safe import). |
| `update_checker.py` | Version detection against GitHub releases (`compare_versions`); no GUI deps so it runs before window exists. |
| `update_manager.py` | Download/install state machine (`UpdateState`: IDLE → DOWNLOADING → VERIFYING → READY → INSTALLING / ERROR). High-risk module — see root CLAUDE.md. |
| `app_context.py` | `AppContext` dataclass bundling audio_player/api/tray/window refs for shutdown handlers (Ref #140). |

## Path Resolution Cheat Sheet

Behavior differs across three files — do not assume one helper covers all:

| Concern | Dev mode | macOS frozen | Windows frozen |
|---------|----------|--------------|----------------|
| Bundled data root (`main._get_base_dir`) | repo root (`Path(__file__).parent.parent`) | `sys._MEIPASS` (Contents/Resources) | `sys._MEIPASS` (_internal/) |
| Config dir (`config_manager._get_config_dir`) | `~/Library/Application Support/simple-edge-tts` | same as dev | exe directory if writable, else `%APPDATA%/simple-edge-tts/config` (Ref #166 portable build) |
| Log dir (`logging_config._get_log_dir`) | `~/Library/Logs/simple-edge-tts` | same as dev | exe directory if writable, else `%LOCALAPPDATA%/simple-edge-tts/logs` |

All three frozen branches use a write-test probe before committing to the exe directory.

## Test Conventions

- Tests mirror modules: `tests/test_api.py` ↔ `api.py`, etc.
- Frozen-path tests patch `sys.frozen = True` (`patch.object(sys, "frozen", True, create=True)` pattern — `tests/test_frozen_paths.py`, `tests/test_config_manager.py`).
- `tests/test_ui/` holds integration-level UI tests.
- Never hardcode version strings in assertions; parse pyproject.toml dynamically.

## Known Tech Debt

- PySide6 remains in transitional deps for pytest-qt UI tests; CI installs Qt system libs until full removal (post-T20). This is why CI tolerates exit code 134 (QThread cleanup SIGABRT).
