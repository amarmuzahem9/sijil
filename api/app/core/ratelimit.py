"""In-process sliding-window limiter for failed sign-ins per client IP (research.md R5).

Only failed attempts count, so an office of marketers sharing one public IP is not blocked by
normal sign-ins. Enough for a single API instance; no extra service needed (Principle VI).
"""

import math
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta

from app.core.timeutil import utc_now


class FailedAttemptLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[datetime]] = defaultdict(deque)

    def _prune(self, key: str, now: datetime, window: timedelta) -> deque[datetime]:
        events = self._events[key]
        while events and now - events[0] >= window:
            events.popleft()
        if not events:
            self._events.pop(key, None)
            return deque()
        return events

    def retry_after(self, key: str, limit: int, window: timedelta) -> int | None:
        """Seconds to wait if `key` has reached `limit` failures in `window`, else None."""
        now = utc_now()
        with self._lock:
            events = self._prune(key, now, window)
            if len(events) < limit:
                return None
            return max(1, math.ceil((events[0] + window - now).total_seconds()))

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._events[key].append(utc_now())

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


login_failures = FailedAttemptLimiter()
