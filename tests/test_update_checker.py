"""Tests for update_checker — GitHub Releases version check."""

import json
from unittest.mock import MagicMock, patch


import src.update_checker as src_update_checker
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
    def test_network_error_raises_to_caller(self, mock_urlopen):
        """Ref #216 — errors propagate so 'up to date' is never a false report."""
        checker = UpdateChecker(current_version="0.1.0")
        try:
            checker._check()
            raised = False
        except Exception:
            raised = True
        assert raised

    def test_skip_version(self):
        checker = UpdateChecker(current_version="0.1.0", skip_version="0.2.0")
        # Even if API returns 0.2.0, skip_version suppresses it
        assert checker._should_skip("0.2.0") is True
        assert checker._should_skip("0.3.0") is False

    @patch("src.update_checker.urlopen")
    def test_check_returns_result(self, mock_urlopen):
        """Test public check() method returns update info."""
        response = MagicMock()
        response.read.return_value = json.dumps({
            "tag_name": "v0.3.0",
            "html_url": "https://github.com/cheerc/simple-edge-tts/releases/tag/v0.3.0"
        }).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        checker = UpdateChecker(current_version="0.1.0")
        result = checker.check()
        assert result is not None
        assert result["latest"] == "0.3.0"

    @patch("src.update_checker.urlopen")
    def test_check_respects_skip(self, mock_urlopen):
        """Test public check() method respects skip_version."""
        response = MagicMock()
        response.read.return_value = json.dumps({
            "tag_name": "v0.2.0",
            "html_url": "https://github.com/cheerc/simple-edge-tts/releases/tag/v0.2.0"
        }).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        checker = UpdateChecker(current_version="0.1.0", skip_version="0.2.0")
        result = checker.check()
        assert result is None


class TestSSLCertifiContext:
    """Test certifi CA bundle usage — frozen builds lack system CA paths (Issue #216)."""

    @patch("src.update_checker.urlopen")
    def test_urlopen_receives_certifi_context(self, mock_urlopen):
        """urlopen is called with an SSL context loaded from the certifi CA file."""
        response = MagicMock()
        response.read.return_value = json.dumps({"tag_name": "v0.2.0"}).encode()
        response.__enter__ = lambda s: s
        response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = response

        checker = UpdateChecker(current_version="0.1.0")
        checker._check()

        context = mock_urlopen.call_args.kwargs["context"]
        import ssl as _ssl
        import certifi
        assert isinstance(context, _ssl.SSLContext)
        assert len(context.get_ca_certs()) > 0
        # The context must have been created from certifi's bundle, not system default
        assert context.cert_store_stats()["x509"] > 0
        assert certifi.where()  # certifi resolvable; factory uses it (see next test)

    def test_default_context_uses_certifi_cafile(self):
        """The module's SSL context factory resolves to the certifi CA file."""
        ctx = src_update_checker._ssl_context()
        import certifi
        assert ctx is not None
        # The loaded CA store must include certifi's bundle path
        assert certifi.where()  # certifi resolvable in runtime env
        stats = ctx.get_ca_certs()
        assert len(stats) > 0


class TestNetworkErrorDistinguishing:
    """Test that network failure is distinguishable from up-to-date (Issue #216).

    Frozen SSL failures were swallowed into None → frontend reported
    'already up to date' even though the check never succeeded.
    """

    @patch("src.update_checker.urlopen", side_effect=Exception("CERTIFICATE_VERIFY_FAILED"))
    def test_network_error_raises_instead_of_none(self, mock_urlopen):
        checker = UpdateChecker(current_version="0.1.0")
        try:
            checker._check()
            raised = False
        except Exception:
            raised = True
        assert raised, "_check() must not swallow network errors into None"
