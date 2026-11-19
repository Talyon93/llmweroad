from datetime import date

import pytest

from casavaiano.agent.graph import Assistant
from casavaiano.agent.grounding import (
    amounts_in,
    numbers_in_sources,
    parse_number,
    ungrounded_amounts,
)
from casavaiano.agent.guards import escalation_reason
from casavaiano.agent.prompts import Persona, acknowledgement, answer_system, localize_signature
from casavaiano.agent.state import Classification, EscalationDraft
from casavaiano.config import Settings
from casavaiano.llm import LLMError, ToolCall
from casavaiano.llm.fake import FakeLLM, FakeReply
from casavaiano.observability import Tracer
from casavaiano.rag.retriever import RetrievedChunk

TODAY = date(2026, 11, 17)
CHEAP, STRONG = "claude-haiku-5-5", "claude-opus-5-5"

PETS_CHUNK = RetrievedChunk(
    id="policies:3",
    text="Policies - Pets\n\nDogs are welcome in Ulivo and Fienile only, for €15 per night.",
    source="policies",
    sections=("Pets",),
    score=0.8,
)


class StubRetriever:
    def __init__(self, chunks=(PETS_CHUNK,)):
        self.chunks = list(chunks)
        self.queries = []

    def search(self, query, k=None):
        self.queries.append(query)
        return self.chunks


def classification(intent="pets", **overrides) -> Classification:
    fields = dict(
        intent=intent,
        secondary_intents=[],
        language="it",
        confidence=0.95,
        risk_flags=[],
        group_size=None,
        search_query="dogs allowed",
    )
    return Classification(**(fields | overrides))


DRAFT = EscalationDraft(
    owner_summary="Guest unhappy.", priority="high", draft_reply="Ci dispiace...", missing_info=[]
)


def make_assistant(handler, routing=True, retriever=None, **settings):
    s = Settings(
        _env_file=None,
        langfuse_public_key=None,
        langfuse_secret_key=None,
        routing_enabled=routing,
        cheap_model=CHEAP,
        strong_model=STRONG,
        **settings,
    )
    fake = FakeLLM(handler)
    assistant = Assistant(fake, retriever or StubRetriever(), s, Tracer(s))
    return assistant, fake


def test_simple_question_answered_by_cheap_model():
    def handler(r):
        if r.name == "classify":
            return classification()
        return "Sì, i cani sono benvenuti in Ulivo e Fienile (€15 a notte).\n\nCasaVaiano"

    assistant, fake = make_assistant(handler)
    response = assistant.run("Accettate cani?", today=TODAY)

    assert response.status == "answered"
    assert "€15" in response.reply
    assert [c.model for c in response.calls] == [CHEAP, CHEAP]
    assert response.cost_usd == pytest.approx(sum(c.cost_usd for c in response.calls))
    assert response.sources == ["policies:3"]
    assert fake.calls("decide")[0].effort == "low"


def test_routing_off_uses_strong_model_everywhere():
    assistant, _ = make_assistant(
        lambda r: classification() if r.name == "classify" else "Sì, €15 a notte.", routing=False
    )
    response = assistant.run("Accettate cani?", today=TODAY)
    assert {c.model for c in response.calls} == {STRONG}


def test_booking_runs_tools_then_answers_with_tool_amounts():
    def handler(r):
        if r.name == "classify":
            return classification("booking", language="en", search_query="availability")
        turn = len(r.messages)
        if turn == 1:
            args = {"check_in": "2027-05-07", "check_out": "2027-05-10", "guests": 2, "dog": False}
            return FakeReply(tool_calls=[ToolCall("t1", "check_availability", args)])
        if turn == 3:
            args = {
                "unit": "ulivo",
                "check_in": "2027-05-07",
                "check_out": "2027-05-10",
                "adults": 2,
                "children_ages": [],
                "dog": False,
                "apartment_breakfast": False,
            }
            return FakeReply(tool_calls=[ToolCall("t2", "quote_stay", args)])
        return "Ulivo is free: €345 for 3 nights, deposit €103.50.\n\nCasaVaiano"

    assistant, fake = make_assistant(handler)
    response = assistant.run("Room for 2, 7-10 May?", today=TODAY)

    assert response.status == "answered"
    assert [t.name for t in response.tools] == ["check_availability", "quote_stay"]
    assert response.tools[1].output["total"] == 345
    decide_calls = fake.calls("decide")
    assert len(decide_calls) == 3
    assert {r.model for r in decide_calls} == {STRONG}
    tool_result = decide_calls[1].messages[2]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "t1"


def test_guard_escalates_complaint_without_answering():
    def handler(r):
        if r.name == "classify":
            return classification("complaint", risk_flags=["complaint", "refund_request"])
        assert r.name == "escalate"
        return DRAFT

    assistant, fake = make_assistant(handler)
    response = assistant.run("La camera era sporca, voglio un rimborso!", today=TODAY)

    assert response.status == "escalated"
    assert response.escalation_reason == "intent:complaint"
    assert response.reply == acknowledgement("it", Persona("Rocco", "Giulia"))
    assert response.escalation == DRAFT
    assert fake.calls("decide") == []
    assert fake.calls("escalate")[0].model == STRONG


def test_llm_can_escalate_through_tool():
    def handler(r):
        if r.name == "classify":
            return classification("policies")
        if r.name == "decide":
            reason = {"reason": "asks to waive the cancellation fee"}
            return FakeReply(tool_calls=[ToolCall("t1", "escalate_to_owner", reason)])
        return DRAFT

    assistant, _ = make_assistant(handler)
    response = assistant.run("Could you waive the fee for us?", today=TODAY)
    assert response.status == "escalated"
    assert response.escalation_reason == "llm:asks to waive the cancellation fee"


