"""Deterministic escalation rules, applied before any answer is generated.

These are business decisions, not language understanding: they belong in code, where they are
testable and cannot be talked around by a cleverly written message.
"""

from casavaiano.agent.state import Classification

ALWAYS_ESCALATE_INTENTS = {"events", "booking_change", "complaint"}
MAX_AUTO_GROUP_SIZE = 6
MIN_CONFIDENCE = 0.6


def escalation_reason(c: Classification) -> str | None:
    if c.intent in ALWAYS_ESCALATE_INTENTS:
        return f"intent:{c.intent}"
    secondary = ALWAYS_ESCALATE_INTENTS.intersection(c.secondary_intents)
    if secondary:
        return f"intent:{sorted(secondary)[0]}"
    if c.risk_flags:
        return f"risk:{sorted(c.risk_flags)[0]}"
    if c.group_size and c.group_size > MAX_AUTO_GROUP_SIZE:
        return f"group_size:{c.group_size}"
    if c.confidence < MIN_CONFIDENCE:
        return f"low_confidence:{c.confidence:.2f}"
    return None
