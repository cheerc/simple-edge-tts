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
