# Config Persistence Spec

## Overview
Application settings (language, file logging, voice params, window geometry) are persisted to a JSON config file managed by `ConfigManager`.

## Config Location

- Config directory: `_get_log_dir()` (same as log directory)
  - macOS: `~/.local/share/simple-edge-tts/logs/`
  - Windows: `%LOCALAPPDATA%/simple-edge-tts/logs/`
  - Windows frozen (writable exe dir): `<exe_dir>/`
  - Windows frozen (readonly, e.g. Program Files): fallback to `%LOCALAPPDATA%`
- Config file: `config.json` in the config directory

## Default Settings

```json
{
  "language": "en-US",
  "voice": "en-US-ChristopherNeural",
  "rate": "+0%",
  "pitch": "+0Hz",
  "output_dir": "<Desktop>",
  "window_geometry": {"x": 100, "y": 100, "w": 900, "h": 600},
  "enable_file_logging": false
}
```

## File Logging Toggle

- Default: **OFF** (`enable_file_logging: false`)
- Toggle via Settings Modal → Switch component → `api.setConfig("enable_file_logging", bool)`
- Changing this setting prompts "Restart Required" dialog
- When OFF: `setup_logging()` skips `RotatingFileHandler` setup, no log files created
- When ON: logs written to log directory with rotation (1 MB × 5 backups)

## API Surface

- `ConfigManager.get(key)` — read config value
- `ConfigManager.set(key, value)` — write and persist to `config.json`
- Frontend bridge: `api.getConfig(key)` / `api.setConfig(key, value)` via pywebview IPC

## Key Constraints

- `config_manager.py` lazy-imports `_get_log_dir` from `logging_config.py` to avoid circular dependency
- `setup_logging()` lazy-imports `ConfigManager` to read `enable_file_logging` default
- `setup_logging()` is idempotent via module-level `_setup_done` flag (works for both file-logging ON and OFF)

## Related

- PR #107: feat(build/settings)
- Issue #105: settings persistence + file logging toggle
