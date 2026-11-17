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
CHEAP_ANSWER_MIN_CONFIDENCE = 0.85


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
    )
    if settings.routing_enabled and simple:
        return Route(settings.cheap_model, "low")
    return Route(settings.strong_model, "low" if simple else "medium")


def escalate_route(settings: Settings) -> Route:
    return Route(settings.strong_model, "low")
