from datetime import date

import pytest

from casavaiano.config import Settings
from casavaiano.tools import registry
from casavaiano.tools.ical import IcalCalendars, busy_nights, ical_urls
from casavaiano.tools.live import (
    Lodging,
    check_availability_live,
    load_lodgings,
    saturday_stay,
)
from casavaiano.tools.registry import DemoTools, LiveTools, make_toolbox
from casavaiano.tools.stay import ToolError

TODAY = date(2026, 11, 18)
d = date.fromisoformat

ICS = """BEGIN:VCALENDAR\r
BEGIN:VEVENT\r
DTSTART;VALUE=DATE:20270710\r
DTEND;VALUE=DATE:20270717\r
SUMMARY:Booked\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART:20270801T140000Z\r
DTEND:20270803T100000Z\r
END:VEVENT\r
BEGIN:VEVENT\r
DTSTART;VALUE=DATE:20270901\r
END:VEVENT\r
END:VCALENDAR\r
"""


def test_busy_nights_treats_dtend_as_exclusive():
    nights = busy_nights(ICS)
    assert d("2027-07-10") in nights and d("2027-07-16") in nights
    assert d("2027-07-17") not in nights
    assert {d("2027-08-01"), d("2027-08-02")} <= nights and d("2027-08-03") not in nights
    assert d("2027-09-01") in nights and d("2027-09-02") not in nights


