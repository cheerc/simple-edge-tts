"""Regression tests for frozen (PyInstaller) path resolution.

Ref: #66 — PyInstaller strips src/ prefix from __file__, making
Path(__file__).parent.parent resolve one level too high.
_get_base_dir() uses sys._MEIPASS when frozen to fix this.

Ref: #175 — Build verification workflow.
Tests for _get_app_version() fallback chain + core module import smoke.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.main import _get_base_dir, _is_dev_mode


class TestGetBaseDir:
    """Tests for _get_base_dir() helper."""

    def test_unfrozen_returns_project_root(self):
        """In dev mode (not frozen), returns Path(__file__).parent.parent."""
        result = _get_base_dir()
        # Should be the project root (parent of parent of src/main.py)
        assert result.is_absolute()
        assert (result / "src").is_dir()

    def test_frozen_returns_meipass(self, tmp_path):
        """In frozen mode, returns Path(sys._MEIPASS)."""
        import sys as real_sys

        fake_meipass = str(tmp_path / "_internal")

        original_frozen = getattr(real_sys, "frozen", None)
        original_meipass = getattr(real_sys, "_MEIPASS", None)
        try:
            real_sys.frozen = True
            real_sys._MEIPASS = fake_meipass
            result = _get_base_dir()
            assert result == Path(fake_meipass)
        finally:
            if original_frozen is None:
                if hasattr(real_sys, "frozen"):
                    del real_sys.frozen
            else:
                real_sys.frozen = original_frozen
            if original_meipass is None:
                if hasattr(real_sys, "_MEIPASS"):
                    del real_sys._MEIPASS
            else:
                real_sys._MEIPASS = original_meipass


class TestIsDevMode:
    """Tests for _is_dev_mode() behavior in frozen vs unfrozen mode."""

    def test_dev_env_var_forces_dev_mode(self, monkeypatch):
        """SIMPLE_EDGE_TTS_DEV env var always returns True."""
        monkeypatch.setenv("SIMPLE_EDGE_TTS_DEV", "1")
        assert _is_dev_mode() is True

    def test_unfrozen_frontend_exists_not_dev(self, monkeypatch):
        """Unfrozen + frontend exists → not dev mode."""
        monkeypatch.delenv("SIMPLE_EDGE_TTS_DEV", raising=False)
        with patch("src.main.FRONTEND_DIST") as mock_dist:
            mock_dist.exists.return_value = True
            assert _is_dev_mode() is False

    def test_unfrozen_frontend_missing_is_dev(self, monkeypatch):
        """Unfrozen + frontend missing → dev mode (fallback to Vite)."""
        monkeypatch.delenv("SIMPLE_EDGE_TTS_DEV", raising=False)
        with patch("src.main.FRONTEND_DIST") as mock_dist:
            mock_dist.exists.return_value = False
            assert _is_dev_mode() is True

    def test_frozen_frontend_exists_not_dev(self, monkeypatch):
        """Frozen + frontend exists → not dev mode."""
        import sys as real_sys

        monkeypatch.delenv("SIMPLE_EDGE_TTS_DEV", raising=False)
        monkeypatch.setattr(real_sys, "frozen", True, raising=False)
        with patch("src.main.FRONTEND_DIST") as mock_dist:
            mock_dist.exists.return_value = True
            assert _is_dev_mode() is False

    def test_frozen_frontend_missing_raises(self, monkeypatch):
        """Frozen + frontend missing → RuntimeError (not silent fallback).

        Ref: #66 — silent fallback to dev server hid the broken path.
        """
        import sys as real_sys

        monkeypatch.delenv("SIMPLE_EDGE_TTS_DEV", raising=False)
        monkeypatch.setattr(real_sys, "frozen", True, raising=False)
        monkeypatch.setattr(real_sys, "_MEIPASS", "/fake/meipass", raising=False)
        with patch("src.main.FRONTEND_DIST") as mock_dist:
            mock_dist.exists.return_value = False
            mock_dist.__str__ = lambda self: "/fake/path/index.html"
            with pytest.raises(RuntimeError, match="Packaged frontend not found"):
                _is_dev_mode()


# ---------------------------------------------------------------------------
# Ref: #175 — _get_app_version() fallback chain tests
# ---------------------------------------------------------------------------


class TestGetAppVersion:
    """_get_app_version() has a 3-tier fallback for frozen builds."""

    def test_importlib_metadata_works_in_dev(self):
        """In dev mode, importlib.metadata returns the real version."""
        from src.api import Api

        ver = Api._get_app_version()
        assert ver != "0.0.0", f"Expected real version, got {ver}"
        # Should match pyproject.toml version format
        assert "." in ver

    def test_fallback_to_pyproject_toml_when_metadata_fails(self, monkeypatch):
        """When importlib.metadata raises, fallback reads pyproject.toml."""
        import importlib.metadata

        def _mock_version(_pkg):
            raise importlib.metadata.PackageNotFoundError

        monkeypatch.setattr(importlib.metadata, "version", _mock_version)

        from src.api import Api

        ver = Api._get_app_version()
        # Falls through to pyproject.toml reader
        assert ver != "0.0.0"
        assert "." in ver

    def test_fallback_to_default_when_both_fail(self, monkeypatch):
        """When both metadata and pyproject.toml fail, returns '0.0.0'."""
        import importlib.metadata

        def _mock_version(_pkg):
            raise importlib.metadata.PackageNotFoundError

        monkeypatch.setattr(importlib.metadata, "version", _mock_version)

        # Also break the pyproject.toml fallback
        original_read_text = Path.read_text
        def _mock_read_text(self, *args, **kwargs):
            if self.name == "pyproject.toml":
                raise FileNotFoundError("Mocked missing pyproject.toml")
            return original_read_text(self, *args, **kwargs)
        monkeypatch.setattr(Path, "read_text", _mock_read_text)

        from src.api import Api

        ver = Api._get_app_version()
        assert ver == "0.0.0"


# ---------------------------------------------------------------------------
# Ref: #175 — Core module import smoke tests
# ---------------------------------------------------------------------------


class TestImportSmoke:
    """Verify all core modules can be imported without errors.

    This catches missing --hidden-import and circular import issues.
    """

    def test_import_api(self):
        import src.api  # noqa: F401

    def test_import_main(self):
        import src.main  # noqa: F401

    def test_import_update_manager(self):
        import src.update_manager  # noqa: F401

    def test_import_update_checker(self):
        import src.update_checker  # noqa: F401

    def test_import_tts_engine(self):
        import src.tts_engine  # noqa: F401

    def test_import_config_manager(self):
        import src.config_manager  # noqa: F401

    def test_import_i18n(self):
        import src.i18n  # noqa: F401
