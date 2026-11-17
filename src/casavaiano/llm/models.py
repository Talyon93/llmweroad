"""Model capabilities and prices. Prices in USD per 1M tokens (Anthropic first-party, Nov 2026).

Cache writes (5-minute TTL) cost 1.25x input. Haiku 5.5 prices apply to prompts up to 100K tokens,
which covers every request in this app.
"""

from dataclasses import dataclass

from casavaiano.llm.base import Usage


@dataclass(frozen=True)
class ModelSpec:
    input: float
    output: float
    cache_read: float
    can_disable_thinking: bool
    server_fallback: bool

    @property
    def cache_write(self) -> float:
        return self.input * 1.25


MODELS: dict[str, ModelSpec] = {
    "claude-haiku-5-5": ModelSpec(
        0.10, 0.50, 0.01, can_disable_thinking=True, server_fallback=False
    ),
    "claude-sonnet-5-5": ModelSpec(
        2.00, 10.00, 0.10, can_disable_thinking=False, server_fallback=True
    ),
    "claude-opus-5-5": ModelSpec(
        4.00, 20.00, 0.20, can_disable_thinking=False, server_fallback=True
    ),
}


def spec(model: str) -> ModelSpec:
    try:
        return MODELS[model]
    except KeyError:
        raise ValueError(f"Unknown model {model!r}; add it to casavaiano.llm.models") from None


def cost_breakdown(model: str, usage: Usage) -> dict[str, float]:
    s = spec(model)
    parts = {
        "input": usage.input_tokens * s.input,
        "output": usage.output_tokens * s.output,
        "cache_read_input_tokens": usage.cache_read_input_tokens * s.cache_read,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens * s.cache_write,
    }
    parts = {k: v / 1_000_000 for k, v in parts.items()}
    parts["total"] = sum(parts.values())
    return parts


def cost_usd(model: str, usage: Usage) -> float:
    return cost_breakdown(model, usage)["total"]
