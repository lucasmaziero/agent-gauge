"""User preferences, in the per-user config directory of whatever OS is running.

See `paths.config_dir` for the three locations.
"""
from __future__ import annotations

import contextlib
import json
import math
from pathlib import Path

from .paths import config_dir, config_file
from .storage import atomic_write

CONFIG_DIR = config_dir()
CONFIG_FILE = config_file()

MIN_POLL = 30
MAX_POLL = 900

DEFAULTS: dict = {
    "pos_x": None,          # None: park in the bottom-right corner
    "pos_y": None,
    "poll_sec": 120,        # fresh enough to act on, cheap enough to ignore
    "opacity": 0.96,
    "locked": False,        # ignore dragging
    "widget_visible": True,
    "compact": False,       # ring only, no text rows
    "language": "auto",     # auto follows the system; "en" or "pt_BR" pin it
    "alert_at": 80,         # notify once per window at this percent; 0 is off
    "provider": "claude",   # which agent to watch; see providers/
}


class Settings(dict):
    """Dict of preferences that loads on construction and saves on demand."""

    def __init__(self, path: Path = CONFIG_FILE) -> None:
        super().__init__(DEFAULTS)
        self.path = path
        self.load()

    def load(self) -> None:
        """Merge stored values over the defaults; unknown keys are dropped."""
        try:
            stored = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(stored, dict):
            return
        for key in DEFAULTS:
            value = stored.get(key, DEFAULTS[key])
            if key in ("pos_x", "pos_y"):
                valid = value is None or type(value) is int
            elif key in ("poll_sec", "alert_at"):
                valid = type(value) is int
            elif key == "opacity":
                valid = type(value) in (int, float) and math.isfinite(value)
            else:
                valid = type(value) is type(DEFAULTS[key])
            if valid:
                self[key] = value
        self["poll_sec"] = min(max(int(self["poll_sec"]), MIN_POLL), MAX_POLL)
        self["opacity"] = min(max(self["opacity"], 0.1), 1.0)
        self["alert_at"] = min(max(self["alert_at"], 0), 100)
        if self["language"] not in ("auto", "en", "pt_BR"):
            self["language"] = DEFAULTS["language"]
        if self["provider"] not in ("claude", "codex"):
            self["provider"] = DEFAULTS["provider"]

    def save(self) -> None:
        with contextlib.suppress(OSError):
            atomic_write(self.path, json.dumps(dict(self), indent=2))
