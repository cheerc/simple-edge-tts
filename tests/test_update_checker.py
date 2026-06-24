"""Tests for update_checker — GitHub Releases version check."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.update_checker import UpdateChecker, compare_versions


class TestCompareVersions:
    """Test semantic version comparison."""

    def test_newer_version_available(self):
        assert compare_versions("0.1.0", "0.2.0") is True

    def test_same_version(self):
        assert compare_versions("0.1.0", "0.1.0") is False

    def test_older_version(self):
        assert compare_versions("0.2.0", "0.1.0") is False

    def test_major_bump(self):
        assert compare_versions("0.9.9", "1.0.0") is True

    def test_patch_bump(self):
        assert compare_versions("0.1.0", "0.1.1") is True

    def test_strips_v_prefix(self):
        assert compare_versions("0.1.0", "v0.2.0") is True


class TestUpdateChecker:
    """Test update check logic (network mocked)."""

    @patch("src.update_checker.urlopen")
    def test_newer_version_emits_signal(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/cheerc/simple-edge-tts/releases/tag/v0.2.0"
        }).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        checker = UpdateChecker(current_version="0.1.0")
        result = checker._check()
        assert result is not None
        assert result["latest"] == "0.2.0"
        assert "releases" in result["url"]

    @patch("src.update_checker.urlopen")
    def test_same_version_returns_none(self, mock_urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps({"tag_name": "v0.1.0"}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        checker = UpdateChecker(current_version="0.1.0")
        assert checker._check() is None

    @patch("src.update_checker.urlopen", side_effect=Exception("no internet"))
    def test_network_error_returns_none(self, mock_urlopen):
        checker = UpdateChecker(current_version="0.1.0")
        assert checker._check() is None

    def test_skip_version(self):
        checker = UpdateChecker(current_version="0.1.0", skip_version="0.2.0")
        # Even if API returns 0.2.0, skip_version suppresses it
        assert checker._should_skip("0.2.0") is True
        assert checker._should_skip("0.3.0") is False
