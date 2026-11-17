"""Deterministic check that every euro amount in a reply comes from the context or a tool result.

Handles Italian/German (1.234,50) and English (1,234.50) number formats.
"""

import re
from collections.abc import Iterable
from typing import Any

_NUMBER = r"\d[\d.,]*\d|\d"
_AMOUNT = re.compile(rf"(?:€|EUR|euro)\s?({_NUMBER})|({_NUMBER})\s?(?:€|EUR\b|euro)", re.IGNORECASE)
_ANY_NUMBER = re.compile(_NUMBER)


def parse_number(raw: str) -> float | None:
    s = raw.strip(".,")
    if "." in s and "," in s:
        decimal = "," if s.rfind(",") > s.rfind(".") else "."
        thousands = "." if decimal == "," else ","
        s = s.replace(thousands, "").replace(decimal, ".")
    elif "," in s:
        s = s.replace(",", ".") if re.search(r",\d{1,2}$", s) else s.replace(",", "")
    elif s.count(".") > 1 or re.search(r"^\d{1,3}\.\d{3}$", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def amounts_in(text: str) -> list[float]:
    values = (parse_number(a or b) for a, b in _AMOUNT.findall(text))
    return [v for v in values if v is not None]


def numbers_in_sources(texts: Iterable[str], tool_outputs: Iterable[Any]) -> set[float]:
    found: set[float] = set()
    for text in texts:
        found.update(v for v in map(parse_number, _ANY_NUMBER.findall(text)) if v is not None)
    for output in tool_outputs:
        found.update(_numbers_in_json(output))
    return found


def ungrounded_amounts(reply: str, sources: set[float]) -> list[float]:
    return [a for a in amounts_in(reply) if not any(abs(a - s) < 0.006 for s in sources)]


def _numbers_in_json(value: Any) -> set[float]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, int | float):
        return {float(value)}
    if isinstance(value, dict):
        return set().union(*(_numbers_in_json(v) for v in value.values()))
    if isinstance(value, list):
        return set().union(*(_numbers_in_json(v) for v in value))
    if isinstance(value, str):
        return {v for v in map(parse_number, _ANY_NUMBER.findall(value)) if v is not None}
    return set()
