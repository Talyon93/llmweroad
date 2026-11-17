"""Deterministic per-case checks: no LLM involved."""

import re

from pydantic import BaseModel

from casavaiano.agent.grounding import numbers_in_sources, parse_number
from casavaiano.agent.state import AssistantResponse
from casavaiano.evals.dataset import EvalCase
from casavaiano.rag.chunking import Chunk


class CaseChecks(BaseModel):
    intent_ok: bool
    language_ok: bool
    escalated: bool
    behavior_ok: bool
    retrieval_hit: bool | None = None
    tools_ok: bool | None = None
    tool_args_ok: bool | None = None
    facts_ok: bool | None = None
    missing_facts: list[list[str]] = []
    forbidden_found: list[str] = []


def fact_present(alternatives: list[str], text: str) -> bool:
    numbers = numbers_in_sources([text], [])
    for alt in alternatives:
        raw = alt.removeprefix("€")
        if alt.startswith("€") or re.fullmatch(r"\d+", alt):
            value = parse_number(raw)
            if value is not None and any(abs(value - n) < 0.006 for n in numbers):
                return True
        elif alt.lower() in text.lower():
            return True
    return False


def run_checks(case: EvalCase, response: AssistantResponse, chunks: dict[str, Chunk]) -> CaseChecks:
    escalated = response.status == "escalated"
    if escalated:
        behavior_ok = case.may_escalate
    else:
        behavior_ok = bool({"answer", "clarify"} & set(case.behavior))

    retrieval_hit = None
    if case.sources:
        retrieved = [chunks[i] for i in response.sources if i in chunks]
        retrieval_hit = any(
            c.source == src and (section == "*" or section in c.sections)
            for c in retrieved
            for src, section in case.sources
        )

    called = [t.name for t in response.tools]
    tools_ok = None
    if case.tools or case.tools_any:
        tools_ok = set(case.tools) <= set(called) and (
            not case.tools_any or bool(set(case.tools_any) & set(called))
        )
    tool_args_ok = None
    if case.tool_args:
        tool_args_ok = all(
            any(
                t.name == name and all(t.input.get(k) == v for k, v in expected.items())
                for t in response.tools
            )
            for name, expected in case.tool_args.items()
        )

    facts_ok, missing = None, []
    if case.must_include and not escalated:
        missing = [alts for alts in case.must_include if not fact_present(alts, response.reply)]
        facts_ok = not missing

    texts = [response.reply] + ([response.escalation.draft_reply] if response.escalation else [])
    forbidden = [p for p in case.must_not_include if any(p.lower() in t.lower() for t in texts)]

    return CaseChecks(
        intent_ok=response.intent in case.intent,
        language_ok=response.language == case.language,
        escalated=escalated,
        behavior_ok=behavior_ok,
        retrieval_hit=retrieval_hit,
        tools_ok=tools_ok,
        tool_args_ok=tool_args_ok,
        facts_ok=facts_ok,
        missing_facts=missing,
        forbidden_found=forbidden,
    )
