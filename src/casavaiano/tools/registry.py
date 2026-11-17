"""Tool definitions exposed to the LLM and their dispatch."""

import json
from datetime import date
from typing import Any

from casavaiano.data import load_units
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
                "Hand the conversation to Giulia (the owner). Use when the answer is not in the "
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
