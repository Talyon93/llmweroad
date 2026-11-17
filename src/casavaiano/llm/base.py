from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class LLMError(Exception):
    pass


class LLMRefusal(LLMError):
    pass


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_input_tokens + other.cache_read_input_tokens,
            self.cache_creation_input_tokens + other.cache_creation_input_tokens,
        )


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass
class LLMRequest:
    model: str
    messages: list[dict[str, Any]]
    system: str = ""
    max_tokens: int = 4096
    effort: Effort | None = None
    disable_thinking: bool = False
    output_schema: type[BaseModel] | None = None
    tools: list[dict[str, Any]] | None = None
    name: str = "llm"


@dataclass
class LLMResult:
    text: str
    model: str
    usage: Usage
    cost_usd: float
    latency_ms: float
    stop_reason: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    parsed: BaseModel | None = None
    content: list[Any] = field(default_factory=list)


class LLMClient(Protocol):
    def complete(self, request: LLMRequest) -> LLMResult: ...