def test_invented_price_is_caught_and_escalated():
    def handler(r):
        if r.name == "classify":
            return classification()
        if r.name == "decide":
            return "Sì, i cani pagano €20 a notte."
        return DRAFT

    assistant, _ = make_assistant(handler)
    response = assistant.run("Accettate cani?", today=TODAY)
    assert response.status == "escalated"
    assert response.escalation_reason == "ungrounded_amounts:[20.0]"


def test_cheap_classifier_failure_falls_back_to_strong():
    def handler(r):
        if r.name == "classify" and r.model == CHEAP:
            raise LLMError("overloaded")
        if r.name == "classify":
            return classification()
        return "Sì, €15 a notte."

    assistant, fake = make_assistant(handler)
    response = assistant.run("Accettate cani?", today=TODAY)
    assert response.status == "answered"
    assert [r.model for r in fake.calls("classify")] == [CHEAP, STRONG]


def test_total_llm_outage_still_escalates_with_fallback_draft():
    def handler(r):
        raise LLMError("down")

    assistant, _ = make_assistant(handler)
    response = assistant.run("Hallo?", today=TODAY)
    assert response.status == "escalated"
    assert response.escalation_reason == "classification_failed"
    assert response.escalation.priority == "high"
    assert response.reply == acknowledgement("en", Persona("Rocco", "Giulia"))


def test_tool_loop_is_bounded():
    def handler(r):
        if r.name == "classify":
            return classification("booking")
        if r.name == "decide":
            args = {"check_in": "2027-05-07", "check_out": "2027-05-10", "guests": 2, "dog": False}
            return FakeReply(tool_calls=[ToolCall("t", "check_availability", args)])
        return DRAFT

    assistant, fake = make_assistant(handler, max_tool_iterations=2)
    response = assistant.run("Room?", today=TODAY)
    assert response.escalation_reason == "tool_loop_limit"
    assert len(fake.calls("decide")) == 2


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("original", ["Hunde?"]),
        ("rewritten", ["dogs allowed"]),
        ("both", ["Hunde?", "dogs allowed"]),
    ],
)
def test_retrieval_query_modes(mode, expected):
    retriever = StubRetriever()
    assistant, _ = make_assistant(
        lambda r: classification() if r.name == "classify" else "Ja, €15.",
        retriever=retriever,
        retrieval_query=mode,
    )
    assistant.run("Hunde?", today=TODAY)
    assert retriever.queries == expected


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"intent": "events"}, "intent:events"),
        ({"secondary_intents": ["booking_change"]}, "intent:booking_change"),
        ({"risk_flags": ["prompt_injection"]}, "risk:prompt_injection"),
        ({"group_size": 9}, "group_size:9"),
        ({"confidence": 0.4}, "low_confidence:0.40"),
        ({"group_size": 4}, None),
        ({}, None),
    ],
)
def test_guards(overrides, reason):
    assert escalation_reason(classification(**overrides)) == reason


@pytest.mark.parametrize(
    ("raw", "value"),
    [
        ("15", 15),
        ("1.234,50", 1234.5),
        ("1,234.50", 1234.5),
        ("103,50", 103.5),
        ("103.50", 103.5),
        ("1.500", 1500),
        ("1,500", 1500),
        ("1.5", 1.5),
        ("2075", 2075),
    ],
)
def test_parse_number(raw, value):
    assert parse_number(raw) == value


def test_amounts_and_grounding():
    reply = "Totale €1.867,50 (acconto 560,25 €), tassa 21 euro. Check-in alle 15:00."
    assert amounts_in(reply) == [1867.5, 560.25, 21]
    sources = numbers_in_sources(["Tourist tax €1.50"], [{"total": 1867.5, "deposit": 560.25}])
    assert ungrounded_amounts(reply, sources) == [21]


@pytest.mark.parametrize(
    ("language", "owner", "expected"),
    [
        ("it", "Giulia", "L'ho passato a Giulia"),
        ("it", None, "L'ho passato alla famiglia"),
        ("de", None, "an die Familie weitergeleitet"),
        ("en", "Anna", "passed it on to Anna"),
        ("fr", None, "to the family"),
    ],
)
def test_acknowledgement_names_and_discloses_assistant(language, owner, expected):
    text = acknowledgement(language, Persona("Rocco", owner))
    assert expected in text
    assert "Rocco" in text
    assert "virtual" in text or "virtuel" in text


def test_answer_prompt_uses_persona():
    prompt = answer_system(Persona("Rocco", None))
    assert "You are Rocco" in prompt
    assert "Giulia" not in prompt
    assert "virtual assistant" in prompt


def test_english_signature_is_localized():
    p = Persona("Rocco", "Tommaso", live=True)
    reply = "Ciao,\n\nSì.\n\nSaluti,\nRocco, CasaVaiano's virtual assistant"
    assert localize_signature(reply, "it", p).endswith("Rocco, l'assistente virtuale di CasaVaiano")
    assert localize_signature(reply, "en", p) == reply
    assert localize_signature(reply, "fr", p) == reply


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"intent": "events", "private_event": True, "group_size": 40}, None),
        ({"intent": "events", "private_event": True, "risk_flags": ["abusive"]}, "risk:abusive"),
        ({"intent": "events", "group_size": 14}, "intent:events"),
        ({"intent": "booking", "units_requested": 3}, "units:3"),
        ({"intent": "booking", "units_requested": 2}, None),
        ({"intent": "complaint", "private_event": True}, "intent:complaint"),
    ],
)
def test_live_guards(overrides, reason):
    assert escalation_reason(classification(**overrides), live=True) == reason


def test_demo_guards_ignore_live_rules():
    wedding = classification(intent="events", private_event=True)
    assert escalation_reason(wedding) == "intent:events"
    assert escalation_reason(classification(units_requested=5)) is None
