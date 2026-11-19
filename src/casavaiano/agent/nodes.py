from typing import Any

from casavaiano.agent import prompts
from casavaiano.agent.grounding import numbers_in_sources, ungrounded_amounts
from casavaiano.agent.guards import escalation_reason
from casavaiano.agent.routing import Route, answer_route, classify_route, escalate_route
from casavaiano.agent.state import (
    AgentState,
    CallRecord,
    Classification,
    EscalationDraft,
    ToolRecord,
)
from casavaiano.config import Settings
from casavaiano.llm import LLMClient, LLMError, LLMRequest, LLMResult
from casavaiano.observability import Tracer
from casavaiano.rag.retriever import RetrievedChunk, Retriever
from casavaiano.tools.registry import ESCALATE_TOOL, make_toolbox, tool_result_block

FALLBACK_CLASSIFICATION = Classification(
    intent="other",
    secondary_intents=[],
    language="en",
    confidence=0.0,
    risk_flags=[],
    group_size=None,
    search_query="",
)


class Nodes:
    def __init__(self, llm: LLMClient, retriever: Retriever, settings: Settings, tracer: Tracer):
        self.llm = llm
        self.retriever = retriever
        self.settings = settings
        self.tracer = tracer
        self.persona = prompts.persona(settings)
        self.toolbox = make_toolbox(settings)

    def classify(self, state: AgentState) -> dict[str, Any]:
        primary = classify_route(self.settings)
        routes = [primary]
        if primary.model != self.settings.strong_model:
            routes.append(Route(self.settings.strong_model, "low"))
        calls = []
        for route in routes:
            try:
                result = self._call(
                    "classify",
                    route,
                    prompts.CLASSIFY_SYSTEM,
                    [
                        {
                            "role": "user",
                            "content": prompts.classify_user(
                                state["message"], state.get("history")
                            ),
                        }
                    ],
                    max_tokens=2048,
                    output_schema=Classification,
                )
            except LLMError:
                continue
            calls.append(_record("classify", result))
            return {"classification": result.parsed, "calls": calls}
        return {
            "classification": FALLBACK_CLASSIFICATION,
            "escalation_reason": "classification_failed",
            "calls": calls,
        }

    def guard(self, state: AgentState) -> dict[str, Any]:
        if state.get("escalation_reason"):
            return {}
        return {"escalation_reason": escalation_reason(state["classification"], self.persona.live)}

    def retrieve(self, state: AgentState) -> dict[str, Any]:
        c = state["classification"]
        mode = self.settings.retrieval_query
        queries = []
        if mode in ("original", "both") or not c.search_query:
            queries.append(state["message"])
        if mode in ("rewritten", "both") and c.search_query:
            queries.append(c.search_query)
        with self.tracer.span("retrieve", as_type="retriever", input=queries) as span:
            best: dict[str, RetrievedChunk] = {}
            for query in queries:
                for chunk in self.retriever.search(query, self.settings.retrieval_k):
                    if chunk.id not in best or chunk.score > best[chunk.id].score:
                        best[chunk.id] = chunk
            chunks = sorted(best.values(), key=lambda c: c.score, reverse=True)
            chunks = chunks[: self.settings.retrieval_k + 2]
            named = getattr(self.retriever, "named", lambda _: [])(state["message"])
            sources = {c.source for c in [*named, *chunks]}
            intros = getattr(self.retriever, "overviews", lambda _: [])(sources)
            first = [*named, *[i for i in intros if i.id not in {n.id for n in named}]]
            chunks = [*first, *[c for c in chunks if c.id not in {f.id for f in first}]]
            span.update(output=[{"id": c.id, "score": c.score} for c in chunks])
        return {"chunks": chunks}

    def decide(self, state: AgentState) -> dict[str, Any]:
        c = state["classification"]
        iterations = state.get("iterations", 0)
        if iterations >= self.settings.max_tool_iterations:
            return {"escalation_reason": "tool_loop_limit", "pending_tool_calls": []}
        route = answer_route(self.settings, c)
        messages = state.get("messages") or [
            *_history_messages(state.get("history")),
            {
                "role": "user",
                "content": prompts.answer_user(
                    state["message"],
                    state["today"],
                    c,
                    prompts.format_context(state["chunks"]),
                    continuing=bool(state.get("history")),
                ),
            },
        ]
        try:
            result = self._call(
                "decide",
                route,
                prompts.answer_system(self.persona),
                messages,
                4096,
                tools=self.toolbox.definitions(),
            )
        except LLMError as exc:
            return {"escalation_reason": f"llm_error:{type(exc).__name__}"}
        update: dict[str, Any] = {
            "messages": [*messages, {"role": "assistant", "content": result.content}],
            "answer_model": route.model,
            "iterations": iterations + 1,
            "calls": [_record("decide", result)],
            "pending_tool_calls": result.tool_calls,
        }
        escalate = next((t for t in result.tool_calls if t.name == ESCALATE_TOOL), None)
        if escalate:
            update["escalation_reason"] = f"llm:{escalate.input.get('reason', '')}"[:200]
            update["pending_tool_calls"] = []
        elif not result.tool_calls:
            update["reply"] = result.text.strip()
        return update

    def tools(self, state: AgentState) -> dict[str, Any]:
        blocks, records = [], []
        for call in state["pending_tool_calls"]:
            with self.tracer.span(call.name, as_type="tool", input=call.input) as span:
                output = self.toolbox.run(call.name, call.input, state["today"])
                span.update(output=output)
            blocks.append(tool_result_block(call.id, output))
            records.append(ToolRecord(name=call.name, input=call.input, output=output))
        return {
            "messages": [*state["messages"], {"role": "user", "content": blocks}],
            "pending_tool_calls": [],
            "tools": records,
        }

    def answer(self, state: AgentState) -> dict[str, Any]:
        earlier_replies = [reply for _, reply in state.get("history") or []]
        sources = numbers_in_sources(
            [c.text for c in state["chunks"]] + earlier_replies,
            [t.output for t in state.get("tools", [])],
        )
        ungrounded = ungrounded_amounts(state.get("reply", ""), sources)
        if ungrounded:
            return {"escalation_reason": f"ungrounded_amounts:{ungrounded}"}
        if not state.get("reply"):
            return {"escalation_reason": "empty_reply"}
        language = state["classification"].language
        reply = prompts.plain_text(state["reply"])
        return {"reply": prompts.localize_signature(reply, language, self.persona)}

    def escalate(self, state: AgentState) -> dict[str, Any]:
        c = state.get("classification")
        reason = state.get("escalation_reason") or "unknown"
        language = c.language if c else "en"
        user = prompts.escalate_user(
            state["message"],
            state["today"],
            c,
            reason,
            prompts.format_context(state.get("chunks", [])),
            state.get("history"),
        )
        try:
            result = self._call(
                "escalate",
                escalate_route(self.settings),
                prompts.escalate_system(self.persona),
                [{"role": "user", "content": user}],
                4096,
                output_schema=EscalationDraft,
            )
            draft, calls = result.parsed, [_record("escalate", result)]
        except LLMError:
            draft = EscalationDraft(
                owner_summary=f"Automatic draft failed. Escalation reason: {reason}.",
                priority="high",
                draft_reply="",
                missing_info=["Read the original message and reply manually"],
            )
            calls = []
        return {
            "escalation": draft,
            "reply": prompts.acknowledgement(language, self.persona),
            "calls": calls,
        }

    def _call(
        self,
        name: str,
        route: Route,
        system: str,
        messages: list[dict[str, Any]],
        max_tokens: int,
        output_schema=None,
        tools=None,
    ) -> LLMResult:
        return self.llm.complete(
            LLMRequest(
                model=route.model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                effort=route.effort,
                disable_thinking=route.model == self.settings.cheap_model,
                output_schema=output_schema,
                tools=tools,
                name=name,
            )
        )


def _history_messages(history: list[tuple[str, str]] | None) -> list[dict[str, Any]]:
    """Earlier turns as alternating user/assistant messages before the current one."""
    messages: list[dict[str, Any]] = []
    for guest, reply in history or []:
        content = f"<guest_message>\n{guest}\n</guest_message>"
        messages.append({"role": "user", "content": content})
        messages.append({"role": "assistant", "content": reply})
    return messages


def _record(node: str, result: LLMResult) -> CallRecord:
    return CallRecord(
        node=node,
        model=result.model,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cache_read_input_tokens=result.usage.cache_read_input_tokens,
        cost_usd=result.cost_usd,
        latency_ms=result.latency_ms,
    )
