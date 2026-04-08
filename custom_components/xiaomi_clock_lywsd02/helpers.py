"""Helper utilities for Xiaomi Clock Time Fixer."""
from __future__ import annotations

import homeassistant.util.dt as dt_util


def get_localized_timestamp() -> int:
    """Get the current timestamp as standard UTC epoch."""
    now = dt_util.now()
    # The LYWSD02 clock adds timezone offset internally. It expects standard UTC Unix time.
    return int(now.timestamp())


def get_tz_offset() -> int:
    """Get the timezone offset dynamically from Home Assistant."""
    now = dt_util.now()
    if now.utcoffset():
        return int(now.utcoffset().total_seconds() / 3600)
    return 0
