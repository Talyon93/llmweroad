from collections import Counter

import pytest

from casavaiano.agent.state import AssistantResponse, Classification, EscalationDraft, ToolRecord
from casavaiano.config import Settings
from casavaiano.evals.checks import CaseChecks, fact_present, run_checks
from casavaiano.evals.dataset import EvalCase, load_cases
from casavaiano.evals.judge import JudgeVerdict
from casavaiano.evals.metrics import is_correct, percentile, summarize
from casavaiano.evals.report import markdown_report
from casavaiano.evals.runner import RunConfig, run_eval, save_run
from casavaiano.llm import ToolCall
from casavaiano.llm.fake import FakeLLM, FakeReply
from casavaiano.observability import Tracer
from casavaiano.rag.chunking import chunk_kb

CHUNKS = {c.id: c for c in chunk_kb("headings")}
PETS_ID = next(i for i, c in CHUNKS.items() if c.sections == ("Pets",))


def case(**overrides) -> EvalCase:
    fields = dict(
        id="x",
        split="dev",
        language="it",
        message="Accettate cani?",
        intent=["pets"],
        behavior=["answer"],
        expected="Dogs in Ulivo and Fienile.",
    )
    return EvalCase(**(fields | overrides))


def response(**overrides) -> AssistantResponse:
    fields = dict(
        status="answered", reply="Sì, Ulivo e Fienile, €15.", intent="pets", language="it"
    )
    return AssistantResponse(**(fields | overrides))


def verdict(f=3, c=3, asks=False) -> JudgeVerdict:
    return JudgeVerdict(
        faithfulness=f,
        correctness=c,
        language_and_tone=3,
        asks_for_missing_info=asks,
        unsupported_claims=[],
        reasoning="ok",
    )


def test_dataset_is_well_formed():
    cases = load_cases()
    assert len(cases) >= 60
    assert len({c.id for c in cases}) == len(cases)
    languages = Counter(c.language for c in cases)
    assert all(languages[lang] >= 15 for lang in ("it", "en", "de"))
    intents = {c.intent[0] for c in cases}
    assert intents >= {"booking", "pets", "events", "complaint", "booking_change", "other"}
    assert sum(c.must_escalate for c in cases) >= 15
    assert 0.2 <= sum(c.split == "test" for c in cases) / len(cases) <= 0.3
    for c in cases:
        for source, section in c.sources:
            assert section == "*" or any(
                ch.source == source and section in ch.sections for ch in CHUNKS.values()
            ), (c.id, source, section)


@pytest.mark.parametrize(
    ("alternatives", "text", "expected"),
    [
        (["€1449"], "Totale €1.449 per 7 notti", True),
        (["€1449"], "Total 1,449 EUR", True),
        (["€1.50"], "€1,50 a persona", True),
        (["€15"], "costa €150", False),
        (["55"], "about 55 km", True),
        (["15"], "150 metres", False),
        (["15:00", "3 pm"], "check-in from 3 pm", True),
        (["gravel"], "a well-kept GRAVEL road", True),
    ],
)
def test_fact_present(alternatives, text, expected):
    assert fact_present(alternatives, text) is expected


def test_checks_for_a_good_answer():
    c = case(must_include=[["Ulivo"], ["€15"]], sources=[("policies", "Pets")])
    checks = run_checks(c, response(sources=[PETS_ID]), CHUNKS)
    assert checks.intent_ok and checks.language_ok and checks.behavior_ok
    assert checks.retrieval_hit and checks.facts_ok
    assert checks.tools_ok is None


def test_checks_for_tools_and_missing_facts():
    c = case(
        intent=["booking"],
        tools=["check_availability"],
        tools_any=["quote_stay"],
        tool_args={"check_availability": {"check_in": "2027-05-07"}},
        must_include=[["€345"]],
    )
    called = [ToolRecord(name="check_availability", input={"check_in": "2027-05-08"}, output={})]
    checks = run_checks(c, response(intent="booking", tools=called), CHUNKS)
    assert checks.tools_ok is False
    assert checks.tool_args_ok is False
    assert checks.missing_facts == [["€345"]]


def test_unexpected_escalation_fails_behavior():
    draft = EscalationDraft(owner_summary="s", priority="low", draft_reply="d", missing_info=[])
    checks = run_checks(case(), response(status="escalated", escalation=draft), CHUNKS)
    assert checks.escalated and not checks.behavior_ok
    assert checks.facts_ok is None


