# Changelog

## v0.1.0 (unreleased)

### Highlights
- Complete UI redesign: PySide6 → React + PyWebView
- Light Cream + Coral color scheme
- System tray support (pystray)
- i18n: zh-TW / en-US live switching
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

### Changed
- UI framework: PySide6 → React + PyWebView
- System tray: QSystemTrayIcon → pystray
- Audio playback: QMediaPlayer → HTML5 `<audio>` bridge
- Entry point: `python -m src.main` → `uv run simple-edge-tts`

### Known Limitations
- Pitch control: backend supports it but no UI slider yet
- Dark/light theme: not yet implemented
- Auto-update: not yet implemented
- Output format selection: MP3 only
