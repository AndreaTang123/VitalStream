"""Minimal login throttle (PRD 5.3's "basic rate limiting").

In-process fixed-window counter, not Redis-backed — this project runs the
api service as a single process, so a shared counter would be over-
engineering for what's meant to blunt naive credential-stuffing, not survive
a multi-instance deployment (a real HA deployment would move this to Redis,
same as insight_service's cache).
"""

from __future__ import annotations

import time
from collections import defaultdict

from api.settings import settings

_attempts: dict[str, list[float]] = defaultdict(list)


def check_login_rate_limit(key: str) -> bool:
    """Returns True if `key` (typically the attempted email) is still under
    the limit, and records this attempt. Call once per login POST."""
    now = time.monotonic()
    window_start = now - settings.login_rate_limit_window_seconds
    attempts = [t for t in _attempts[key] if t >= window_start]
    attempts.append(now)
    _attempts[key] = attempts
    return len(attempts) <= settings.login_rate_limit_attempts
