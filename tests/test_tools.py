from datetime import date

import pytest

from casavaiano.tools.registry import run_tool, tool_definitions, tool_result_block
from casavaiano.tools.stay import ToolError, check_availability, quote_stay

TODAY = date(2026, 11, 17)


def avail(check_in, check_out, guests=2, dog=False):
    return check_availability(
        date.fromisoformat(check_in), date.fromisoformat(check_out), guests, dog, TODAY
    )


def quote(unit, check_in, check_out, adults=2, children=(), dog=False, breakfast=False):
    return quote_stay(
        unit,
        date.fromisoformat(check_in),
        date.fromisoformat(check_out),
        adults,
        list(children),
        dog,
        breakfast,
        TODAY,
    )


def free_units(result):
    return {u["unit"] for u in result["available"]}


def test_ferragosto_is_full():
    result = avail("2027-08-10", "2027-08-17")
    assert free_units(result) == set()
    assert set(result["unavailable"].values()) == {"booked"}


def test_low_season_weekend_mostly_free():
    result = avail("2027-03-05", "2027-03-07")
    assert {"ulivo", "cipresso", "torre"} <= free_units(result)
    assert result["unavailable"]["granaio"] == "minimum stay 3 nights"


def test_closed_and_private_event():
    assert avail("2027-02-10", "2027-02-12")["reason"] == "closed"
    assert avail("2027-06-12", "2027-06-14")["reason"] == "private_event"


def test_dog_and_party_size_filters():
    dog = avail("2027-04-10", "2027-04-13", guests=2, dog=True)
    assert free_units(dog) == {"ulivo", "fienile"}
    big = avail("2027-04-10", "2027-04-13", guests=6)
    assert free_units(big) == {"granaio"}
    assert big["unavailable"]["vigna"] == "too small (max 5 guests)"


def test_high_season_min_stay_for_rooms():
    result = avail("2027-07-20", "2027-07-22")
    assert result["unavailable"]["ulivo"] == "minimum stay 3 nights"


def test_quote_simple_mid_season_room():
    q = quote("ulivo", "2027-05-07", "2027-05-10")
    assert q["accommodation"] == 3 * 115
    assert q["total"] == 345
    assert q["deposit_to_confirm"] == pytest.approx(103.5)
    assert q["tourist_tax_paid_on_site"] == 2 * 3 * 1.5
    assert q["breakfast_included"]
    assert q["available"]


def test_quote_mixes_seasons_and_applies_long_stay_discount():
    q = quote("torre", "2027-06-10", "2027-06-20")
    by_season = {s["season"]: s["nights"] for s in q["nights_by_season"]}
    assert by_season == {"mid": 5, "high": 5}
    assert q["accommodation"] == 5 * 185 + 5 * 230
    assert q["long_stay_discount"] == pytest.approx(207.5)
    assert q["total"] == pytest.approx(2075 - 207.5)
    assert q["tourist_tax_paid_on_site"] == 2 * 7 * 1.5
    assert not q["available"]


def test_quote_extras_children_and_tourist_tax():
    q = quote("vigna", "2027-09-01", "2027-09-04", adults=2, children=[16, 10, 7, 1], dog=False)
    assert {e["item"]: e["amount"] for e in q["extras"]} == {"extra bed": 90}
    assert q["tourist_tax_paid_on_site"] == 3 * 3 * 1.5


def test_quote_apartment_breakfast_and_dog():
    q = quote("fienile", "2027-10-11", "2027-10-14", adults=2, dog=True, breakfast=True)
    extras = {e["item"]: e["amount"] for e in q["extras"]}
    assert extras == {"dog": 45, "breakfast for 2": 72}
    assert q["total"] == 3 * 160 + 45 + 72
    assert not q["breakfast_included"]


def test_quote_warnings():
    assert any(
        "minimum stay" in w for w in quote("granaio", "2027-07-01", "2027-07-03")["warnings"]
    )
    assert any(
        "children under 6" in w
        for w in quote("torre", "2027-05-01", "2027-05-03", children=[4])["warnings"]
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (("cipresso", "2027-05-01", "2027-05-03", 2, (), True), "Dogs are not allowed"),
        (("ulivo", "2027-05-01", "2027-05-03", 3), "sleeps at most 2"),
        (("ulivo", "2026-11-01", "2026-11-03"), "in the past"),
        (("ulivo", "2027-05-03", "2027-05-01"), "after check_in"),
        (("ulivo", "2027-02-01", "2027-02-03"), "closed"),
        (("ulivo", "2027-04-01", "2027-05-15"), "longer than 30"),
        (("castle", "2027-05-01", "2027-05-03"), "Unknown unit"),
    ],
)
def test_quote_rejects_invalid_requests(args, message):
    with pytest.raises(ToolError, match=message):
        quote(*args)


def test_infants_do_not_count_toward_capacity():
    q = quote("ulivo", "2027-05-01", "2027-05-03", adults=2, children=[1])
    assert q["total"] == 2 * 115


def test_run_tool_returns_errors_as_data():
    ok = run_tool(
        "check_availability",
        {"check_in": "2027-05-01", "check_out": "2027-05-03", "guests": 2, "dog": False},
        TODAY,
    )
    assert "available" in ok
    bad = run_tool(
        "quote_stay",
        {
            "unit": "cipresso",
            "check_in": "2027-05-01",
            "check_out": "2027-05-03",
            "adults": 2,
            "children_ages": [],
            "dog": True,
            "apartment_breakfast": False,
        },
        TODAY,
    )
    assert "Dogs are not allowed" in bad["error"]
    assert run_tool("check_availability", {"check_in": "soon"}, TODAY)["error"]
    assert tool_result_block("t1", bad)["is_error"]


def test_tool_definitions_are_strict():
    for tool in tool_definitions():
        schema = tool["input_schema"]
        assert tool["strict"]
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
