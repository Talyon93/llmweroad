from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from casavaiano.llm.base import LLMRequest, LLMResult, ToolCall, Usage
from casavaiano.llm.models import cost_usd


@dataclass
class FakeReply:
    text: str = ""
    parsed: BaseModel | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    latency_ms: float = 5.0


Handler = Callable[[LLMRequest], FakeReply | BaseModel | str]


class FakeLLM:
    """Scripted LLMClient for tests. The handler decides the reply from the request."""

    def __init__(self, handler: Handler):
        self.handler = handler
        self.requests: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        reply = self.handler(request)
        if isinstance(reply, str):
            reply = FakeReply(text=reply)
        elif isinstance(reply, BaseModel):
            reply = FakeReply(text=reply.model_dump_json(), parsed=reply)
        prompt = request.system + str(request.messages)
        usage = Usage(input_tokens=len(prompt) // 4, output_tokens=max(len(reply.text) // 4, 1))
        content: list[Any] = [{"type": "text", "text": reply.text}] if reply.text else []
        content += [
            {"type": "tool_use", "id": t.id, "name": t.name, "input": t.input}
            for t in reply.tool_calls
        ]
        return LLMResult(
            text=reply.text,
            model=request.model,
            usage=usage,
            cost_usd=cost_usd(request.model, usage),
            latency_ms=reply.latency_ms,
            stop_reason="tool_use" if reply.tool_calls else "end_turn",
            tool_calls=reply.tool_calls,
            parsed=reply.parsed,
            content=content,
        )

    def calls(self, name: str) -> list[LLMRequest]:
        return [r for r in self.requests if r.name == name]
