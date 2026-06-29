"""Application context dataclass for lifecycle management.

Ref: #140 — Replaces the 4-parameter lambda in SystemTrayManager
shutdown with a single context object, reducing coupling and
simplifying future component additions.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class AppContext:
    """Holds references to core application objects.

    Used by shutdown handlers (execute_quit_shutdown, execute_window_closing_shutdown,
    _run_cleanup) to access audio_player, api, tray, and window through a single
    parameter instead of four separate arguments.

    Fields are initialized as None and populated during main() startup.
    """

    audio_player: Any = None
    api: Any = None
    tray: Any = None
    window: Any = None
