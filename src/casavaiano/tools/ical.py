"""Read Slope's iCal calendars: one per apartment, all-day events = nights not available
(bookings and closures alike). Cached, fetched in parallel, last good copy kept on errors."""

import logging
import os
import re
import threading
import time
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

from dotenv import dotenv_values

from casavaiano.config import ROOT_DIR

log = logging.getLogger("casavaiano.ical")

PREFIX = "CASA_ICAL_"
_DATE = re.compile(r"(\d{8})")


def busy_nights(ics: str) -> set[date]:
    """Nights covered by the calendar's events. DTEND is exclusive, as in iCal."""
    nights: set[date] = set()
    for event in ics.replace("\r", "").split("BEGIN:VEVENT")[1:]:
        start = _field_date(event, "DTSTART")
        if start is None:
            continue
        end = _field_date(event, "DTEND") or start + timedelta(days=1)
        day = start
        while day < max(end, start + timedelta(days=1)):
            nights.add(day)
            day += timedelta(days=1)
    return nights


def _field_date(event: str, name: str) -> date | None:
    for line in event.split("\n"):
        if line.startswith(name):
            match = _DATE.search(line.split(":", 1)[-1])
            if match:
                raw = match.group(1)
                return date(int(raw[:4]), int(raw[4:6]), int(raw[6:]))
    return None


def ical_urls(env_file: Path = ROOT_DIR / ".env") -> dict[str, str]:
    """CASA_ICAL_GIRASOLE=https://... -> {"Girasole": url}, from .env and the environment."""
    values = {**dotenv_values(env_file), **os.environ} if env_file.exists() else dict(os.environ)
    return {
        key[len(PREFIX) :].replace("_", " ").title(): url
        for key, url in values.items()
        if key.startswith(PREFIX) and url
    }


def _http_get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "casavaiano-assistant"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


class IcalCalendars:
    def __init__(
        self,
        urls: dict[str, str],
        ttl_seconds: int = 900,
        fetch: Callable[[str], str] = _http_get,
    ):
        self.urls = urls
        self.ttl = ttl_seconds
        self.fetch = fetch
        self._busy: dict[str, set[date]] = {}
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def busy(self) -> dict[str, set[date] | None]:
        """Busy nights per apartment; None for an apartment whose calendar was never readable."""
        with self._lock:
            if time.monotonic() - self._fetched_at > self.ttl or not self._busy:
                self._refresh()
            return {name: self._busy.get(name) for name in self.urls}

    def _refresh(self) -> None:
        def load(item: tuple[str, str]) -> tuple[str, set[date] | None]:
            name, url = item
            try:
                return name, busy_nights(self.fetch(url))
            except Exception as exc:  # network or parse error: keep the last good copy
                log.warning("calendar %s not readable: %s", name, type(exc).__name__)
                return name, None

        with ThreadPoolExecutor(max_workers=8) as pool:
            for name, nights in pool.map(load, self.urls.items()):
                if nights is not None:
                    self._busy[name] = nights
        self._fetched_at = time.monotonic()
