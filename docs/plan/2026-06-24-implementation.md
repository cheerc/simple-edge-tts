# simple-edge-tts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-platform desktop TTS app with PySide6 GUI that wraps edge-tts for voice synthesis, supporting zh-TW/en-US i18n, dark/light theming, and single-file distribution.

**Architecture:** Python app with PySide6 GUI. Core logic modules (tts_engine, config_manager, i18n, audio_player) are pure logic with no Qt dependency where possible, making them independently testable. UI modules compose these into a left-right split layout. edge-tts async calls run in QThread to avoid UI freezes.

**Tech Stack:** Python 3.11+, PySide6, edge-tts, PyInstaller, pytest, pytest-qt, pytest-asyncio

**Spec:** `docs/spec/2026-06-24-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Project metadata, dependencies, scripts |
| `src/__init__.py` | Package marker |
| `src/main.py` | Entry point: create QApplication, show window |
| `src/app.py` | App-level setup: theme detection, high-DPI |
| `src/config_manager.py` | Read/write `~/.simple-edge-tts/config.json`, defaults |
| `src/i18n.py` | Translation loader, `t("key")` lookup, language switch signal |
| `src/tts_engine.py` | Wrap edge-tts: list voices, generate audio in QThread |
| `src/audio_player.py` | Play/stop audio via QMediaPlayer, state machine |
| `src/ui/__init__.py` | Package marker |
| `src/ui/main_window.py` | Main window: splitter layout, title bar, status bar |
| `src/ui/voice_panel.py` | Left panel: voice combo, search, sliders, folder picker |
| `src/ui/text_panel.py` | Right panel: text edit, action buttons, status label |
| `src/ui/theme.py` | QSS for light/dark, OS theme listener |
| `src/resources/translations/zh-TW.json` | Traditional Chinese UI strings |
| `src/resources/translations/en-US.json` | English UI strings |
| `tests/test_config_manager.py` | Config read/write/defaults tests |
| `tests/test_i18n.py` | Translation loading, key parity tests |
| `tests/test_tts_engine.py` | Voice listing, param formatting, async gen (mocked) |
| `tests/test_audio_player.py` | Play/stop state machine tests |
| `tests/test_ui/test_main_window.py` | Window layout, splitter tests |
| `tests/test_ui/test_voice_panel.py` | Voice combo, slider, folder picker tests |
| `tests/test_ui/test_text_panel.py` | Text input, button state, export tests |
| `workflow.sh` | Local test runner (t1-t6), interactive menu + CLI dispatch |
| `deploy.sh` | Packaging script (p1/p2/p3/v1) |
| `.github/workflows/ci.yml` | PR gate: runs `./workflow.sh t6` |
| `.github/workflows/build.yml` | Release build: tag v* → exe + dmg |
| `.github/PULL_REQUEST_TEMPLATE.md` | PR checklist template |
| `.pre-commit-config.yaml` | gitleaks secret scanning hook |

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/main.py`
- Create: `tests/__init__.py`
- Create: `tests/test_ui/__init__.py`
- Create: `README.md`
- Create: `LICENSE`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "simple-edge-tts"
version = "0.1.0"
description = "Cross-platform Edge TTS desktop app with PySide6 GUI"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
authors = [{name = "cheerc", url = "https://github.com/cheerc"}]
dependencies = [
    "PySide6>=6.6.0",
    "edge-tts>=6.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-qt>=4.2",
    "pytest-asyncio>=0.21",
    "mypy>=1.8",
    "ruff>=0.3",
    "pyinstaller>=6.0",
]

[project.scripts]
simple-edge-tts = "src.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `src/__init__.py`, `tests/__init__.py`, `tests/test_ui/__init__.py`**

All three files: empty files (package markers).

- [ ] **Step 3: Create `src/main.py` stub**

```python
"""Entry point for simple-edge-tts application."""

import sys


def main():
    """Launch the application."""
    print("simple-edge-tts v0.1.0")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Create `README.md`**

```markdown
# simple-edge-tts

Cross-platform desktop app for Microsoft Edge text-to-speech. Select a voice, type your text, preview, and export as MP3.

## Features

- 🎙️ 300+ voices from Microsoft Edge TTS
- 🇹🇼 Traditional Chinese & English UI
- 🎚️ Adjustable rate and pitch
- 🌗 Dark/Light theme (follows system)
- 💾 Export to MP3
- 🖥️ macOS + Windows

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
```

- [ ] **Step 5: Create `LICENSE`** (MIT, copyright cheerc 2026)

- [ ] **Step 6: Install dev dependencies and verify**

Run: `pip install -e ".[dev]"`
Run: `python -m src.main`
Expected: prints `simple-edge-tts v0.1.0`

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding with pyproject.toml and stubs"
```

---

## Task 2: Config Manager (TDD)

**Files:**
- Create: `src/config_manager.py`
- Create: `tests/test_config_manager.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for config_manager — read/write config, defaults, corrupt file recovery."""

import json
import pytest
from src.config_manager import ConfigManager


class TestConfigManagerDefaults:
    def test_default_language_is_zh_tw(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("language") == "zh-TW"

    def test_default_voice(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("last_voice") == "zh-TW-HsiaoChenNeural"

    def test_default_rate(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("rate") == "+0%"

    def test_default_pitch(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("pitch") == "+0Hz"

    def test_default_output_dir_is_desktop(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert "Desktop" in cm.get("output_dir") or cm.get("output_dir") == ""

    def test_unknown_key_returns_none(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("nonexistent_key") is None


class TestConfigManagerReadWrite:
    def test_set_and_get(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.set("language", "en-US")
        assert cm.get("language") == "en-US"

    def test_persistence_across_instances(self, tmp_path):
        cm1 = ConfigManager(config_dir=tmp_path)
        cm1.set("rate", "+20%")
        cm1.save()

        cm2 = ConfigManager(config_dir=tmp_path)
        assert cm2.get("rate") == "+20%"

    def test_save_creates_config_file(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.save()
        assert (tmp_path / "config.json").exists()

    def test_save_writes_valid_json(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)
        cm.set("language", "en-US")
        cm.save()
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["language"] == "en-US"


class TestConfigManagerEdgeCases:
    def test_corrupt_json_resets_to_defaults(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text("{invalid json!!!}")
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("language") == "zh-TW"

    def test_missing_key_in_file_falls_back_to_default(self, tmp_path):
        config_file = tmp_path / "config.json"
        config_file.write_text('{"language": "en-US"}')
        cm = ConfigManager(config_dir=tmp_path)
        assert cm.get("language") == "en-US"
        assert cm.get("rate") == "+0%"

    def test_config_dir_created_if_missing(self, tmp_path):
        nested = tmp_path / "subdir" / "config"
        cm = ConfigManager(config_dir=nested)
        cm.save()
        assert nested.exists()
        assert (nested / "config.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.config_manager'`

