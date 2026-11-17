"""The KB markdown is what the LLM reads; the structured data is what the tools compute with.
These tests keep the two from drifting apart."""

import re

import pytest

from casavaiano.config import KB_DIR
from casavaiano.data import load_seasons, load_units


def kb(name: str) -> str:
    return (KB_DIR / f"{name}.md").read_text(encoding="utf-8")


def table_rows(text: str, first_cell: str) -> dict[str, list[str]]:
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells[0] not in (first_cell, "---"):
            rows[cells[0]] = cells[1:]
    return rows


def section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"missing section: {heading}"
    return match.group(1)


def test_price_table_matches_structured_data():
    rows = table_rows(section(kb("prices"), "Nightly prices"), "Unit")
    units = load_units()
    assert set(rows) == {u.name for u in units.values()}
    for unit in units.values():
        _, max_guests, low, mid, high = rows[unit.name]
        assert int(max_guests) == unit.max_guests
        assert [low, mid, high] == [f"€{unit.prices[s]}" for s in ("low", "mid", "high")]


def test_min_stay_table_matches_structured_data():
    rows = table_rows(section(kb("prices"), "Minimum stay"), "Unit type")
    min_stay = load_seasons().min_stay
    for label, kind in (("Rooms", "room"), ("Apartments", "apartment")):
        values = [int(cell.split()[0]) for cell in rows[label]]
        assert values == [min_stay[kind][s] for s in ("low", "mid", "high")]


@pytest.mark.parametrize(
    ("doc", "phrase"),
    [
        ("prices", "Extra bed (Vigna and Torre only): €{extra_bed_per_night:g} per night"),
        ("prices", "Dog: €{dog_per_night:g} per night"),
        ("prices", "€{apartment_breakfast_per_person:g} per person per day"),
        ("prices", "€{tourist_tax_per_person_per_night:.2f} per person per night"),
        ("prices", "maximum of {tourist_tax_max_nights} consecutive nights"),
        ("prices", "Children under {tourist_tax_exempt_under_age} are exempt"),
        ("prices", "{long_stay_min_nights} nights or more get {long_stay_discount_pct:g}% off"),
        ("policies", "A deposit of {deposit_pct:g}%"),
        ("policies", "Free cancellation up to {free_cancellation_days} days"),
        ("policies", "{late_cancellation_pct:g}% of the total"),
        ("policies", "€{dog_per_night:g} per\nnight"),
    ],
)
def test_fees_are_stated_in_kb(doc, phrase):
    fees = load_seasons().fees.model_dump()
    assert phrase.format(**fees) in kb(doc)


def test_every_unit_has_a_rooms_section():
    rooms = kb("rooms")
    for unit in load_units().values():
        assert f"## {unit.name} (" in rooms


def test_pet_and_extra_bed_rules_match():
    units = load_units().values()
    pet_units = sorted(u.name for u in units if u.pets_allowed)
    extra_bed_units = sorted(u.name for u in units if u.extra_bed)
    assert f"Dogs are welcome in the {pet_units[1]} room and the {pet_units[0]} apartment" in kb(
        "policies"
    )
    assert f"Extra bed ({' and '.join(reversed(extra_bed_units))} only)" in kb("prices")


def test_total_capacity_in_about():
    total = sum(u.max_guests for u in load_units().values())
    assert f"up to\n{total} guests" in kb("about")
    assert f"{total} beds" in kb("events")
