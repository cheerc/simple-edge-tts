"""Shared SSL context for outbound HTTPS in frozen builds.

Ref: #216/#218 — PyInstaller bundles can't find system CA roots
(CERTIFICATE_VERIFY_FAILED); certifi ships as an edge-tts/aiohttp
transitive dep, so point ssl at it explicitly. Ref: #228 — extracted
here so update_checker and update_manager share one implementation.
"""

import ssl


def ssl_context() -> ssl.SSLContext:
    """Return an SSL context trusting certifi's CA bundle."""
    import certifi

    return ssl.create_default_context(cafile=certifi.where())
