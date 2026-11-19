"""Model routing. With routing off, every call uses the strong model (the baseline)."""

from dataclasses import dataclass

from casavaiano.agent.state import Classification
from casavaiano.config import Settings
from casavaiano.llm.base import Effort

SIMPLE_INTENTS = {
    "prices",
    "rooms",
    "pets",
    "restaurant",
    "checkin",
    "directions",
    "services",
    "policies",
    "other",
}
# Haiku rates plain but short questions ("Che giochi ci sono per i bambini?") at 0.8; at 0.85
# they went to Opus at ~50x the cost. Below 0.6 the guard escalates anyway.
CHEAP_ANSWER_MIN_CONFIDENCE = 0.7
MAX_CHEAP_BOOKING_GUESTS = 5


@dataclass(frozen=True)
class Route:
    model: str
    effort: Effort


def classify_route(settings: Settings) -> Route:
    model = settings.cheap_model if settings.routing_enabled else settings.strong_model
    return Route(model, "low")


def answer_route(settings: Settings, c: Classification) -> Route:
    simple = (
        c.intent in SIMPLE_INTENTS
        and SIMPLE_INTENTS.issuperset(c.secondary_intents)
        and c.confidence >= CHEAP_ANSWER_MIN_CONFIDENCE
    ) or _simple_live_booking(settings, c)
    if settings.routing_enabled and simple:
        return Route(settings.cheap_model, "low")
    return Route(settings.strong_model, "low" if simple else "medium")


def _simple_live_booking(settings: Settings, c: Classification) -> bool:
    """On the real site a booking is one availability check and a booking link: no prices to
    compute, so the cheap model can do it for one apartment. Demo bookings compute quotes and
    stay on the strong model."""
    return (
        settings.availability_source == "slope"
        and c.intent == "booking"
        and SIMPLE_INTENTS.issuperset(c.secondary_intents)
        and c.confidence >= CHEAP_ANSWER_MIN_CONFIDENCE
        and (c.group_size or 0) <= MAX_CHEAP_BOOKING_GUESTS
        and (c.units_requested or 1) <= 1
    )


def escalate_route(settings: Settings) -> Route:
    return Route(settings.strong_model, "low")
