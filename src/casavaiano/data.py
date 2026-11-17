import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from casavaiano.config import STRUCTURED_DIR

Season = Literal["low", "mid", "high"]
UnitKind = Literal["room", "apartment"]


class Unit(BaseModel):
    id: str
    name: str
    kind: UnitKind
    description: str
    max_guests: int
    size_m2: int
    extra_bed: bool
    pets_allowed: bool
    accessible: bool
    prices: dict[Season, int]


class Period(BaseModel):
    start: str
    end: str
    season: Season | None = None
    label: str | None = None
    reason: str | None = None

    def contains(self, day: date) -> bool:
        md = (day.month, day.day)
        start, end = _month_day(self.start), _month_day(self.end)
        if start <= end:
            return start <= md <= end
        return md >= start or md <= end


class Fees(BaseModel):
    extra_bed_per_night: float
    dog_per_night: float
    apartment_breakfast_per_person: float
    tourist_tax_per_person_per_night: float
    tourist_tax_max_nights: int
    tourist_tax_exempt_under_age: int
    long_stay_min_nights: int
    long_stay_discount_pct: float
    deposit_pct: float
    free_cancellation_days: int
    late_cancellation_pct: float


class SeasonCalendar(BaseModel):
    closed: list[Period]
    periods: list[Period]
    min_stay: dict[UnitKind, dict[Season, int]]
    fees: Fees

    def is_open(self, day: date) -> bool:
        return not any(p.contains(day) for p in self.closed)

    def season_for(self, day: date) -> Season:
        if not self.is_open(day):
            raise ValueError(f"CasaVaiano is closed on {day.isoformat()}")
        for period in self.periods:
            if period.contains(day):
                return period.season
        raise ValueError(f"No season defined for {day.isoformat()}")


class Booking(BaseModel):
    unit: str
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def _check_dates(self):
        if self.check_out <= self.check_in:
            raise ValueError(f"check_out must be after check_in: {self}")
        return self

    def overlaps(self, check_in: date, check_out: date) -> bool:
        return self.check_in < check_out and check_in < self.check_out


class ExclusiveUse(Booking):
    unit: str = "*"
    reason: str


class Calendar(BaseModel):
    bookings: list[Booking]
    exclusive_use: list[ExclusiveUse]


def nights(check_in: date, check_out: date) -> list[date]:
    return [check_in + timedelta(days=i) for i in range((check_out - check_in).days)]


def _month_day(value: str) -> tuple[int, int]:
    month, day = value.split("-")
    return int(month), int(day)


@lru_cache
def load_units(directory: Path = STRUCTURED_DIR) -> dict[str, Unit]:
    raw = yaml.safe_load((directory / "rooms.yaml").read_text(encoding="utf-8"))
    return {u["id"]: Unit(**u) for u in raw["units"]}


@lru_cache
def load_seasons(directory: Path = STRUCTURED_DIR) -> SeasonCalendar:
    raw = yaml.safe_load((directory / "seasons.yaml").read_text(encoding="utf-8"))
    return SeasonCalendar(**raw)


@lru_cache
def load_calendar(directory: Path = STRUCTURED_DIR) -> Calendar:
    raw = json.loads((directory / "availability.json").read_text(encoding="utf-8"))
    return Calendar(**raw)
