import time
from typing import Any

import anthropic

from casavaiano.llm.base import LLMError, LLMRefusal, LLMRequest, LLMResult, ToolCall, Usage
from casavaiano.llm.models import MODELS, cost_breakdown, spec
from casavaiano.llm.schema import strict_json_schema
from casavaiano.observability import Tracer, get_tracer

SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicClient:
    """LLMClient on the Anthropic Messages API.

    - structured output via output_config.format (forced tool_choice is not available on 5.5 models)
    - server-side refusal fallback on models that support it
    - every call recorded as a Langfuse generation with tokens, latency and cost
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        tracer: Tracer | None = None,
    ):
        # The SDK emits its own OpenTelemetry generation span, which Langfuse also ingests:
        # every call would then be counted twice. We record our own, named per graph node.
        self._client = anthropic.Anthropic(
            api_key=api_key, timeout=timeout, max_retries=max_retries, open_telemetry=False
        )
        self._tracer = tracer or get_tracer()

    def complete(self, request: LLMRequest) -> LLMResult:
        kwargs = self._build_kwargs(request)
        params = {
            k: v for k, v in kwargs.items() if k in ("max_tokens", "output_config", "thinking")
        }
        with self._tracer.span(
            request.name,
            as_type="generation",
            model=request.model,
            input={"system": request.system, "messages": _jsonable(request.messages)},
            model_parameters={k: str(v) for k, v in params.items()},
        ) as generation:
            started = time.perf_counter()
            try:
                response = self._client.beta.messages.create(**kwargs)
            except anthropic.APIError as exc:
                generation.update(level="ERROR", status_message=str(exc))
                raise LLMError(f"{request.name}: {exc}") from exc
            latency_ms = (time.perf_counter() - started) * 1000
            result = self._to_result(request, response, latency_ms)
            generation.update(
                model=result.model,
                output=result.parsed.model_dump() if result.parsed else _output(result),
                usage_details=_usage_details(result.usage),
                cost_details=cost_breakdown(result.model, result.usage),
                metadata={"stop_reason": result.stop_reason, "latency_ms": round(latency_ms)},
            )
        if result.stop_reason == "refusal":
            raise LLMRefusal(f"{request.name}: model refused ({response.stop_details})")
        return result

    def _build_kwargs(self, request: LLMRequest) -> dict[str, Any]:
        model = spec(request.model)
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": request.messages,
        }
        if request.system:
            kwargs["system"] = [
                {"type": "text", "text": request.system, "cache_control": {"type": "ephemeral"}}
            ]
        output_config: dict[str, Any] = {}
        if request.effort:
            output_config["effort"] = request.effort
        if request.output_schema:
            output_config["format"] = {
                "type": "json_schema",
                "schema": strict_json_schema(request.output_schema),
            }
        if output_config:
            kwargs["output_config"] = output_config
        if request.disable_thinking and model.can_disable_thinking:
            kwargs["thinking"] = {"type": "disabled"}
        if request.tools:
            kwargs["tools"] = request.tools
        if model.server_fallback:
            kwargs["betas"] = [SERVER_FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def _to_result(self, request: LLMRequest, response: Any, latency_ms: float) -> LLMResult:
        u = response.usage
        usage = Usage(
            input_tokens=u.input_tokens or 0,
            output_tokens=u.output_tokens or 0,
            cache_read_input_tokens=u.cache_read_input_tokens or 0,
            cache_creation_input_tokens=u.cache_creation_input_tokens or 0,
        )
        # A server-side fallback may serve the turn with another model; price it when we know it.
        served_model = response.model if response.model in MODELS else request.model
        text = "".join(b.text for b in response.content if b.type == "text")
        tool_calls = [
            ToolCall(b.id, b.name, dict(b.input)) for b in response.content if b.type == "tool_use"
        ]
        parsed = None
        if request.output_schema and response.stop_reason not in ("refusal", "max_tokens"):
            parsed = request.output_schema.model_validate_json(text)
        return LLMResult(
            text=text,
            model=served_model,
            usage=usage,
            cost_usd=cost_breakdown(served_model, usage)["total"],
            latency_ms=latency_ms,
            stop_reason=response.stop_reason or "",
            tool_calls=tool_calls,
            parsed=parsed,
            content=list(response.content),
        )


def default_client() -> AnthropicClient:
    from casavaiano.config import get_settings

    key = get_settings().anthropic_api_key
    if not key:
        raise LLMError("ANTHROPIC_API_KEY is not set; add it to .env")
    return AnthropicClient(api_key=key.get_secret_value())


def _usage_details(usage: Usage) -> dict[str, int]:
    return {
        "input": usage.input_tokens,
        "output": usage.output_tokens,
        "cache_read_input_tokens": usage.cache_read_input_tokens,
        "cache_creation_input_tokens": usage.cache_creation_input_tokens,
    }


def _output(result: LLMResult) -> Any:
    if result.tool_calls:
        return {"text": result.text, "tool_calls": [vars(t) for t in result.tool_calls]}
    return result.text


def _jsonable(value: Any) -> Any:
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    return value
