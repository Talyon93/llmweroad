"""Availability and price quotes, computed from data/structured. The LLM never does this maths."""

from collections import Counter
from datetime import date

from casavaiano.data import (
    Unit,
    load_calendar,
    load_seasons,
    load_units,
    nights,
)

MAX_NIGHTS = 30
INFANT_MAX_AGE = 2


class ToolError(ValueError):
    pass


def check_availability(
    check_in: date, check_out: date, guests: int, dog: bool, today: date
) -> dict:
    stay = _validate_dates(check_in, check_out, today)
    seasons = load_seasons()
    closed = [n for n in stay if not seasons.is_open(n)]
    base = {"check_in": str(check_in), "check_out": str(check_out), "nights": len(stay)}
    if closed:
        return base | {
            "available": [],
            "reason": "closed",
            "detail": "CasaVaiano is closed from 7 January to the end of February.",
        }
    if any(e.overlaps(check_in, check_out) for e in load_calendar().exclusive_use):
        return base | {
            "available": [],
            "reason": "private_event",
            "detail": "The whole property is reserved for a private event on these dates.",
        }

    available, unavailable = [], {}
    arrival_season = seasons.season_for(check_in)
    for unit in load_units().values():
        min_nights = seasons.min_stay[unit.kind][arrival_season]
        if guests > _capacity(unit):
            unavailable[unit.id] = f"too small (max {_capacity(unit)} guests)"
        elif dog and not unit.pets_allowed:
            unavailable[unit.id] = "dogs not allowed"
        elif _is_booked(unit.id, check_in, check_out):
            unavailable[unit.id] = "booked"
        elif len(stay) < min_nights:
            unavailable[unit.id] = f"minimum stay {min_nights} nights"
        else:
            available.append(
                {
                    "unit": unit.id,
                    "name": unit.name,
                    "kind": unit.kind,
                    "max_guests": _capacity(unit),
                }
            )
    return base | {"available": available, "unavailable": unavailable}


def quote_stay(
    unit_id: str,
    check_in: date,
    check_out: date,
    adults: int,
    children_ages: list[int],
    dog: bool,
    apartment_breakfast: bool,
    today: date,
) -> dict:
    units = load_units()
    if unit_id not in units:
        raise ToolError(f"Unknown unit {unit_id!r}. Valid units: {', '.join(units)}")
    unit = units[unit_id]
    stay = _validate_dates(check_in, check_out, today)
    if adults < 1:
        raise ToolError("At least one adult is required")
    seasons = load_seasons()
    fees = seasons.fees
    if any(not seasons.is_open(n) for n in stay):
        raise ToolError("CasaVaiano is closed from 7 January to the end of February")
    if dog and not unit.pets_allowed:
        raise ToolError(f"Dogs are not allowed in {unit.name}; only in Ulivo and Fienile")

    counted = adults + sum(1 for age in children_ages if age > INFANT_MAX_AGE)
    if counted > _capacity(unit):
        raise ToolError(f"{unit.name} sleeps at most {_capacity(unit)} guests (infants excluded)")
    needs_extra_bed = counted > unit.max_guests

    by_season = Counter(seasons.season_for(n) for n in stay)
    accommodation = sum(unit.prices[s] * count for s, count in by_season.items())
    discount = 0.0
    if len(stay) >= fees.long_stay_min_nights:
        discount = round(accommodation * fees.long_stay_discount_pct / 100, 2)
    accommodation_net = accommodation - discount

    extras = []
    if needs_extra_bed:
        extras.append({"item": "extra bed", "amount": fees.extra_bed_per_night * len(stay)})
    if dog:
        extras.append({"item": "dog", "amount": fees.dog_per_night * len(stay)})
    if apartment_breakfast and unit.kind == "apartment":
        amount = fees.apartment_breakfast_per_person * counted * len(stay)
        extras.append({"item": f"breakfast for {counted}", "amount": amount})

    taxable = adults + sum(1 for age in children_ages if age >= fees.tourist_tax_exempt_under_age)
    tourist_tax = taxable * min(len(stay), fees.tourist_tax_max_nights)
    tourist_tax *= fees.tourist_tax_per_person_per_night

    min_nights = seasons.min_stay[unit.kind][seasons.season_for(check_in)]
    warnings = []
    if len(stay) < min_nights:
        warnings.append(f"Below the minimum stay of {min_nights} nights for this arrival date")
    if unit.id == "torre" and any(age < 6 for age in children_ages):
        warnings.append("Torre is not suitable for children under 6 (spiral staircase)")
    if apartment_breakfast and unit.kind == "room":
        warnings.append("Breakfast is already included in room prices")

    total = accommodation_net + sum(e["amount"] for e in extras)
    return {
        "unit": unit.id,
        "name": unit.name,
        "check_in": str(check_in),
        "check_out": str(check_out),
        "nights": len(stay),
        "nights_by_season": [
            {"season": s, "nights": c, "price_per_night": unit.prices[s]}
            for s, c in by_season.items()
        ],
        "breakfast_included": unit.kind == "room",
        "accommodation": _money(accommodation),
        "long_stay_discount": _money(discount),
        "extras": [{**e, "amount": _money(e["amount"])} for e in extras],
        "total": _money(total),
        "deposit_to_confirm": _money(accommodation_net * fees.deposit_pct / 100),
        "tourist_tax_paid_on_site": _money(tourist_tax),
        "available": not _is_booked(unit.id, check_in, check_out)
        and not any(e.overlaps(check_in, check_out) for e in load_calendar().exclusive_use),
        "warnings": warnings,
    }


def _validate_dates(check_in: date, check_out: date, today: date) -> list[date]:
    if check_in < today:
        raise ToolError(f"check_in {check_in} is in the past (today is {today})")
    if check_out <= check_in:
        raise ToolError("check_out must be after check_in")
    stay = nights(check_in, check_out)
    if len(stay) > MAX_NIGHTS:
        raise ToolError(f"Stays longer than {MAX_NIGHTS} nights are arranged directly with us")
    return stay


def _capacity(unit: Unit) -> int:
    return unit.max_guests + (1 if unit.extra_bed else 0)


def _is_booked(unit_id: str, check_in: date, check_out: date) -> bool:
    return any(
        b.unit == unit_id and b.overlaps(check_in, check_out) for b in load_calendar().bookings
    )


def _money(value: float) -> float:
    return round(value, 2)
