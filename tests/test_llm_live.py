"""Smoke tests against the real API. Run with: uv run pytest -m live"""

from typing import Literal

import pytest
from pydantic import BaseModel

from casavaiano.config import get_settings
from casavaiano.llm import LLMRequest
from casavaiano.llm.anthropic_client import default_client
from casavaiano.observability import get_tracer

pytestmark = pytest.mark.live


class Detected(BaseModel):
    language: Literal["it", "en", "de", "other"]
    topic: Literal["pets", "prices", "other"]


@pytest.fixture(scope="module")
def client():
    if not get_settings().anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return default_client()


def test_cheap_model_structured_output(client):
    tracer = get_tracer()
    with tracer.trace("live-smoke", input="Dürfen wir unseren Hund mitbringen?", tags=["test"]):
        result = client.complete(
            LLMRequest(
                model=get_settings().cheap_model,
                system="Detect the language and topic of the guest message.",
                messages=[{"role": "user", "content": "Dürfen wir unseren Hund mitbringen?"}],
                max_tokens=512,
                effort="low",
                disable_thinking=True,
                output_schema=Detected,
                name="detect",
            )
        )
        trace_id = tracer.current_trace_id()
    tracer.flush()
    assert result.parsed == Detected(language="de", topic="pets")
    assert result.usage.input_tokens > 0
    assert result.cost_usd > 0
    print(f"\ncheap: {result.latency_ms:.0f} ms, ${result.cost_usd:.6f}, {result.usage}")
    print(f"trace: {tracer.trace_url(trace_id)}")


def test_strong_model_plain_answer(client):
    result = client.complete(
        LLMRequest(
            model=get_settings().strong_model,
            messages=[{"role": "user", "content": "Reply with exactly the word: ciao"}],
            max_tokens=1024,
            effort="low",
            name="echo",
        )
    )
    get_tracer().flush()
    assert "ciao" in result.text.lower()
    print(f"\nstrong: {result.latency_ms:.0f} ms, ${result.cost_usd:.6f}, {result.usage}")