def checks_ok(**overrides) -> CaseChecks:
    fields = dict(intent_ok=True, language_ok=True, escalated=False, behavior_ok=True)
    return CaseChecks(**(fields | overrides))


def test_is_correct():
    assert is_correct(case(), checks_ok(), verdict())
    assert not is_correct(case(), checks_ok(), verdict(f=1))
    assert not is_correct(case(), checks_ok(facts_ok=False), verdict())
    assert not is_correct(case(), checks_ok(behavior_ok=False), verdict())
    must = case(behavior=["escalate"])
    assert is_correct(must, checks_ok(escalated=True), verdict(f=0))
    clarify = case(behavior=["clarify"])
    assert not is_correct(clarify, checks_ok(), verdict(asks=False))
    assert is_correct(clarify, checks_ok(), verdict(asks=True))


def test_percentile():
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile([], 95) == 0.0


def fake_result(behavior, escalated, correct, language="it"):
    return {
        "case": {"behavior": behavior, "language": language, "tags": []},
        "checks": {
            "intent_ok": True,
            "language_ok": True,
            "escalated": escalated,
            "behavior_ok": correct,
            "retrieval_hit": None,
            "tools_ok": None,
            "tool_args_ok": None,
            "facts_ok": None,
        },
        "response": {"latency_ms": 1000.0, "cost_usd": 0.01, "calls": []},
        "judge": None,
        "correct": correct,
    }


def test_escalation_precision_and_recall():
    results = [
        fake_result(["escalate"], True, True),
        fake_result(["escalate"], False, False),
        fake_result(["answer", "escalate"], True, True),
        fake_result(["answer"], True, False),
        fake_result(["answer"], False, True),
    ]
    s = summarize(results)
    assert s["escalation_recall"] == 0.5
    assert s["escalation_precision"] == round(2 / 3, 3)
    assert s["answer_correctness"] == 0.6
    assert s["cost_per_query_usd"] == 0.01


class StubRetriever:
    def search(self, query, k=None):
        return []


def test_run_eval_end_to_end_with_fakes(tmp_path):
    def handler(r):
        if r.name == "classify":
            text = r.messages[0]["content"]
            intent = "complaint" if "doccia" in text else "booking" if "May" in text else "pets"
            return Classification(
                intent=intent,
                secondary_intents=[],
                language="it" if intent != "booking" else "en",
                confidence=0.9,
                risk_flags=["complaint"] if intent == "complaint" else [],
                group_size=None,
                search_query="q",
            )
        if r.name == "decide" and "May" in r.messages[0]["content"] and len(r.messages) == 1:
            args = {"check_in": "2027-05-07", "check_out": "2027-05-10", "guests": 2, "dog": False}
            return FakeReply(tool_calls=[ToolCall("t1", "check_availability", args)])
        if r.name == "decide":
            return "Ulivo e Fienile accettano cani."
        if r.name == "escalate":
            return EscalationDraft(
                owner_summary="s", priority="high", draft_reply="d", missing_info=[]
            )
        return verdict()

    settings = Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None)
    config = RunConfig(
        label="fake", ids=["pets-it-01", "booking-en-01", "complaint-it-01"], concurrency=2
    )
    run = run_eval(config, FakeLLM(handler), Tracer(settings), retriever=StubRetriever())
    by_id = {r["case"]["id"]: r for r in run["results"]}

    assert run["summary"]["n"] == 3
    assert by_id["complaint-it-01"]["correct"]
    assert by_id["booking-en-01"]["checks"]["tool_args_ok"]
    assert not by_id["booking-en-01"]["correct"]
    assert by_id["pets-it-01"]["checks"]["facts_ok"] is False
    assert run["summary"]["escalation_recall"] == 1.0

    json_path, md_path = save_run(run, tmp_path)
    report = md_path.read_text(encoding="utf-8")
    assert "### booking-en-01" in report
    assert "### complaint-it-01" not in report
    assert markdown_report(run) == report
    assert json_path.exists()


def test_unsendable_tone_fails_even_if_facts_are_right():
    leaked = verdict()
    leaked.language_and_tone = 1
    assert not is_correct(case(), checks_ok(), leaked)
