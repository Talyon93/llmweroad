"""Deterministic escalation rules, applied before any answer is generated.

These are business decisions, not language understanding: they belong in code, where they are
testable and cannot be talked around by a cleverly written message.
"""

from casavaiano.agent.state import Classification

ALWAYS_ESCALATE_INTENTS = {"events", "booking_change", "complaint"}
MAX_AUTO_GROUP_SIZE = 6
MAX_AUTO_UNITS = 2
MIN_CONFIDENCE = 0.6


def escalation_reason(c: Classification, live: bool = False) -> str | None:
    """live: the real property, which hosts no weddings or private events. The owner wants those
    requests declined by the assistant from the knowledge base, not handed to him."""
    declined_event = live and c.private_event
    intents = {c.intent, *c.secondary_intents} & ALWAYS_ESCALATE_INTENTS
    if declined_event:
        intents.discard("events")
    if c.intent in intents:
        return f"intent:{c.intent}"
    if intents:
        return f"intent:{sorted(intents)[0]}"
    if c.risk_flags:
        return f"risk:{sorted(c.risk_flags)[0]}"
    if declined_event:
        return None
    if c.group_size and c.group_size > MAX_AUTO_GROUP_SIZE:
        return f"group_size:{c.group_size}"
    if live and c.units_requested and c.units_requested > MAX_AUTO_UNITS:
        return f"units:{c.units_requested}"
    if c.confidence < MIN_CONFIDENCE:
        return f"low_confidence:{c.confidence:.2f}"
    return None