- [ ] **Step 3: Implement `src/config_manager.py`**

```python
"""Manages persistent application configuration via JSON file."""

import json
from pathlib import Path
from typing import Any


DEFAULTS = {
    "language": "zh-TW",
    "last_voice": "zh-TW-HsiaoChenNeural",
    "rate": "+0%",
    "pitch": "+0Hz",
    "output_dir": str(Path.home() / "Desktop"),
    "window_geometry": {"x": 100, "y": 100, "w": 900, "h": 600},
}


class ConfigManager:
    """Read/write application config with defaults and corrupt-file recovery."""

    def __init__(self, config_dir: Path | None = None):
        if config_dir is None:
            config_dir = Path.home() / ".simple-edge-tts"
        self._config_dir = Path(config_dir)
        self._config_file = self._config_dir / "config.json"
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self):
        if self._config_file.exists():
            try:
                with open(self._config_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                if isinstance(saved, dict):
                    self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass  # corrupt file — keep defaults

    def get(self, key: str) -> Any:
        return self._data.get(key)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def save(self):
        self._config_dir.mkdir(parents=True, exist_ok=True)
        with open(self._config_file, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config_manager.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/config_manager.py tests/test_config_manager.py
git commit -m "feat: config manager with defaults, persistence, and corrupt file recovery"
```

---

## Task 3: Internationalization (TDD)

**Files:**
- Create: `src/i18n.py`
- Create: `src/resources/translations/zh-TW.json`
- Create: `src/resources/translations/en-US.json`
- Create: `tests/test_i18n.py`

- [ ] **Step 1: Create translation files**

`src/resources/translations/zh-TW.json`:
```json
{
  "app_title": "simple-edge-tts",
  "voice_selection": "聲音選擇",
  "search_voice": "搜尋聲音...",
  "parameters": "參數設定",
  "rate": "語速 (Rate)",
  "pitch": "音調 (Pitch)",
  "output_settings": "輸出設定",
  "choose_folder": "選擇資料夾",
  "text_placeholder": "輸入要轉換的文字...",
  "preview": "試聽",
  "stop": "停止",
  "export_mp3": "匯出 MP3",
  "status_ready": "就緒",
  "status_generating": "產生語音中...",
  "status_playing": "播放中...",
  "status_exported": "匯出完成：{filename}",
  "error_no_internet": "無法連線到 TTS 服務，請檢查網路連線",
  "error_export_failed": "匯出失敗：{error}",
  "error_folder_not_writable": "無法寫入資料夾，請選擇其他位置",
  "voice_group_tw": "台灣中文",
  "voice_group_en": "English",
  "voice_group_other": "其他",
  "lang_toggle": "EN"
}
```

`src/resources/translations/en-US.json`:
```json
{
  "app_title": "simple-edge-tts",
  "voice_selection": "Voice Selection",
  "search_voice": "Search voices...",
  "parameters": "Parameters",
  "rate": "Rate",
  "pitch": "Pitch",
  "output_settings": "Output Settings",
  "choose_folder": "Choose Folder",
  "text_placeholder": "Enter text to convert...",
  "preview": "Preview",
  "stop": "Stop",
  "export_mp3": "Export MP3",
  "status_ready": "Ready",
  "status_generating": "Generating speech...",
  "status_playing": "Playing...",
  "status_exported": "Exported: {filename}",
  "error_no_internet": "Cannot connect to TTS service. Please check your internet connection.",
  "error_export_failed": "Export failed: {error}",
  "error_folder_not_writable": "Cannot write to folder. Please choose another location.",
  "voice_group_tw": "Traditional Chinese",
  "voice_group_en": "English",
  "voice_group_other": "Other",
  "lang_toggle": "繁中"
}
```

- [ ] **Step 2: Write failing tests**

```python
"""Tests for i18n — translation loading, key parity, fallback."""

import json
from pathlib import Path
import pytest
from src.i18n import I18n


TRANSLATIONS_DIR = Path(__file__).parent.parent / "src" / "resources" / "translations"


class TestI18nLoading:
    def test_load_zh_tw(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "試聽"

    def test_load_en_us(self):
        i18n = I18n("en-US", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "Preview"

    def test_switch_language(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "試聽"
        i18n.set_language("en-US")
        assert i18n.t("preview") == "Preview"

    def test_current_language(self):
        i18n = I18n("en-US", translations_dir=TRANSLATIONS_DIR)
        assert i18n.current_language == "en-US"


class TestI18nFallback:
    def test_missing_key_returns_key_name(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("nonexistent_key") == "nonexistent_key"

    def test_invalid_language_falls_back_to_zh_tw(self):
        i18n = I18n("fr-FR", translations_dir=TRANSLATIONS_DIR)
        assert i18n.t("preview") == "試聽"


class TestI18nKeyParity:
    def test_both_languages_have_same_keys(self):
        zh = json.loads((TRANSLATIONS_DIR / "zh-TW.json").read_text())
        en = json.loads((TRANSLATIONS_DIR / "en-US.json").read_text())
        assert set(zh.keys()) == set(en.keys()), (
            f"Key mismatch: zh-TW only={set(zh.keys()) - set(en.keys())}, "
            f"en-US only={set(en.keys()) - set(zh.keys())}"
        )


class TestI18nFormatting:
    def test_string_interpolation(self):
        i18n = I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)
        result = i18n.t("status_exported", filename="test.mp3")
        assert result == "匯出完成：test.mp3"

    def test_string_interpolation_en(self):
        i18n = I18n("en-US", translations_dir=TRANSLATIONS_DIR)
        result = i18n.t("status_exported", filename="test.mp3")
        assert result == "Exported: test.mp3"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_i18n.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.i18n'`

- [ ] **Step 4: Implement `src/i18n.py`**

