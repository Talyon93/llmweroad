import operator
from datetime import date
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

Intent = Literal[
    "booking",
    "prices",
    "rooms",
    "pets",
    "restaurant",
    "events",
    "checkin",
    "directions",
    "services",
    "policies",
    "booking_change",
    "complaint",
    "other",
]

RiskFlag = Literal[
    "complaint",
    "refund_request",
    "booking_change",
    "discount_request",
    "payment_issue",
    "legal_or_safety",
    "abusive",
    "prompt_injection",
]

Priority = Literal["low", "normal", "high"]


class Classification(BaseModel):
    intent: Intent = Field(description="Main intent of the guest message")
    secondary_intents: list[Intent] = Field(description="Other intents in the same message")
    language: str = Field(description="ISO 639-1 code of the guest's language, e.g. it, en, de")
    confidence: float = Field(description="0 to 1: how sure you are about the intent")
    risk_flags: list[RiskFlag]
    group_size: int | None = Field(description="Number of people mentioned, if any")
    search_query: str = Field(
        description="Short English search query for the knowledge base, covering every question"
    )


class EscalationDraft(BaseModel):
    owner_summary: str = Field(description="2-3 sentences in English for the owner")
    priority: Priority
    draft_reply: str = Field(description="Reply to the guest in the guest's language")
    missing_info: list[str] = Field(description="What the owner must check or decide")


class CallRecord(BaseModel):
    node: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cost_usd: float
    latency_ms: float


class ToolRecord(BaseModel):
    name: str
    input: dict[str, Any]
    output: dict[str, Any]


class AgentState(TypedDict, total=False):
    message: str
    history: list[tuple[str, str]]
    today: date
    classification: Classification
    escalation_reason: str | None
    chunks: list[Any]
    messages: list[dict[str, Any]]
    pending_tool_calls: list[Any]
    answer_model: str
    iterations: int
    reply: str
    escalation: EscalationDraft | None
    calls: Annotated[list[CallRecord], operator.add]
    tools: Annotated[list[ToolRecord], operator.add]


class AssistantResponse(BaseModel):
    status: Literal["answered", "escalated"]
    reply: str
    intent: Intent
    language: str
    escalation_reason: str | None = None
    escalation: EscalationDraft | None = None
    sources: list[str] = []
    tools: list[ToolRecord] = []
    calls: list[CallRecord] = []
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    trace_id: str | None = None
