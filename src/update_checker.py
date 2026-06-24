"""Check GitHub Releases for new versions on startup."""

import json
import logging
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com/repos/cheerc/simple-edge-tts/releases/latest"


def compare_versions(current: str, latest: str) -> bool:
    """Return True if latest is newer than current (semver)."""
    def parse(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    return parse(latest) > parse(current)


class UpdateChecker(QThread):
    """Background thread that checks GitHub for a newer release."""

    update_available = Signal(dict)  # {"latest": str, "url": str}

    def __init__(self, current_version: str, skip_version: str | None = None):
        super().__init__()
        self.current_version = current_version
        self.skip_version = skip_version

    def _should_skip(self, version: str) -> bool:
        """Return True if this version should be suppressed."""
        return self.skip_version is not None and version.lstrip("v") == self.skip_version

    def _check(self) -> dict | None:
        """Fetch latest release info. Returns dict or None."""
        try:
            req = Request(GITHUB_API_URL, headers={"User-Agent": "simple-edge-tts"})
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

    def run(self):
        """QThread entry point."""
        result = self._check()
        if result and not self._should_skip(result["latest"]):
            self.update_available.emit(result)
