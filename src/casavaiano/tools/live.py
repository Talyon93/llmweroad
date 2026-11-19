"""Real availability for the live site: Slope calendars, no prices (they change daily)."""

from dataclasses import dataclass
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

from casavaiano.config import DATA_DIR
from casavaiano.data import nights
from casavaiano.tools.ical import IcalCalendars
from casavaiano.tools.stay import _validate_dates

LODGINGS_PATH = DATA_DIR / "real" / "lodgings.yaml"
HIGH_SEASON_MONTHS = (7, 8)
SATURDAY = 5
MIN_NIGHTS = 3

PRICES_NOTE = (
    "Prices change every day (dynamic pricing). Never state a price: the guest sees the live "
    "price and can book at booking_url, or can ask for a personal quote."
)


@dataclass(frozen=True)
class Lodging:
    name: str
    size_m2: int
    capacity: int | None
    facts: str
    standard_guests: int | None = None
    floor: str | None = None


@lru_cache
def load_lodgings(path: Path = LODGINGS_PATH) -> tuple[Lodging, ...]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return tuple(Lodging(**item) for item in raw["lodgings"])


def in_high_season(check_in: date, check_out: date) -> bool:
    return any(n.month in HIGH_SEASON_MONTHS for n in nights(check_in, check_out))


def saturday_stay(check_in: date, check_out: date) -> tuple[date, date] | None:
    """In July and August stays go Saturday to Saturday, whole weeks. Returns the stay to check
    instead of the dates asked, or None when the dates asked are fine. Arrival moves to the
    nearest Saturday (Sunday-Tuesday: the one before; Wednesday-Friday: the one after)."""
    if not in_high_season(check_in, check_out):
        return None
    if check_in.weekday() == SATURDAY and check_out.weekday() == SATURDAY:
        return None
    since_saturday = (check_in.weekday() - SATURDAY) % 7
    if since_saturday <= 3:
        start = check_in - timedelta(days=since_saturday)
    else:
        start = check_in + timedelta(days=7 - since_saturday)
    weeks = max(1, round((check_out - check_in).days / 7))
    return start, start + timedelta(days=7 * weeks)


def check_availability_live(
    check_in: date,
    check_out: date,
    guests: int,
    today: date,
    calendars: IcalCalendars,
    booking_url: str,
    lodgings: tuple[Lodging, ...] | None = None,
) -> dict:
    _validate_dates(check_in, check_out, today)
    lodgings = lodgings or load_lodgings()
    result: dict = {"requested": {"check_in": str(check_in), "check_out": str(check_out)}}
    suggestion = saturday_stay(check_in, check_out)
    if suggestion:
        check_in, check_out = suggestion
        result["rule"] = "In July and August stays go Saturday to Saturday, whole weeks."
    elif (check_out - check_in).days < MIN_NIGHTS:
        result["min_stay"] = (
            f"The minimum stay is {MIN_NIGHTS} nights: these dates cannot be booked as they are. "
            "Ask the guest to extend the stay."
        )
    stay = set(nights(check_in, check_out))
    result |= {
        "checked": {"check_in": str(check_in), "check_out": str(check_out), "nights": len(stay)},
        "available": [],
        "not_available": [],
        "unknown": [],
    }
    busy = calendars.busy()
    for lodging in lodgings:
        nights_busy = busy.get(lodging.name)
        if nights_busy is None:
            result["unknown"].append(lodging.name)
        elif stay & nights_busy:
            result["not_available"].append(lodging.name)
        elif lodging.capacity is not None and guests > lodging.capacity:
            result["not_available"].append(f"{lodging.name} (sleeps {lodging.capacity})")
        else:
            entry = {"name": lodging.name, "size_m2": lodging.size_m2, "facts": lodging.facts}
            if lodging.capacity is None:
                entry["capacity"] = "not in the data: the owner confirms it for the party size"
            elif lodging.standard_guests and guests > lodging.standard_guests:
                entry["extra_bed"] = "needs the extra single bed (supplement on request)"
            result["available"].append(entry)
    result["prices"] = PRICES_NOTE
    result["booking_url"] = booking_url
    return result
