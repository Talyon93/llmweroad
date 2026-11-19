"""Abuse protection for the public endpoint: per-IP rate limits and a daily spend cap.

In process memory, like the chat memory: right for one Cloud Run instance."""

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import date

from fastapi import Request

MAX_KEYS = 20_000


class RateLimiter:
    """Sliding windows: each rule is (max_hits, window_seconds)."""

    def __init__(self, rules: list[tuple[int, int]], clock: Callable[[], float] = time.monotonic):
        self.rules = rules
        self.clock = clock
        self.longest = max(window for _, window in rules)
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> int | None:
        """Record a hit. Returns None if allowed, else the seconds to wait (nothing recorded)."""
        now = self.clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.longest:
                hits.popleft()
            for max_hits, window in self.rules:
                recent = [t for t in hits if now - t <= window]
                if len(recent) >= max_hits:
                    return max(1, int(window - (now - recent[0])) + 1)
            hits.append(now)
            if len(self._hits) > MAX_KEYS:
                stale = [k for k, v in self._hits.items() if not v or now - v[-1] > self.longest]
                for k in stale:
                    del self._hits[k]
            return None


class DailyBudget:
    """Stops the assistant for the rest of the day once the day's LLM spend reaches the limit."""

    def __init__(self, limit_usd: float, today: Callable[[], date] = date.today):
        self.limit = limit_usd
        self.today = today
        self._day = today()
        self._spent = 0.0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        if self.today() != self._day:
            self._day, self._spent = self.today(), 0.0

    def exceeded(self) -> bool:
        with self._lock:
            self._roll()
            return self.limit > 0 and self._spent >= self.limit

    def add(self, cost_usd: float) -> None:
        with self._lock:
            self._roll()
            self._spent += cost_usd

    @property
    def spent(self) -> float:
        with self._lock:
            self._roll()
            return round(self._spent, 4)


def client_ip(request: Request, trust_forwarded_for: bool) -> str:
    """The caller's IP. Behind Cloud Run every request comes from Google's front end, so the real
    client is the LAST X-Forwarded-For entry (appended by Google; earlier ones can be forged)."""
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[-1]
    return request.client.host if request.client else "unknown"