def test_ical_urls_from_env_file(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CASA_ICAL_GIRASOLE=https://a\nCASA_ICAL_CAPANNA=\nOTHER=x\n", encoding="utf-8")
    monkeypatch.setenv("CASA_ICAL_FIORDALISO", "https://b")
    assert ical_urls(env) == {"Girasole": "https://a", "Fiordaliso": "https://b"}


def test_calendars_cache_and_keep_last_good_copy():
    calls = {"n": 0, "fail": False}

    def fetch(url):
        calls["n"] += 1
        if calls["fail"] or url == "bad":
            raise OSError("down")
        return ICS

    calendars = IcalCalendars({"Girasole": "ok", "Capanna": "bad"}, ttl_seconds=0, fetch=fetch)
    first = calendars.busy()
    assert d("2027-07-10") in first["Girasole"]
    assert first["Capanna"] is None
    calls["fail"] = True
    assert calendars.busy()["Girasole"] == first["Girasole"]

    cached = IcalCalendars({"Girasole": "ok"}, ttl_seconds=3600, fetch=fetch)
    before = calls["n"]
    calls["fail"] = False
    cached.busy()
    cached.busy()
    assert calls["n"] == before + 1


@pytest.mark.parametrize(
    ("check_in", "check_out", "expected"),
    [
        ("2027-07-14", "2027-07-21", ("2027-07-17", "2027-07-24")),  # Wed -> next Saturday
        ("2027-07-12", "2027-07-19", ("2027-07-10", "2027-07-17")),  # Mon -> previous Saturday
        ("2027-07-10", "2027-07-24", None),  # already Saturday to Saturday
        ("2027-06-10", "2027-06-14", None),  # not July or August
        ("2027-08-28", "2027-09-02", ("2027-08-28", "2027-09-04")),  # last nights in August
        ("2027-07-10", "2027-07-21", ("2027-07-10", "2027-07-24")),  # 11 nights -> 2 weeks
        ("2027-07-14", "2027-07-16", ("2027-07-17", "2027-07-24")),  # short stay -> 1 week
    ],
)
def test_saturday_stay(check_in, check_out, expected):
    result = saturday_stay(d(check_in), d(check_out))
    assert result == (None if expected is None else (d(expected[0]), d(expected[1])))


class FakeCalendars:
    def __init__(self, busy):
        self._busy = busy

    def busy(self):
        return self._busy


LODGINGS = (
    Lodging("Girasole", 50, None, "aria condizionata"),
    Lodging("Capanna", 45, 4, "indipendente"),
    Lodging("Ginestra", 55, 6, "due bagni"),
    Lodging("Castagno", 50, None, "accessibile"),
)


def test_live_availability_classifies_each_apartment():
    calendars = FakeCalendars(
        {
            "Girasole": set(),
            "Capanna": set(),
            "Ginestra": {d("2027-05-08")},
            "Castagno": None,
        }
    )
    result = check_availability_live(
        d("2027-05-07"), d("2027-05-10"), 5, TODAY, calendars, "https://book", LODGINGS
    )
    assert [a["name"] for a in result["available"]] == ["Girasole"]
    assert "owner confirms" in result["available"][0]["capacity"]
    assert result["not_available"] == ["Capanna (sleeps 4)", "Ginestra"]
    assert result["unknown"] == ["Castagno"]
    assert result["booking_url"] == "https://book"
    assert "Never state a price" in result["prices"]
    assert "rule" not in result


def test_live_availability_applies_saturday_rule():
    calendars = FakeCalendars({name.name: set() for name in LODGINGS})
    result = check_availability_live(
        d("2027-07-14"), d("2027-07-21"), 2, TODAY, calendars, "", LODGINGS
    )
    assert result["requested"] == {"check_in": "2027-07-14", "check_out": "2027-07-21"}
    assert result["checked"]["check_in"] == "2027-07-17"
    assert "Saturday to Saturday" in result["rule"]


def test_live_availability_rejects_past_dates():
    with pytest.raises(ToolError, match="in the past"):
        check_availability_live(
            d("2026-11-01"), d("2026-11-03"), 2, TODAY, FakeCalendars({}), "", LODGINGS
        )


def test_real_lodgings_file():
    names = [lodging.name for lodging in load_lodgings()]
    assert names == [
        "Capanna", "Girasole", "Ginestra", "Cipresso",
        "Castagno", "Papavero", "Ciclamino", "Fiordaliso",
    ]  # fmt: skip


def test_live_tools_offer_no_prices():
    tools = LiveTools(FakeCalendars({}), "https://book")
    names = [t["name"] for t in tools.definitions()]
    assert names == ["check_availability", "escalate_to_owner"]
    assert "error" in tools.run("quote_stay", {}, TODAY)
    assert "error" in tools.run("check_availability", {"check_in": "soon"}, TODAY)


def test_make_toolbox(monkeypatch, tmp_path):
    assert isinstance(make_toolbox(Settings(_env_file=None)), DemoTools)
    monkeypatch.setattr(registry, "ical_urls", lambda: {"Girasole": "https://a"})
    with pytest.raises(ToolError, match="real knowledge base"):
        make_toolbox(Settings(_env_file=None, availability_source="slope"))
    live = Settings(_env_file=None, availability_source="slope", kb_dir=str(tmp_path))
    assert isinstance(make_toolbox(live), LiveTools)
    monkeypatch.setattr(registry, "ical_urls", lambda: {})
    with pytest.raises(ToolError, match="CASA_ICAL"):
        make_toolbox(live)


def test_live_escalation_drafts_never_contain_prices():
    from casavaiano.agent.prompts import Persona, escalate_system

    assert "Never write a price" in escalate_system(Persona("Rocco", "Tommaso", live=True))
    assert "Never write a price" not in escalate_system(Persona("Rocco", "Giulia"))


def test_fifth_guest_needs_the_extra_bed():
    lodgings = (Lodging("Girasole", 50, 5, "aria condizionata", standard_guests=4),)
    calendars = FakeCalendars({"Girasole": set()})
    five = check_availability_live(
        d("2027-05-07"), d("2027-05-10"), 5, TODAY, calendars, "", lodgings
    )
    assert "extra single bed" in five["available"][0]["extra_bed"]
    four = check_availability_live(
        d("2027-05-07"), d("2027-05-10"), 4, TODAY, calendars, "", lodgings
    )
    assert "extra_bed" not in four["available"][0]
    six = check_availability_live(
        d("2027-05-07"), d("2027-05-10"), 6, TODAY, calendars, "", lodgings
    )
    assert six["not_available"] == ["Girasole (sleeps 5)"]


def test_minimum_stay_outside_high_season():
    calendars = FakeCalendars({"Girasole": set()})
    lodgings = (Lodging("Girasole", 50, 5, "aria condizionata", standard_guests=4),)
    short = check_availability_live(
        d("2027-05-07"), d("2027-05-09"), 2, TODAY, calendars, "", lodgings
    )
    assert "minimum stay is 3 nights" in short["min_stay"]
    ok = check_availability_live(
        d("2027-05-07"), d("2027-05-10"), 2, TODAY, calendars, "", lodgings
    )
    assert "min_stay" not in ok


def test_closed_season_and_new_year():
    calendars = FakeCalendars({"Girasole": set()})
    lodgings = (Lodging("Girasole", 50, 5, "aria condizionata", standard_guests=4),)
    february = check_availability_live(
        d("2027-02-02"), d("2027-02-12"), 4, TODAY, calendars, "", lodgings
    )
    assert "closed" in february["closed"] and february["available"] == []
    late_october = check_availability_live(
        d("2027-10-28"), d("2027-11-02"), 2, TODAY, calendars, "", lodgings
    )
    assert "closed" in late_october
    new_year = check_availability_live(
        d("2026-12-30"), d("2027-01-02"), 2, TODAY, calendars, "", lodgings
    )
    assert "New Year" in new_year["new_year"] and "closed" not in new_year
