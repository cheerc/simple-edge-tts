# Changelog

## v0.1.0 (unreleased)

### Highlights
- Complete UI redesign: PySide6 → React + PyWebView
- Light Cream + Coral color scheme with dark/light theme support
- System tray support (pystray)
- i18n: zh-TW / en-US live switching
- Auto-update version check (detect + notify)
- CI/CD pipeline with frontend build

### Added
- React frontend with Tailwind CSS v4
- PyWebView IPC bridge (window.pywebview.api.*)
- Voice selection with language grouping (zh-TW/en-US priority)
- Speed control slider (0.5× – 2.0×)
- Text editor with character count
- Toast notification system
- Settings modal (language selection)
- System tray (Show/Hide, Quit) via pystray
- Frontend i18n with live language switching
- CI: frontend build + lint integrated
- Pitch control slider (-50 to +50 Hz)
- Dark/light theme with system preference detection
- Auto-update version check (detect + notify, no auto-download)

### Changed
- UI framework: PySide6 → React + PyWebView
- System tray: QSystemTrayIcon → pystray
- Audio playback: QMediaPlayer → HTML5 `<audio>` bridge
- Entry point: `python -m src.main` → `uv run simple-edge-tts`

### Known Limitations
- Output format: MP3 only (edge-tts API limitation)
