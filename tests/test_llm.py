from types import SimpleNamespace
from typing import Literal

import pytest
from pydantic import BaseModel

from casavaiano.config import Settings
from casavaiano.llm import LLMRefusal, LLMRequest, ToolCall, Usage
from casavaiano.llm.anthropic_client import SERVER_FALLBACK_BETA, AnthropicClient
from casavaiano.llm.fake import FakeLLM, FakeReply
from casavaiano.llm.models import cost_breakdown, cost_usd, spec
from casavaiano.llm.schema import strict_json_schema
from casavaiano.observability import Tracer


class Inner(BaseModel):
    note: str | None = None


class Classification(BaseModel):
    intent: Literal["pricing", "pets"]
    confidence: float = 0.5
    tags: list[str]
    inner: Inner


def disabled_tracer() -> Tracer:
    return Tracer(Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None))


def client_with_response(response) -> AnthropicClient:
    client = AnthropicClient(api_key="test-key", tracer=disabled_tracer())
    create = lambda **kwargs: (client.sent.append(kwargs), response)[1]  # noqa: E731
    client.sent = []
    client._client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return client


def fake_response(content, stop_reason="end_turn", model="claude-haiku-5-5"):
    usage = SimpleNamespace(
        input_tokens=1000,
        output_tokens=200,
        cache_read_input_tokens=None,
        cache_creation_input_tokens=0,
    )
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, model=model, usage=usage, stop_details=None
    )


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def test_cost_math():
    usage = Usage(input_tokens=1_000, output_tokens=500)
    assert cost_usd("claude-opus-5-5", usage) == pytest.approx(0.004 + 0.010)
    assert cost_usd("claude-haiku-5-5", usage) == pytest.approx(0.0001 + 0.00025)
    cached = cost_breakdown("claude-opus-5-5", Usage(cache_read_input_tokens=1_000_000))
    assert cached["total"] == pytest.approx(0.20)
    assert spec("claude-opus-5-5").cache_write == pytest.approx(5.0)


def test_unknown_model_is_an_error():
    with pytest.raises(ValueError, match="Unknown model"):
        cost_usd("gpt-whatever", Usage())


def test_usage_adds_up():
    assert Usage(1, 2, 3, 4) + Usage(10, 20, 30, 40) == Usage(11, 22, 33, 44)


def test_strict_schema_closes_every_object():
    schema = strict_json_schema(Classification)
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["intent", "confidence", "tags", "inner"]
    inner = schema["$defs"]["Inner"]
    assert inner["additionalProperties"] is False
    assert inner["required"] == ["note"]
    assert "default" not in str(schema)
    assert "'title'" not in str(schema)
    assert schema["properties"]["intent"]["enum"] == ["pricing", "pets"]


def test_cheap_model_request_shape():
    client = client_with_response(
        fake_response([text_block('{"intent":"pets","confidence":0.9,"tags":[],"inner":{}}')])
    )
    request = LLMRequest(
        model="claude-haiku-5-5",
        system="sys",
        messages=[{"role": "user", "content": "Hunde?"}],
        effort="low",
        disable_thinking=True,
        output_schema=Classification,
    )
    result = client.complete(request)
    sent = client.sent[0]
    assert sent["thinking"] == {"type": "disabled"}
    assert sent["output_config"]["effort"] == "low"
    assert sent["output_config"]["format"]["type"] == "json_schema"
    assert sent["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "betas" not in sent
    assert result.parsed == Classification(intent="pets", confidence=0.9, tags=[], inner=Inner())
    assert result.cost_usd == pytest.approx(cost_usd("claude-haiku-5-5", Usage(1000, 200)))
    assert result.latency_ms >= 0


def test_strong_model_gets_server_fallback_and_keeps_thinking():
    client = client_with_response(fake_response([text_block("ok")], model="claude-opus-5-5"))
    client.complete(
        LLMRequest(
            model="claude-opus-5-5",
            messages=[{"role": "user", "content": "hi"}],
            disable_thinking=True,
        )
    )
    sent = client.sent[0]
    assert sent["betas"] == [SERVER_FALLBACK_BETA]
    assert sent["fallbacks"] == "default"
    assert "thinking" not in sent
    assert "system" not in sent


def test_tool_calls_are_extracted():
    tool_block = SimpleNamespace(type="tool_use", id="t1", name="quote", input={"unit": "ulivo"})
    client = client_with_response(
        fake_response([text_block("Let me check."), tool_block], "tool_use")
    )
    result = client.complete(
        LLMRequest(model="claude-haiku-5-5", messages=[{"role": "user", "content": "price?"}])
    )
    assert result.tool_calls == [ToolCall("t1", "quote", {"unit": "ulivo"})]
    assert result.text == "Let me check."
    assert result.content[1] is tool_block


def test_refusal_raises():
    client = client_with_response(fake_response([], stop_reason="refusal"))
    with pytest.raises(LLMRefusal):
        client.complete(
            LLMRequest(model="claude-haiku-5-5", messages=[{"role": "user", "content": "x"}])
        )


def test_fake_llm_records_requests_and_prices_usage():
    fake = FakeLLM(
        lambda r: (
            Classification(intent="pets", tags=[], inner=Inner())
            if r.name == "classify"
            else FakeReply(tool_calls=[ToolCall("1", "quote", {})])
        )
    )
    parsed = fake.complete(LLMRequest(model="claude-haiku-5-5", messages=[], name="classify"))
    tool = fake.complete(LLMRequest(model="claude-opus-5-5", messages=[], name="answer"))
    assert parsed.parsed.intent == "pets"
    assert tool.stop_reason == "tool_use"
    assert tool.content == [{"type": "tool_use", "id": "1", "name": "quote", "input": {}}]
    assert parsed.cost_usd > 0
    assert len(fake.calls("classify")) == 1


def test_disabled_tracer_is_a_no_op():
    tracer = disabled_tracer()
    assert not tracer.enabled
    with tracer.trace("run", input="x") as root, tracer.span("child") as child:
        root.update(output="y")
        child.update(output="z")
    assert tracer.current_trace_id() is None
    assert tracer.trace_url("abc") is None
    tracer.flush()


def test_sdk_tracing_is_off_to_avoid_double_counted_cost():
    client = AnthropicClient(api_key="test-key", tracer=disabled_tracer())
    assert not client._client.open_telemetry["traces"]["enabled"]