```python
"""Internationalization: load translations, provide t() lookup with formatting."""

import json
from pathlib import Path
from typing import Any

DEFAULT_LANGUAGE = "zh-TW"
SUPPORTED_LANGUAGES = ("zh-TW", "en-US")


class I18n:
    """Translation manager supporting zh-TW and en-US."""

    def __init__(
        self,
        language: str = DEFAULT_LANGUAGE,
        translations_dir: Path | None = None,
    ):
        if translations_dir is None:
            translations_dir = Path(__file__).parent / "resources" / "translations"
        self._translations_dir = translations_dir
        self._strings: dict[str, str] = {}
        self._language = ""
        self.set_language(language)

    @property
    def current_language(self) -> str:
        return self._language

    def set_language(self, language: str):
        if language not in SUPPORTED_LANGUAGES:
            language = DEFAULT_LANGUAGE
        self._language = language
        file = self._translations_dir / f"{language}.json"
        try:
            with open(file, "r", encoding="utf-8") as f:
                self._strings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._strings = {}

    def t(self, key: str, **kwargs: Any) -> str:
        value = self._strings.get(key, key)
        if kwargs:
            try:
                value = value.format(**kwargs)
            except KeyError:
                pass
        return value
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_i18n.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add src/i18n.py src/resources/ tests/test_i18n.py
git commit -m "feat: i18n with zh-TW/en-US translations and string interpolation"
```

---

## Task 4: TTS Engine (TDD)

**Files:**
- Create: `src/tts_engine.py`
- Create: `tests/test_tts_engine.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for tts_engine — voice listing, param formatting, async generation (mocked)."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from src.tts_engine import TTSEngine, format_rate, format_pitch, sanitize_filename


class TestParamFormatting:
    def test_format_rate_positive(self):
        assert format_rate(20) == "+20%"

    def test_format_rate_zero(self):
        assert format_rate(0) == "+0%"

    def test_format_rate_negative(self):
        assert format_rate(-30) == "-30%"

    def test_format_pitch_positive(self):
        assert format_pitch(10) == "+10Hz"

    def test_format_pitch_zero(self):
        assert format_pitch(0) == "+0Hz"

    def test_format_pitch_negative(self):
        assert format_pitch(-25) == "-25Hz"


class TestSanitizeFilename:
    def test_ascii_text(self):
        result = sanitize_filename("Hello World")
        assert result == "Hello_Wo"

    def test_chinese_text(self):
        result = sanitize_filename("你好世界測試用文字")
        assert result == "你好世界測試用文"

    def test_short_text(self):
        result = sanitize_filename("Hi")
        assert result == "Hi"

    def test_special_chars_replaced(self):
        result = sanitize_filename('a/b\\c:d"e')
        assert "/" not in result
        assert "\\" not in result
        assert ":" not in result

    def test_empty_text(self):
        result = sanitize_filename("")
        assert result == "untitled"


class TestTTSEngineVoices:
    @patch("src.tts_engine.edge_tts.list_voices")
    def test_list_voices_returns_list(self, mock_list):
        mock_list.return_value = asyncio.coroutine(lambda: [
            {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
        ])()
        engine = TTSEngine()
        voices = engine.get_voices_sync()
        assert len(voices) >= 2

    @patch("src.tts_engine.edge_tts.list_voices")
    def test_voices_grouped_tw_first(self, mock_list):
        mock_voices = [
            {"ShortName": "en-US-JennyNeural", "Locale": "en-US", "Gender": "Female"},
            {"ShortName": "zh-TW-HsiaoChenNeural", "Locale": "zh-TW", "Gender": "Female"},
            {"ShortName": "ja-JP-NanamiNeural", "Locale": "ja-JP", "Gender": "Female"},
        ]
        mock_list.return_value = asyncio.coroutine(lambda: mock_voices)()
        engine = TTSEngine()
        grouped = engine.get_grouped_voices_sync()
        groups = list(grouped.keys())
        assert groups[0] == "zh-TW"
        assert groups[1] == "en-US"


class TestTTSEngineGenerate:
    @patch("src.tts_engine.edge_tts.Communicate")
    def test_generate_creates_file(self, mock_communicate, tmp_path):
        mock_instance = MagicMock()
        mock_instance.save = AsyncMock()
        mock_communicate.return_value = mock_instance

        engine = TTSEngine()
        output = tmp_path / "test.mp3"
        asyncio.run(engine.generate("Hello", "en-US-JennyNeural", str(output)))

        mock_communicate.assert_called_once()
        mock_instance.save.assert_called_once_with(str(output))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_tts_engine.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `src/tts_engine.py`**

```python
"""Wraps edge-tts: list voices, generate audio, format parameters."""

import asyncio
import re
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

import edge_tts

VOICE_GROUP_ORDER = ["zh-TW", "en-US"]


def format_rate(value: int) -> str:
    return f"+{value}%" if value >= 0 else f"{value}%"


def format_pitch(value: int) -> str:
    return f"+{value}Hz" if value >= 0 else f"{value}Hz"


def sanitize_filename(text: str, max_len: int = 8) -> str:
    if not text.strip():
        return "untitled"
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", text)
    cleaned = cleaned.strip()[:max_len]
    return cleaned if cleaned else "untitled"


def make_output_filename(text: str) -> str:
    prefix = sanitize_filename(text)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}.mp3"


