"""Check GitHub Releases for new versions on startup.

Simple detect-only: no auto-download/install. Returns update info
dict if newer version is available, None otherwise.

Ref: T24 — Auto-update detect + notify
"""

import json
import logging
import ssl
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/cheerc/simple-edge-tts/releases/latest"


def _ssl_context() -> ssl.SSLContext:
    """Return an SSL context trusting certifi's CA bundle.

    Ref: #216 — frozen (PyInstaller) builds can't find system CA roots
    (CERTIFICATE_VERIFY_FAILED). certifi ships as an edge-tts/aiohttp
    transitive dep and is already bundled, so point ssl at it explicitly.
    """
    import certifi

    return ssl.create_default_context(cafile=certifi.where())


def compare_versions(current: str, latest: str) -> bool:
    """Return True if latest is newer than current (semver)."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    return parse(latest) > parse(current)


class UpdateChecker:
    """Check GitHub for a newer release (no PySide6 dependency)."""

    def __init__(self, current_version: str, skip_version: str | None = None):
        self.current_version = current_version
        self.skip_version = skip_version

    def _should_skip(self, version: str) -> bool:
        """Return True if this version should be suppressed."""
        return self.skip_version is not None and version.lstrip("v") == self.skip_version

    def _check(self) -> dict | None:
        """Fetch latest release info. Returns dict, or raises on network failure.

        Ref: #216 — network errors propagate to the caller instead of being
        swallowed into None; None must only mean "no newer version" so the
        frontend never reports 'up to date' for a failed check.
        """
        req = Request(GITHUB_API_URL, headers={"User-Agent": f"simple-edge-tts/{self.current_version}"})
        with urlopen(req, timeout=5, context=_ssl_context()) as resp:
            data = json.loads(resp.read())
        tag = data.get("tag_name", "")
        latest = tag.lstrip("v")
        if compare_versions(self.current_version, latest):
            return {
                "latest": latest,
                "url": data.get("html_url", GITHUB_API_URL),
            }
        return None

    def check(self) -> dict | None:
        """Check for updates, respecting skip_version.

        Returns:
            {'latest': str, 'url': str} if newer non-skipped version available.
        Raises:
            Exception on network/SSL failure (caller decides how to surface it;
            auto path stays fail-silent, manual path shows an error — #216).
            None is reserved for "up to date" / skipped.
        """
        try:
            result = self._check()
        except Exception as e:
            logger.warning("Update check failed: %s", e)
            raise
        if result and not self._should_skip(result["latest"]):
            return result
        return None
