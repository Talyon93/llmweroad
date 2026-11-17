from collections import Counter
from datetime import date, timedelta

import pytest

from casavaiano.data import load_calendar, load_seasons, load_units, nights


def all_days(year: int) -> list[date]:
    start = date(year, 1, 1)
    return [start + timedelta(days=i) for i in range((date(year + 1, 1, 1) - start).days)]


def test_units_load():
    units = load_units()
    assert len(units) == 7
    assert sum(u.max_guests for u in units.values()) == 23
    assert {u.kind for u in units.values()} == {"room", "apartment"}


@pytest.mark.parametrize("year", [2026, 2027, 2028])
def test_every_open_day_has_exactly_one_season(year):
    seasons = load_seasons()
    for day in all_days(year):
        matches = [p for p in seasons.periods if p.contains(day)]
        if seasons.is_open(day):
            assert len(matches) == 1, day
        else:
            assert day.month in (1, 2), day


@pytest.mark.parametrize(
    ("day", "season"),
    [
        (date(2027, 3, 1), "low"),
        (date(2027, 3, 31), "low"),
        (date(2027, 4, 1), "mid"),
        (date(2027, 6, 14), "mid"),
        (date(2027, 6, 15), "high"),
        (date(2027, 9, 15), "high"),
        (date(2027, 9, 16), "mid"),
        (date(2027, 11, 2), "mid"),
        (date(2027, 11, 3), "low"),
        (date(2027, 12, 19), "low"),
        (date(2027, 12, 20), "high"),
        (date(2028, 1, 6), "high"),
    ],
)
def test_season_boundaries(day, season):
    assert load_seasons().season_for(day) == season


@pytest.mark.parametrize("day", [date(2027, 1, 7), date(2027, 2, 14), date(2028, 2, 29)])
def test_closed_days(day):
    seasons = load_seasons()
    assert not seasons.is_open(day)
    with pytest.raises(ValueError, match="closed"):
        seasons.season_for(day)


def test_bookings_reference_known_units():
    units = load_units()
    assert {b.unit for b in load_calendar().bookings} <= units.keys()


def test_bookings_do_not_overlap():
    calendar = load_calendar()
    occupied = Counter(
        (b.unit, night) for b in calendar.bookings for night in nights(b.check_in, b.check_out)
    )
    assert [key for key, count in occupied.items() if count > 1] == []
    for block in calendar.exclusive_use:
        clashes = [b for b in calendar.bookings if b.overlaps(block.check_in, block.check_out)]
        assert clashes == []


def test_bookings_fall_in_opening_period():
    seasons = load_seasons()
    calendar = load_calendar()
    for stay in [*calendar.bookings, *calendar.exclusive_use]:
        assert all(seasons.is_open(n) for n in nights(stay.check_in, stay.check_out)), stay


def test_booking_rejects_inverted_dates():
    from casavaiano.data import Booking

    with pytest.raises(ValueError):
        Booking(unit="ulivo", check_in=date(2027, 5, 3), check_out=date(2027, 5, 1))
