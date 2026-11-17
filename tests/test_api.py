import pytest
from fastapi.testclient import TestClient

from casavaiano.agent.graph import Assistant
from casavaiano.agent.state import Classification, EscalationDraft
from casavaiano.api.main import MAX_MESSAGE_CHARS, create_app
from casavaiano.config import Settings
from casavaiano.llm import LLMError
from casavaiano.llm.fake import FakeLLM
from casavaiano.observability import Tracer
from casavaiano.rag.retriever import RetrievedChunk

CHUNK = RetrievedChunk("policies:3", "Dogs: €15 per night.", "policies", ("Pets",), 0.9)


class StubRetriever:
    def search(self, query, k=None):
        return [CHUNK]


def handler(request):
    if request.name == "classify":
        complaint = "sporca" in request.messages[0]["content"]
        return Classification(
            intent="complaint" if complaint else "pets",
            secondary_intents=[],
            language="it",
            confidence=0.9,
            risk_flags=["complaint"] if complaint else [],
            group_size=None,
            search_query="dogs",
        )
    if request.name == "escalate":
        return EscalationDraft(owner_summary="s", priority="high", draft_reply="d", missing_info=[])
    return "Sì, €15 a notte."


def fake_assistant() -> Assistant:
    settings = Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None)
    return Assistant(FakeLLM(handler), StubRetriever(), settings, Tracer(settings))


@pytest.fixture
def client():
    return TestClient(create_app(fake_assistant))


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert "routing" in body


def test_chat_answer(client):
    body = client.post("/chat", json={"message": "Accettate cani?"}).json()
    assert body["status"] == "answered"
    assert body["reply"] == "Sì, €15 a notte."
    assert body["intent"] == "pets"
    assert body["sources"] == ["policies:3"]
    assert body["cost_usd"] > 0
    assert [c["node"] for c in body["calls"]] == ["classify", "decide"]


def test_chat_escalation(client):
    body = client.post("/chat", json={"message": "La camera era sporca!"}).json()
    assert body["status"] == "escalated"
    assert body["escalation"]["priority"] == "high"
    assert "Giulia" in body["reply"]


@pytest.mark.parametrize("message", ["", "x" * (MAX_MESSAGE_CHARS + 1)])
def test_message_length_is_validated(client, message):
    assert client.post("/chat", json={"message": message}).status_code == 422


def test_unconfigured_assistant_returns_503():
    def missing_key():
        raise LLMError("ANTHROPIC_API_KEY is not set")

    client = TestClient(create_app(missing_key))
    assert client.post("/chat", json={"message": "hi"}).status_code == 503
    assert client.get("/health").status_code == 200


def test_unexpected_error_returns_500_without_details():
    class Broken:
        def run(self, *args, **kwargs):
            raise RuntimeError("secret internal detail")

    client = TestClient(create_app(lambda: Broken()), raise_server_exceptions=False)
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 500
    assert "secret" not in response.text


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "CasaVaiano" in response.text
