"""Regression tests for frozen (PyInstaller) path resolution.

Ref: #66 — PyInstaller strips src/ prefix from __file__, making
Path(__file__).parent.parent resolve one level too high.
_get_base_dir() uses sys._MEIPASS when frozen to fix this.
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
