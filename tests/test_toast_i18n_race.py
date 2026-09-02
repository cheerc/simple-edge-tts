"""Regression test for #183 auto-update Toast i18n race.

Root cause: App.tsx startDownload used eager t("update_...") which
captures plain string at call time. When translations={} initially,
t(key) returns key itself; Toast stores plain string and never
re-renders after translations load (reactive {key} would re-resolve
via t at render time).

This test guards the frozen scope: all update-flow toasts must be
reactive {key: ...} and must not use eager t("update_...").
Ref: App.tsx:101-181, Toast.tsx:13-22, useI18n.ts:46-47
"""

import re
from pathlib import Path


APP_TSX = Path(__file__).parent.parent / "frontend" / "src" / "App.tsx"
TOAST_TSX = Path(__file__).parent.parent / "frontend" / "src" / "components" / "Toast.tsx"
TYPES_TS = Path(__file__).parent.parent / "frontend" / "src" / "types.ts"


def _read_app() -> str:
    return APP_TSX.read_text(encoding="utf-8")


class TestEagerVsReactiveGuard:
    """Static guard: no eager t(\"update_...\") in update flow."""

    def test_no_eager_t_for_update_keys_in_app(self):
        text = _read_app()
        # Any t("update_...") is forbidden — must be {key: "update_..."}
        eager = re.findall(r't\s*\(\s*["\']update_[^"\']+["\']\s*\)', text)
        assert eager == [], f"Found eager t() for update keys (must be reactive {{key}}): {eager}"

    def test_no_template_eager_progress(self):
        text = _read_app()
        # Forbidden: `${t("update_downloading")} ${progress...`
        assert '${t("update_downloading")}' not in text
        assert "${t('update_downloading')}" not in text
        # Also forbid t("update_verifying") eager
        assert 't("update_verifying")' not in text

    def test_reactive_keys_present(self):
        text = _read_app()
        # Required reactive keys
        for key in [
            'update_downloading',
            'update_verifying',
            'update_downloaded',
            'update_download_error',
            'update_cancel',
            'update_install_restart',
        ]:
            assert f'{{ key: "{key}" }}' in text or f"{{key: \"{key}\"}}" in text or f'key: "{key}"' in text, \
                f"Missing reactive key for {key}"

    def test_error_branch_keeps_backend_string_fallback(self):
        text = _read_app()
        # Error branch must allow backend string fallback, not always t()
        # Acceptable pattern: progress.error ? progress.error : { key: "update_download_error" }
        assert 'progress.error ? progress.error' in text
        assert '{ key: "update_download_error" }' in text

    def test_install_error_is_reactive_for_i18n_keys(self):
        text = _read_app()
        assert 'isI18nKey' in text or 'startsWith("update_")' in text
        assert '{ key: result.error }' in text or '{key: result.error' in text

    def test_start_download_no_t_dependency(self):
        text = _read_app()
        # After fix, startDownload no longer depends on t — dep array should not contain t
        # Extract startDownload dep array
        m = re.search(r'startDownload.*?\[([^\]]+)\]\)', text, re.DOTALL)
        if m:
            deps = m.group(1)
            # t should not be in deps for startDownload
            assert '"t"' not in deps and "'t'" not in deps and ", t," not in deps and " t," not in deps, \
                f"startDownload still depends on t: [{deps}]"

class TestToastReactiveContract:
    """Functional contract: Toast resolveMessage re-renders with new translations."""

    def _resolve_message(self, msg, translations):
        """Mirror Toast.tsx:13-22 logic in Python."""
        def t(key: str) -> str:
            return translations.get(key, key)
        if isinstance(msg, str):
            return msg
        text = t(msg["key"])
        params = msg.get("params") or {}
        for k, v in params.items():
            text = text.replace(f"{{{k}}}", v)
        return text

    def _resolve_action_label(self, label, translations):
        def t(key: str) -> str:
            return translations.get(key, key)
        if isinstance(label, str):
            return label
        return t(label["key"])

    def test_eager_string_never_updates_after_translations_load(self):
        # Simulate eager: captured when translations={}
        translations_empty: dict[str, str] = {}
        def t_empty(k: str) -> str:
            return translations_empty.get(k, k)
        eager_msg = t_empty("update_downloading")  # => "update_downloading"
        # Eager string stays key, never re-resolves (loaded translation ignored)
        assert eager_msg == "update_downloading"
        # Simulate still showing eager_msg (not re-resolved)
        assert eager_msg != "下載中..."

    def test_reactive_object_re_resolves_after_load(self):
        reactive = {"key": "update_downloading"}
        empty = {}
        loaded_zh = {"update_downloading": "下載中...", "update_verifying": "驗證中..."}
        loaded_en = {"update_downloading": "Downloading..."}
        # Initial render with empty -> key
        assert self._resolve_message(reactive, empty) == "update_downloading"
        # After load -> translation
        assert self._resolve_message(reactive, loaded_zh) == "下載中..."
        assert self._resolve_message(reactive, loaded_en) == "Downloading..."
        # Params variant
        reactive_params = {"key": "update_available", "params": {"version": "1.2.3"}}
        trans = {"update_available": "Version {version} available!"}
        assert self._resolve_message(reactive_params, trans) == "Version 1.2.3 available!"

    def test_reactive_action_label_also_updates(self):
        reactive_label = {"key": "update_cancel"}
        empty = {}
        loaded = {"update_cancel": "取消"}
        assert self._resolve_action_label(reactive_label, empty) == "update_cancel"
        assert self._resolve_action_label(reactive_label, loaded) == "取消"

    def test_all_update_phases_reactive(self):
        """Each phase's reactive key resolves correctly after load."""
        phases = [
            {"key": "update_downloading"},
            {"key": "update_verifying"},
            {"key": "update_downloaded"},
            {"key": "update_download_error"},
        ]
        zh = {
            "update_downloading": "下載中...",
            "update_verifying": "驗證中...",
            "update_downloaded": "已下載 — 可安裝",
            "update_download_error": "下載失敗",
        }
        for msg in phases:
            assert self._resolve_message(msg, zh) == zh[msg["key"]]
            # Empty must be raw key (proving eager would leak key)
            assert self._resolve_message(msg, {}) == msg["key"]

class TestToastTypesSupportReactive:
    def test_types_support_reactive(self):
        text = TYPES_TS.read_text(encoding="utf-8")
        assert "ToastMessage = string | { key: string" in text
        assert 'label: string | { key: string }' in text

    def test_toast_component_resolves_reactively(self):
        text = TOAST_TSX.read_text(encoding="utf-8")
        assert "resolveMessage" in text
        assert "typeof msg === \"string\"" in text
        assert "t(msg.key)" in text
        # Action labels also reactive
        assert 't(action.label.key)' in text
