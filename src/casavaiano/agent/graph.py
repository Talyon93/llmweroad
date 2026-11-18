"""The agent graph:

classify -> guard -> retrieve -> decide <-> tools
                                   |
                                 answer -> END
      (guard, decide or answer may route to) escalate -> END
"""

import time
from datetime import date
from typing import Any

from langgraph.graph import END, START, StateGraph

from casavaiano.agent.nodes import Nodes
from casavaiano.agent.state import AgentState, AssistantResponse
from casavaiano.config import Settings, get_settings
from casavaiano.llm import LLMClient
from casavaiano.observability import Tracer, get_tracer
from casavaiano.rag.retriever import Retriever, default_retriever


def build_graph(nodes: Nodes):
    graph = StateGraph(AgentState)
    for name in ("classify", "guard", "retrieve", "decide", "tools", "answer", "escalate"):
        graph.add_node(name, _traced(nodes.tracer, name, getattr(nodes, name)))
    graph.add_edge(START, "classify")
    graph.add_edge("classify", "guard")
    graph.add_edge("guard", "retrieve")
    graph.add_conditional_edges("retrieve", _after_retrieve, ["decide", "escalate"])
    graph.add_conditional_edges("decide", _after_decide, ["tools", "answer", "escalate"])
    graph.add_edge("tools", "decide")
    graph.add_conditional_edges("answer", _after_answer, ["escalate", END])
    graph.add_edge("escalate", END)
    return graph.compile()


def _after_retrieve(state: AgentState) -> str:
    return "escalate" if state.get("escalation_reason") else "decide"


def _after_decide(state: AgentState) -> str:
    if state.get("escalation_reason"):
        return "escalate"
    return "tools" if state.get("pending_tool_calls") else "answer"


def _after_answer(state: AgentState) -> str:
    return "escalate" if state.get("escalation_reason") else END


def _traced(tracer: Tracer, name: str, fn):
    if name in ("retrieve", "tools"):
        return fn

    def run(state: AgentState) -> dict[str, Any]:
        with tracer.span(name, as_type="chain") as span:
            update = fn(state)
            span.update(output=_summary(update))
        return update

    return run


def _summary(update: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, value in update.items():
        if key in ("messages", "calls", "tools", "chunks"):
            continue
        out[key] = value.model_dump() if hasattr(value, "model_dump") else str(value)
    return out


class Assistant:
    def __init__(
        self,
        llm: LLMClient,
        retriever: Retriever | None = None,
        settings: Settings | None = None,
        tracer: Tracer | None = None,
    ):
        self.settings = settings or get_settings()
        self.tracer = tracer or get_tracer()
        retriever = retriever or default_retriever(self.settings.chunking_strategy, self.settings)
        expected_kb = self.settings.knowledge_base_dir.resolve()
        if getattr(retriever, "kb_dir", expected_kb).resolve() != expected_kb:
            raise ValueError(
                f"Retriever reads {retriever.kb_dir} but the settings say {expected_kb}"
            )
        self.graph = build_graph(Nodes(llm, retriever, self.settings, self.tracer))

    def run(
        self,
        message: str,
        today: date | None = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
    ) -> AssistantResponse:
        started = time.perf_counter()
        metadata = {
            "routing": self.settings.routing_enabled,
            "chunking": self.settings.chunking_strategy,
            "retrieval_query": self.settings.retrieval_query,
            "cheap_model": self.settings.cheap_model,
            "strong_model": self.settings.strong_model,
        }
        with self.tracer.trace(
            "guest-inquiry", input=message, session_id=session_id, tags=tags, metadata=metadata
        ) as root:
            state = self.graph.invoke(
                {"message": message, "today": today or date.today(), "calls": [], "tools": []}
            )
            response = _response(state, (time.perf_counter() - started) * 1000)
            response.trace_id = self.tracer.current_trace_id()
            root.update(
                output=response.model_dump(include={"status", "reply", "intent", "escalation"})
            )
        return response


def _response(state: AgentState, latency_ms: float) -> AssistantResponse:
    c = state["classification"]
    calls = state.get("calls", [])
    escalation = state.get("escalation")
    return AssistantResponse(
        status="escalated" if escalation else "answered",
        reply=state.get("reply", ""),
        intent=c.intent,
        language=c.language,
        escalation_reason=state.get("escalation_reason") if escalation else None,
        escalation=escalation,
        sources=[chunk.id for chunk in state.get("chunks", [])],
        tools=state.get("tools", []),
        calls=calls,
        cost_usd=sum(call.cost_usd for call in calls),
        latency_ms=latency_ms,
    )
