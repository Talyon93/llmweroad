"""Tool definitions exposed to the LLM and their dispatch."""

import json
from datetime import date
from functools import lru_cache
from typing import Any

from casavaiano.config import KB_DIR
from casavaiano.data import load_units
from casavaiano.tools.ical import IcalCalendars, ical_urls
from casavaiano.tools.live import check_availability_live
from casavaiano.tools.stay import ToolError, check_availability, quote_stay

ESCALATE_TOOL = "escalate_to_owner"

_DATE = {"type": "string", "format": "date", "description": "YYYY-MM-DD"}


def tool_definitions() -> list[dict[str, Any]]:
    unit_ids = list(load_units())
    return [
        {
            "name": "check_availability",
            "description": (
                "Check which rooms and apartments are free for given dates and party size. "
                "Use whenever the guest gives (or clearly implies) specific dates."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "check_in": _DATE,
                    "check_out": _DATE,
                    "guests": {
                        "type": "integer",
                        "description": "People sleeping in one unit, excluding children under 3",
                    },
                    "dog": {"type": "boolean"},
                },
                "required": ["check_in", "check_out", "guests", "dog"],
                "additionalProperties": False,
            },
        },
        {
            "name": "quote_stay",
            "description": (
                "Exact price for one unit and dates, including season mix, long-stay discount, "
                "extras, deposit and tourist tax. Always use this instead of computing prices."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "unit": {"type": "string", "enum": unit_ids},
                    "check_in": _DATE,
                    "check_out": _DATE,
                    "adults": {"type": "integer"},
                    "children_ages": {"type": "array", "items": {"type": "integer"}},
                    "dog": {"type": "boolean"},
                    "apartment_breakfast": {"type": "boolean"},
                },
                "required": [
                    "unit",
                    "check_in",
                    "check_out",
                    "adults",
                    "children_ages",
                    "dog",
                    "apartment_breakfast",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": ESCALATE_TOOL,
            "description": (
                "Hand the conversation to the owners (a human). Use when the answer is not in the "
                "context or tool results, when the guest asks for an exception to a policy, a "
                "special discount, or anything you are not sure about."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": ["reason"],
                "additionalProperties": False,
            },
        },
    ]


def run_tool(name: str, args: dict[str, Any], today: date) -> dict[str, Any]:
    try:
        if name == "check_availability":
            return check_availability(
                date.fromisoformat(args["check_in"]),
                date.fromisoformat(args["check_out"]),
                int(args["guests"]),
                bool(args["dog"]),
                today,
            )
        if name == "quote_stay":
            return quote_stay(
                args["unit"],
                date.fromisoformat(args["check_in"]),
                date.fromisoformat(args["check_out"]),
                int(args["adults"]),
                [int(a) for a in args["children_ages"]],
                bool(args["dog"]),
                bool(args["apartment_breakfast"]),
                today,
            )
    except (ToolError, ValueError, KeyError) as exc:
        return {"error": str(exc)}
    return {"error": f"Unknown tool {name!r}"}


def tool_result_block(tool_use_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": json.dumps(result, ensure_ascii=False),
        "is_error": "error" in result,
    }


class DemoTools:
    """Fictional rooms, prices and bookings from data/structured: used by the evals and the demo."""

    def definitions(self) -> list[dict[str, Any]]:
        return tool_definitions()

    def run(self, name: str, args: dict[str, Any], today: date) -> dict[str, Any]:
        return run_tool(name, args, today)


class LiveTools:
    """The real apartments: availability from Slope's iCal calendars, no prices."""

    def __init__(self, calendars: IcalCalendars, booking_url: str):
        self.calendars = calendars
        self.booking_url = booking_url

    def definitions(self) -> list[dict[str, Any]]:
        escalate = next(t for t in tool_definitions() if t["name"] == ESCALATE_TOOL)
        check = {
            "name": "check_availability",
            "description": (
                "Check which apartments are free for given dates, from the live booking "
                "calendars. Use whenever the guest gives (or clearly implies) specific dates. "
                "In July and August it checks the Saturday-to-Saturday stay closest to the dates."
            ),
            "strict": True,
            "input_schema": {
                "type": "object",
                "properties": {
                    "check_in": _DATE,
                    "check_out": _DATE,
                    "guests": {"type": "integer", "description": "Total people, children included"},
                },
                "required": ["check_in", "check_out", "guests"],
                "additionalProperties": False,
            },
        }
        return [check, escalate]

    def run(self, name: str, args: dict[str, Any], today: date) -> dict[str, Any]:
        if name != "check_availability":
            return {"error": f"Unknown tool {name!r}"}
        try:
            return check_availability_live(
                date.fromisoformat(args["check_in"]),
                date.fromisoformat(args["check_out"]),
                int(args["guests"]),
                today,
                self.calendars,
                self.booking_url,
            )
        except (ToolError, ValueError, KeyError) as exc:
            return {"error": str(exc)}


@lru_cache
def _live_calendars(urls: tuple[tuple[str, str], ...]) -> IcalCalendars:
    return IcalCalendars(dict(urls))


def make_toolbox(settings) -> DemoTools | LiveTools:
    if settings.availability_source == "slope":
        if settings.knowledge_base_dir.resolve() == KB_DIR.resolve():
            raise ToolError(
                "AVAILABILITY_SOURCE=slope needs the real knowledge base: set KB_DIR, the demo "
                "KB has fictional apartments and prices"
            )
        urls = ical_urls()
        if not urls:
            raise ToolError("AVAILABILITY_SOURCE=slope but no CASA_ICAL_* calendars are set")
        return LiveTools(_live_calendars(tuple(sorted(urls.items()))), settings.booking_url)
    return DemoTools()
