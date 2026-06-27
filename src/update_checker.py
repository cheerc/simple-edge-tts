"""Check GitHub Releases for new versions on startup.

Simple detect-only: no auto-download/install. Returns update info
dict if newer version is available, None otherwise.

Ref: T24 — Auto-update detect + notify
"""

import json
import logging
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/cheerc/simple-edge-tts/releases/latest"


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
        """Fetch latest release info. Returns dict or None."""
        try:
            req = Request(GITHUB_API_URL, headers={"User-Agent": f"simple-edge-tts/{self.current_version}"})
            with urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            latest = tag.lstrip("v")
            if compare_versions(self.current_version, latest):
                return {
                    "latest": latest,
                    "url": data.get("html_url", GITHUB_API_URL),
                }
        except Exception:
            logger.debug("Update check failed", exc_info=True)
        return None

    def check(self) -> dict | None:
        """Check for updates, respecting skip_version.

        Returns:
            {'latest': str, 'url': str} if newer non-skipped version available,
            None otherwise.
        """
        result = self._check()
        if result and not self._should_skip(result["latest"]):
            return result
        return None