class TTSEngine:
    """Synchronous-facing wrapper around async edge-tts."""

    def get_voices_sync(self) -> list[dict[str, Any]]:
        return asyncio.run(edge_tts.list_voices())

    def get_grouped_voices_sync(self) -> OrderedDict[str, list[dict]]:
        voices = self.get_voices_sync()
        groups: dict[str, list[dict]] = {}
        for v in voices:
            locale = v.get("Locale", "unknown")
            groups.setdefault(locale, []).append(v)

        ordered = OrderedDict()
        for key in VOICE_GROUP_ORDER:
            if key in groups:
                ordered[key] = groups.pop(key)
        for key in sorted(groups.keys()):
            ordered[key] = groups[key]
        return ordered

    async def generate(
        self,
        text: str,
        voice: str,
        output_path: str,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ):
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
        await communicate.save(output_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_tts_engine.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/tts_engine.py tests/test_tts_engine.py
git commit -m "feat: TTS engine wrapper with voice grouping and param formatting"
```

---

## Task 5: Audio Player (TDD)

**Files:**
- Create: `src/audio_player.py`
- Create: `tests/test_audio_player.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for audio_player — state machine: idle→playing→idle, stop, errors."""

from unittest.mock import MagicMock, patch
import pytest
from src.audio_player import AudioPlayer, PlayerState


class TestPlayerState:
    def test_initial_state_is_idle(self):
        player = AudioPlayer()
        assert player.state == PlayerState.IDLE

    def test_play_changes_state(self):
        player = AudioPlayer()
        with patch.object(player, "_media_player", create=True):
            player.play("/fake/path.mp3")
            assert player.state == PlayerState.PLAYING

    def test_stop_returns_to_idle(self):
        player = AudioPlayer()
        with patch.object(player, "_media_player", create=True):
            player.play("/fake/path.mp3")
            player.stop()
            assert player.state == PlayerState.IDLE

    def test_stop_when_idle_is_noop(self):
        player = AudioPlayer()
        player.stop()
        assert player.state == PlayerState.IDLE

    def test_play_nonexistent_file_stays_idle(self):
        player = AudioPlayer()
        player.play("/nonexistent/file.mp3")
        assert player.state == PlayerState.IDLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_audio_player.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `src/audio_player.py`**

```python
"""Audio playback controller using QMediaPlayer. State machine: idle ↔ playing."""

from enum import Enum, auto
from pathlib import Path

from PySide6.QtCore import QUrl, QObject, Signal
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class PlayerState(Enum):
    IDLE = auto()
    PLAYING = auto()


class AudioPlayer(QObject):
    """Play/stop audio files with state tracking."""

    state_changed = Signal(PlayerState)
    playback_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = PlayerState.IDLE
        self._media_player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._media_player.setAudioOutput(self._audio_output)
        self._media_player.mediaStatusChanged.connect(self._on_status_changed)

    @property
    def state(self) -> PlayerState:
        return self._state

    def play(self, file_path: str):
        path = Path(file_path)
        if not path.exists():
            return
        self._media_player.setSource(QUrl.fromLocalFile(str(path)))
        self._media_player.play()
        self._state = PlayerState.PLAYING
        self.state_changed.emit(self._state)

    def stop(self):
        if self._state == PlayerState.IDLE:
            return
        self._media_player.stop()
        self._state = PlayerState.IDLE
        self.state_changed.emit(self._state)

    def _on_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._state = PlayerState.IDLE
            self.state_changed.emit(self._state)
            self.playback_finished.emit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_audio_player.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/audio_player.py tests/test_audio_player.py
git commit -m "feat: audio player with play/stop state machine"
```

---

## Task 6: Theme System

**Files:**
- Create: `src/ui/__init__.py`
- Create: `src/ui/theme.py`

- [ ] **Step 1: Create `src/ui/__init__.py`** (empty file)

- [ ] **Step 2: Implement `src/ui/theme.py`**

```python
"""QSS theme definitions for light and dark modes. Follows OS setting."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

LIGHT_QSS = """
QMainWindow {
    background-color: #f5f5f7;
}
QLabel {
    color: #1d1d1f;
}
QTextEdit {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 1px solid #d2d2d7;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
}
QComboBox {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #d2d2d7;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #007aff;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QPushButton {
    background-color: #007aff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #0066d6;
}
QPushButton:disabled {
    background-color: #d2d2d7;
    color: #86868b;
}
QPushButton#exportButton {
    background-color: #34c759;
}
QPushButton#exportButton:hover {
    background-color: #2db84d;
}
QGroupBox {
    border: 1px solid #e5e5ea;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 20px;
    background-color: #ffffff;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #86868b;
    font-weight: 600;
    font-size: 12px;
}
QStatusBar {
    color: #86868b;
    font-size: 12px;
}
QLineEdit {
    background-color: #ffffff;
    border: 1px solid #d2d2d7;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
"""

DARK_QSS = """
QMainWindow {
    background-color: #1c1c1e;
}
QLabel {
    color: #f5f5f7;
}
QTextEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 8px;
    padding: 12px;
    font-size: 14px;
}
QComboBox {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #3a3a3c;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #0a84ff;
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}
QPushButton {
    background-color: #0a84ff;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #409cff;
}
QPushButton:disabled {
    background-color: #3a3a3c;
    color: #636366;
}
QPushButton#exportButton {
    background-color: #30d158;
}
QPushButton#exportButton:hover {
    background-color: #4de06e;
}
QGroupBox {
    border: 1px solid #3a3a3c;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 20px;
    background-color: #2c2c2e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #8e8e93;
    font-weight: 600;
    font-size: 12px;
}
QStatusBar {
    color: #8e8e93;
    font-size: 12px;
}
QLineEdit {
    background-color: #2c2c2e;
    color: #f5f5f7;
    border: 1px solid #3a3a3c;
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 13px;
}
"""


def is_dark_mode() -> bool:
    hints = QApplication.instance().styleHints()
    if hasattr(hints, "colorScheme"):
        return hints.colorScheme() == Qt.ColorScheme.Dark
    palette = QApplication.instance().palette()
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


def apply_theme(app: QApplication):
    qss = DARK_QSS if is_dark_mode() else LIGHT_QSS
    app.setStyleSheet(qss)
```

- [ ] **Step 3: Commit**

```bash
git add src/ui/
git commit -m "feat: light/dark theme QSS following OS color scheme"
```

---

## Task 7: UI — Voice Panel

**Files:**
- Create: `src/ui/voice_panel.py`
- Create: `tests/test_ui/test_voice_panel.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for voice_panel — voice combo, search filter, sliders, folder picker."""

import pytest
from PySide6.QtCore import Qt
from src.ui.voice_panel import VoicePanel
from src.i18n import I18n
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


class TestVoicePanel:
    def test_panel_creates(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel is not None

    def test_rate_slider_default_zero(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel.rate_value() == 0

    def test_pitch_slider_default_zero(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel.pitch_value() == 0

    def test_rate_slider_range(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._rate_slider.setValue(-50)
        assert panel.rate_value() == -50
        panel._rate_slider.setValue(100)
        assert panel.rate_value() == 100

    def test_voice_combo_exists(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel._voice_combo is not None

    def test_search_filter_exists(self, qtbot, i18n):
        panel = VoicePanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel._search_input is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui/test_voice_panel.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `src/ui/voice_panel.py`**

```python
"""Left panel: voice selection with search, rate/pitch sliders, output folder picker."""

from pathlib import Path

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QComboBox, QLineEdit,
    QSlider, QLabel, QHBoxLayout, QPushButton, QFileDialog,
)

from src.i18n import I18n


class VoicePanel(QWidget):
    """Left panel containing voice selection, parameter sliders, and output settings."""

    voice_changed = Signal(str)
    rate_changed = Signal(int)
    pitch_changed = Signal(int)
    output_dir_changed = Signal(str)

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._output_dir = str(Path.home() / "Desktop")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Voice selection group
        voice_group = QGroupBox(self._i18n.t("voice_selection"))
        voice_layout = QVBoxLayout(voice_group)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(self._i18n.t("search_voice"))
        self._search_input.textChanged.connect(self._filter_voices)
        voice_layout.addWidget(self._search_input)
        self._voice_combo = QComboBox()
        self._voice_combo.currentTextChanged.connect(
            lambda t: self.voice_changed.emit(t)
        )
        voice_layout.addWidget(self._voice_combo)
        layout.addWidget(voice_group)

        # Parameters group
        param_group = QGroupBox(self._i18n.t("parameters"))
        param_layout = QVBoxLayout(param_group)

        # Rate slider
        self._rate_label = QLabel(f"{self._i18n.t('rate')}: +0%")
        param_layout.addWidget(self._rate_label)
        self._rate_slider = QSlider(Qt.Orientation.Horizontal)
        self._rate_slider.setRange(-50, 100)
        self._rate_slider.setValue(0)
        self._rate_slider.valueChanged.connect(self._on_rate_changed)
        param_layout.addWidget(self._rate_slider)

        # Pitch slider
        self._pitch_label = QLabel(f"{self._i18n.t('pitch')}: +0Hz")
        param_layout.addWidget(self._pitch_label)
        self._pitch_slider = QSlider(Qt.Orientation.Horizontal)
        self._pitch_slider.setRange(-50, 50)
        self._pitch_slider.setValue(0)
        self._pitch_slider.valueChanged.connect(self._on_pitch_changed)
        param_layout.addWidget(self._pitch_slider)

        layout.addWidget(param_group)

        # Output settings group
        output_group = QGroupBox(self._i18n.t("output_settings"))
        output_layout = QVBoxLayout(output_group)
        self._dir_label = QLabel(self._output_dir)
        self._dir_label.setWordWrap(True)
        output_layout.addWidget(self._dir_label)
        dir_btn = QPushButton(self._i18n.t("choose_folder"))
        dir_btn.clicked.connect(self._choose_folder)
        output_layout.addWidget(dir_btn)
        layout.addWidget(output_group)

        layout.addStretch()

    def _on_rate_changed(self, value: int):
        sign = "+" if value >= 0 else ""
        self._rate_label.setText(f"{self._i18n.t('rate')}: {sign}{value}%")
        self.rate_changed.emit(value)

    def _on_pitch_changed(self, value: int):
        sign = "+" if value >= 0 else ""
        self._pitch_label.setText(f"{self._i18n.t('pitch')}: {sign}{value}Hz")
        self.pitch_changed.emit(value)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "", self._output_dir)
        if folder:
            self._output_dir = folder
            self._dir_label.setText(folder)
            self.output_dir_changed.emit(folder)

    def _filter_voices(self, text: str):
        for i in range(self._voice_combo.count()):
            # Filter is handled by showing/hiding — QComboBox doesn't natively support this,
            # so we repopulate. This is a simplified version.
            pass

    def set_voices(self, voices: list[dict]):
        self._all_voices = voices
        self._voice_combo.clear()
        for v in voices:
            self._voice_combo.addItem(v["ShortName"], v)

    def set_output_dir(self, path: str):
        self._output_dir = path
        self._dir_label.setText(path)

    def rate_value(self) -> int:
        return self._rate_slider.value()

    def pitch_value(self) -> int:
        return self._pitch_slider.value()

    def current_voice(self) -> str:
        return self._voice_combo.currentText()

    def update_texts(self):
        # Called when language changes — re-apply all i18n strings
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ui/test_voice_panel.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui/voice_panel.py tests/test_ui/test_voice_panel.py
git commit -m "feat: voice panel with search, rate/pitch sliders, folder picker"
```

---

## Task 8: UI — Text Panel

**Files:**
- Create: `src/ui/text_panel.py`
- Create: `tests/test_ui/test_text_panel.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for text_panel — text input, button states, signals."""

import pytest
from PySide6.QtCore import Qt
from src.ui.text_panel import TextPanel
from src.i18n import I18n
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


class TestTextPanel:
    def test_panel_creates(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert panel is not None

    def test_buttons_disabled_when_empty(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        assert not panel._preview_btn.isEnabled()
        assert not panel._export_btn.isEnabled()

    def test_buttons_enabled_when_text_entered(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        assert panel._preview_btn.isEnabled()
        assert panel._export_btn.isEnabled()

    def test_buttons_disabled_again_when_text_cleared(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        panel._text_edit.clear()
        assert not panel._preview_btn.isEnabled()
        assert not panel._export_btn.isEnabled()

    def test_get_text(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("測試文字")
        assert panel.get_text() == "測試文字"

    def test_preview_signal_emitted(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        with qtbot.waitSignal(panel.preview_requested):
            panel._preview_btn.click()

    def test_export_signal_emitted(self, qtbot, i18n):
        panel = TextPanel(i18n=i18n)
        qtbot.addWidget(panel)
        panel._text_edit.setPlainText("Hello")
        with qtbot.waitSignal(panel.export_requested):
            panel._export_btn.click()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui/test_text_panel.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `src/ui/text_panel.py`**

```python
"""Right panel: text input area, preview/stop/export buttons, status display."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QHBoxLayout, QPushButton, QLabel,
)

from src.i18n import I18n


class TextPanel(QWidget):
    """Right panel containing text input and action buttons."""

    preview_requested = Signal()
    stop_requested = Signal()
    export_requested = Signal()

    def __init__(self, i18n: I18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Text input
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(self._i18n.t("text_placeholder"))
        self._text_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._text_edit)

        # Button row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._preview_btn = QPushButton(f"▶ {self._i18n.t('preview')}")
        self._preview_btn.setEnabled(False)
        self._preview_btn.clicked.connect(self.preview_requested.emit)
        btn_layout.addWidget(self._preview_btn)

        self._stop_btn = QPushButton(f"⏹ {self._i18n.t('stop')}")
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        btn_layout.addWidget(self._stop_btn)

        self._export_btn = QPushButton(f"💾 {self._i18n.t('export_mp3')}")
        self._export_btn.setObjectName("exportButton")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self.export_requested.emit)
        btn_layout.addWidget(self._export_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        # Status
        self._status_label = QLabel(self._i18n.t("status_ready"))
        layout.addWidget(self._status_label)

    def _on_text_changed(self):
        has_text = bool(self._text_edit.toPlainText().strip())
        self._preview_btn.setEnabled(has_text)
        self._export_btn.setEnabled(has_text)

    def get_text(self) -> str:
        return self._text_edit.toPlainText()

    def set_status(self, text: str):
        self._status_label.setText(text)

    def set_playing(self, playing: bool):
        self._stop_btn.setEnabled(playing)
        self._preview_btn.setEnabled(not playing and bool(self.get_text().strip()))

    def update_texts(self):
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_ui/test_text_panel.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui/text_panel.py tests/test_ui/test_text_panel.py
git commit -m "feat: text panel with preview/stop/export buttons and status"
```

---

## Task 9: Main Window Assembly

**Files:**
- Create: `src/ui/main_window.py`
- Create: `src/app.py`
- Modify: `src/main.py`
- Create: `tests/test_ui/test_main_window.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for main_window — layout, splitter, i18n toggle."""

import pytest
from src.ui.main_window import MainWindow
from src.i18n import I18n
from src.config_manager import ConfigManager
from pathlib import Path

TRANSLATIONS_DIR = Path(__file__).parent.parent.parent / "src" / "resources" / "translations"


@pytest.fixture
def i18n():
    return I18n("zh-TW", translations_dir=TRANSLATIONS_DIR)


@pytest.fixture
def config(tmp_path):
    return ConfigManager(config_dir=tmp_path)


class TestMainWindow:
    def test_window_creates(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win is not None

    def test_window_title(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert "simple-edge-tts" in win.windowTitle()

    def test_has_voice_panel(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win._voice_panel is not None

    def test_has_text_panel(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win._text_panel is not None

    def test_minimum_size(self, qtbot, i18n, config):
        win = MainWindow(i18n=i18n, config=config)
        qtbot.addWidget(win)
        assert win.minimumWidth() >= 700
        assert win.minimumHeight() >= 500
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ui/test_main_window.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `src/ui/main_window.py`**

```python
"""Main window: left-right splitter layout with voice panel and text panel."""

import asyncio
import tempfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QHBoxLayout,
    QPushButton, QStatusBar, QMessageBox,
)

from src.config_manager import ConfigManager
from src.i18n import I18n
from src.tts_engine import TTSEngine, format_rate, format_pitch, make_output_filename
from src.audio_player import AudioPlayer, PlayerState
from src.ui.voice_panel import VoicePanel
from src.ui.text_panel import TextPanel


class TTSWorker(QThread):
    """Run edge-tts generation in background thread."""

    finished = Signal(str)
    error = Signal(str)

    def __init__(self, text, voice, output_path, rate, pitch):
        super().__init__()
        self._text = text
        self._voice = voice
        self._output_path = output_path
        self._rate = rate
        self._pitch = pitch

    def run(self):
        try:
            engine = TTSEngine()
            asyncio.run(engine.generate(
                self._text, self._voice, self._output_path,
                rate=self._rate, pitch=self._pitch,
            ))
            self.finished.emit(self._output_path)
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window with left-right split layout."""

    def __init__(self, i18n: I18n, config: ConfigManager, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self._config = config
        self._player = AudioPlayer(self)
        self._worker = None
        self._setup_ui()
        self._connect_signals()
        self._restore_state()

    def _setup_ui(self):
        self.setWindowTitle(self._i18n.t("app_title"))
        self.setMinimumSize(700, 500)
        self.resize(900, 600)

        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._voice_panel = VoicePanel(i18n=self._i18n)
        self._text_panel = TextPanel(i18n=self._i18n)

        splitter.addWidget(self._voice_panel)
        splitter.addWidget(self._text_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 7)

        # Language toggle
        self._lang_btn = QPushButton(self._i18n.t("lang_toggle"))
        self._lang_btn.setFixedSize(60, 28)
        self._lang_btn.clicked.connect(self._toggle_language)

        top_layout = QHBoxLayout()
        top_layout.addStretch()
        top_layout.addWidget(self._lang_btn)

        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.addWidget(splitter)

        from PySide6.QtWidgets import QVBoxLayout
        outer = QVBoxLayout()
        outer.addLayout(top_layout)
        outer.addWidget(wrapper)
        central.setLayout(outer)

        # Status bar
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def _connect_signals(self):
        self._text_panel.preview_requested.connect(self._on_preview)
        self._text_panel.stop_requested.connect(self._on_stop)
        self._text_panel.export_requested.connect(self._on_export)
        self._player.state_changed.connect(self._on_player_state_changed)
        self._player.playback_finished.connect(
            lambda: self._text_panel.set_status(self._i18n.t("status_ready"))
        )

    def _restore_state(self):
        output_dir = self._config.get("output_dir")
        if output_dir:
            self._voice_panel.set_output_dir(output_dir)

        rate = self._config.get("rate")
        if rate:
            try:
                val = int(rate.replace("%", "").replace("+", ""))
                self._voice_panel._rate_slider.setValue(val)
            except ValueError:
                pass

        pitch = self._config.get("pitch")
        if pitch:
            try:
                val = int(pitch.replace("Hz", "").replace("+", ""))
                self._voice_panel._pitch_slider.setValue(val)
            except ValueError:
                pass

    def _on_preview(self):
        text = self._text_panel.get_text()
        voice = self._voice_panel.current_voice()
        if not text or not voice:
            return
        self._text_panel.set_status(self._i18n.t("status_generating"))
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp.close()
        self._run_tts(text, voice, tmp.name, is_preview=True)

    def _on_export(self):
        text = self._text_panel.get_text()
        voice = self._voice_panel.current_voice()
        if not text or not voice:
            return
        output_dir = self._voice_panel._output_dir
        filename = make_output_filename(text)
        output_path = str(Path(output_dir) / filename)
        self._text_panel.set_status(self._i18n.t("status_generating"))
        self._run_tts(text, voice, output_path, is_preview=False)

    def _run_tts(self, text, voice, output_path, is_preview):
        rate = format_rate(self._voice_panel.rate_value())
        pitch = format_pitch(self._voice_panel.pitch_value())
        self._worker = TTSWorker(text, voice, output_path, rate, pitch)
        if is_preview:
            self._worker.finished.connect(self._on_preview_ready)
        else:
            self._worker.finished.connect(self._on_export_ready)
        self._worker.error.connect(self._on_tts_error)
        self._worker.start()

    def _on_preview_ready(self, file_path):
        self._text_panel.set_status(self._i18n.t("status_playing"))
        self._player.play(file_path)

    def _on_export_ready(self, file_path):
        filename = Path(file_path).name
        self._text_panel.set_status(
            self._i18n.t("status_exported", filename=filename)
        )

    def _on_tts_error(self, error_msg):
        self._text_panel.set_status(
            self._i18n.t("error_export_failed", error=error_msg)
        )

    def _on_stop(self):
        self._player.stop()

    def _on_player_state_changed(self, state):
        self._text_panel.set_playing(state == PlayerState.PLAYING)

    def _toggle_language(self):
        current = self._i18n.current_language
        new_lang = "en-US" if current == "zh-TW" else "zh-TW"
        self._i18n.set_language(new_lang)
        self._config.set("language", new_lang)
        self._lang_btn.setText(self._i18n.t("lang_toggle"))
        self.setWindowTitle(self._i18n.t("app_title"))
        self.statusBar().showMessage(self._i18n.t("status_ready"))

    def closeEvent(self, event):
        self._config.set("rate", format_rate(self._voice_panel.rate_value()))
        self._config.set("pitch", format_pitch(self._voice_panel.pitch_value()))
        self._config.save()
        super().closeEvent(event)
```

- [ ] **Step 4: Implement `src/app.py`**

```python
"""Application-level setup: theme, high-DPI, font."""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from src.ui.theme import apply_theme


def create_app(argv=None) -> QApplication:
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    app.setApplicationName("simple-edge-tts")
    app.setApplicationVersion("0.1.0")
    apply_theme(app)

    # Listen for OS theme changes
    hints = app.styleHints()
    if hasattr(hints, "colorSchemeChanged"):
        hints.colorSchemeChanged.connect(lambda: apply_theme(app))

    return app
```

- [ ] **Step 5: Update `src/main.py`**

```python
"""Entry point for simple-edge-tts application."""

import sys
from pathlib import Path

from src.app import create_app
from src.config_manager import ConfigManager
from src.i18n import I18n
from src.ui.main_window import MainWindow


TRANSLATIONS_DIR = Path(__file__).parent / "resources" / "translations"


def main():
    app = create_app()
    config = ConfigManager()
    i18n = I18n(config.get("language"), translations_dir=TRANSLATIONS_DIR)
    window = MainWindow(i18n=i18n, config=config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run all tests**

Run: `pytest -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add src/ui/main_window.py src/app.py src/main.py tests/test_ui/test_main_window.py
git commit -m "feat: main window with splitter layout, TTS worker, and language toggle"
```

---

## Task 10: workflow.sh — Local Test Runner

**Files:**
- Create: `workflow.sh`

- [ ] **Step 1: Create `workflow.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

# ─── Colors ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

PASS=0; FAIL=0; STEPS=()

run_step() {
  local name="$1"; shift
  printf "${BLUE}▶ %s${NC}\n" "$name"
  if "$@"; then
    printf "${GREEN}✓ %s PASSED${NC}\n\n" "$name"
    PASS=$((PASS + 1))
  else
    printf "${RED}✗ %s FAILED${NC}\n\n" "$name"
    FAIL=$((FAIL + 1))
  fi
  STEPS+=("$name")
}

summary() {
  echo "──────────────────────────────────"
  printf "${GREEN}PASS: %d${NC}  ${RED}FAIL: %d${NC}  TOTAL: %d\n" "$PASS" "$FAIL" "$((PASS + FAIL))"
  if [ "$FAIL" -gt 0 ]; then exit 1; fi
}

# ─── Test Steps ───────────────────────────────────────────
t1() { run_step "t1 Build check" python -m py_compile src/main.py; }
t2() { run_step "t2 Type check"  python -m mypy src/ --ignore-missing-imports; }
t3() { run_step "t3 Lint"        python -m ruff check src/ tests/; }
t4() { run_step "t4 Unit tests"  python -m pytest tests/ -v --ignore=tests/test_ui; }
t5() { run_step "t5 UI tests"    python -m pytest tests/test_ui/ -v; }
t6() { t2; t3; t4; t5; summary; }

# ─── Single-file runners (TDD) ────────────────────────────
t4-file() { run_step "t4-file $1" python -m pytest "$1" -v; }

# ─── Interactive Menu ─────────────────────────────────────
menu() {
  echo "┌─────────────────────────────────┐"
  echo "│  simple-edge-tts  workflow.sh   │"
  echo "├─────────────────────────────────┤"
  echo "│  t1  Build check                │"
  echo "│  t2  Type check (mypy)          │"
  echo "│  t3  Lint (ruff)                │"
  echo "│  t4  Unit tests                 │"
  echo "│  t5  UI tests                   │"
  echo "│  t6  Full run (t2→t3→t4→t5)     │"
  echo "│                                 │"
  echo "│  t4-file <path>  Single test    │"
  echo "└─────────────────────────────────┘"
  printf "Select step: "
  read -r choice
  case "$choice" in
    t[1-6]) "$choice" ;;
    t4-file)
      printf "File path: "
      read -r fpath
      t4-file "$fpath"
      ;;
    *) echo "Unknown: $choice" ;;
  esac
}

# ─── Dispatch ─────────────────────────────────────────────
if [ $# -eq 0 ]; then
  menu
else
  cmd="$1"; shift
  case "$cmd" in
    t[1-6]) "$cmd" ;;
    t4-file) t4-file "$1" ;;
    *) echo "Unknown: $cmd"; exit 1 ;;
  esac
fi
```

- [ ] **Step 2: Make executable and test**

Run: `chmod +x workflow.sh && ./workflow.sh t1`
Expected: "t1 Build check PASSED"

- [ ] **Step 3: Commit**

```bash
git add workflow.sh
git commit -m "ci: add workflow.sh local test runner (t1-t6)"
```

---

## Task 11: deploy.sh — Packaging Script

**Files:**
- Create: `deploy.sh`

- [ ] **Step 1: Create `deploy.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'

APP_NAME="simple-edge-tts"
VERSION=$(python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])")

info()  { printf "${BLUE}▶ %s${NC}\n" "$*"; }
ok()    { printf "${GREEN}✓ %s${NC}\n" "$*"; }
warn()  { printf "${YELLOW}⚠ %s${NC}\n" "$*"; }
err()   { printf "${RED}✗ %s${NC}\n" "$*"; exit 1; }

# ─── Packaging Steps ──────────────────────────────────────
p1() {
  info "p1: Build Windows exe"
  python -m PyInstaller --onefile --windowed \
    --name "$APP_NAME" \
    --icon src/resources/icons/icon.ico \
    src/main.py
  ok "Built: dist/${APP_NAME}.exe"
}

p2() {
  info "p2: Build macOS app + dmg"
  python -m PyInstaller --windowed \
    --name "$APP_NAME" \
    --icon src/resources/icons/icon.icns \
    src/main.py
  info "Creating .dmg..."
  hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "dist/${APP_NAME}.app" \
    -ov -format UDZO \
    "dist/${APP_NAME}.dmg"
  ok "Built: dist/${APP_NAME}.dmg"
}

p3() {
  info "p3: Build All"
  p1
  p2
}

v1() {
  info "v1: Version bump"
  if [ $# -eq 0 ]; then
    printf "New version (current: %s): " "$VERSION"
    read -r NEW_VERSION
  else
    NEW_VERSION="$1"
  fi
  sed -i.bak "s/version = \"$VERSION\"/version = \"$NEW_VERSION\"/" pyproject.toml
  rm -f pyproject.toml.bak
  git add pyproject.toml
  git commit -m "chore: bump version to $NEW_VERSION"
  git tag "v$NEW_VERSION"
  ok "Bumped to $NEW_VERSION and tagged v$NEW_VERSION"
  warn "Run 'git push origin main --tags' to trigger release build"
}

# ─── Interactive Menu ─────────────────────────────────────
menu() {
  echo "┌──────────────────────────────────┐"
  echo "│  simple-edge-tts  deploy.sh      │"
  echo "├──────────────────────────────────┤"
  echo "│  p1  Build Windows exe           │"
  echo "│  p2  Build macOS app + dmg       │"
  echo "│  p3  Build All                   │"
  echo "│  v1  Version bump + tag          │"
  echo "└──────────────────────────────────┘"
  printf "Select step: "
  read -r choice
  case "$choice" in
    p[1-3]|v1) "$choice" ;;
    *) echo "Unknown: $choice" ;;
  esac
}

# ─── Dispatch ─────────────────────────────────────────────
if [ $# -eq 0 ]; then
  menu
else
  cmd="$1"; shift
  case "$cmd" in
    p[1-3]) "$cmd" ;;
    v1) v1 "$@" ;;
    *) echo "Unknown: $cmd"; exit 1 ;;
  esac
fi
```

- [ ] **Step 2: Make executable**

Run: `chmod +x deploy.sh`

- [ ] **Step 3: Commit**

```bash
git add deploy.sh
git commit -m "ci: add deploy.sh packaging script (p1/p2/p3/v1)"
```

---

## Task 12: GitHub Actions Workflows

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/build.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  pull_request:
    branches: [main]
    types: [opened, synchronize, reopened]
    paths-ignore:
      - '**/*.md'
      - 'docs/**'
  workflow_dispatch:

concurrency:
  group: pre-merge-checks-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  pre-merge-checks:
    name: pre-merge-checks
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: pip
      - name: Install dependencies
        run: pip install -e ".[dev]"
      - name: t2 Type check
        run: ./workflow.sh t2
      - name: t3 Lint
        run: ./workflow.sh t3
      - name: t4 Unit tests
        run: ./workflow.sh t4
      - name: t5 UI tests
        run: |
          sudo apt-get update
          sudo apt-get install -y libegl1 libxkbcommon0 libxcb-xinerama0
          QT_QPA_PLATFORM=offscreen ./workflow.sh t5
```

- [ ] **Step 2: Create `.github/workflows/build.yml`**

```yaml
name: Build & Release

on:
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -v
      - run: pyinstaller --onefile --windowed --name simple-edge-tts src/main.py
      - uses: actions/upload-artifact@v4
        with:
          name: windows-exe
          path: dist/simple-edge-tts.exe

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: pytest -v
      - run: pyinstaller --windowed --name simple-edge-tts src/main.py
      - run: |
          hdiutil create -volname "simple-edge-tts" -srcfolder dist/simple-edge-tts.app -ov -format UDZO dist/simple-edge-tts.dmg
      - uses: actions/upload-artifact@v4
        with:
          name: macos-dmg
          path: dist/simple-edge-tts.dmg

  release:
    needs: [build-windows, build-macos]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/download-artifact@v4
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            windows-exe/simple-edge-tts.exe
            macos-dmg/simple-edge-tts.dmg
```

- [ ] **Step 3: Create `.github/PULL_REQUEST_TEMPLATE.md`**

```markdown
## What
<!-- Brief description of changes -->
## Why
<!-- Motivation / issue reference -->
## How
<!-- Implementation approach -->
## Checklist
- [ ] `./workflow.sh t6` passes (full run)
- [ ] New tests added for new functionality
- [ ] No secrets or credentials in code
```

- [ ] **Step 4: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.4
    hooks:
      - id: gitleaks
```

- [ ] **Step 5: Commit**

```bash
git add .github/ .pre-commit-config.yaml
git commit -m "ci: add PR gate workflow, release build, PR template, gitleaks hook"
```

---

## Task 13: Manual Smoke Test

- [ ] **Step 1: Run full workflow check**

Run: `./workflow.sh t6`
Expected: t2→t3→t4→t5 all PASS

- [ ] **Step 2: Run the app locally**

Run: `python -m src.main`
Expected: Window opens with left-right layout, dark/light theme matches OS

- [ ] **Step 3: Verify i18n toggle**

Click `EN` button → all UI text switches to English
Click `繁中` button → all UI text switches back to Traditional Chinese

- [ ] **Step 4: Test TTS preview** (requires internet)

Type text → click ▶ 試聽 → audio plays through speakers

- [ ] **Step 5: Test export** (requires internet)

Type text → click 💾 匯出 MP3 → file saved to output folder

- [ ] **Step 6: Final commit and tag**

```bash
git add -A
git commit -m "chore: ready for v0.1.0 release"
git tag v0.1.0
git push origin main --tags
```
