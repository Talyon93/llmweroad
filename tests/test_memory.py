from datetime import date

from fastapi.testclient import TestClient

from casavaiano.agent.graph import Assistant
from casavaiano.agent.memory import MAX_CHARS, ConversationStore
from casavaiano.agent.state import Classification, EscalationDraft
from casavaiano.api.main import create_app
from casavaiano.config import Settings
from casavaiano.llm.fake import FakeLLM
from casavaiano.observability import Tracer
from casavaiano.rag.retriever import RetrievedChunk

TODAY = date(2026, 11, 19)
SETTINGS = Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None)


class StubRetriever:
    def search(self, query, k=None):
        return [RetrievedChunk("policies:3", "Dogs: €15 per night.", "policies", ("Pets",), 0.9)]


def classification(intent="pets"):
    return Classification(
        intent=intent,
        secondary_intents=[],
        language="it",
        confidence=0.95,
        risk_flags=["complaint"] if intent == "complaint" else [],
        group_size=None,
        search_query="q",
    )


def make(handler):
    fake = FakeLLM(handler)
    return Assistant(fake, StubRetriever(), SETTINGS, Tracer(SETTINGS)), fake


def test_store_keeps_recent_turns_per_session():
    store = ConversationStore(max_turns=2)
    assert store.history(None) == []
    assert store.history("unknown") == []
    for i in range(3):
        store.add("a", f"q{i}", f"r{i}")
    store.add("b", "other", "reply")
    store.add(None, "ignored", "ignored")
    assert store.history("a") == [("q1", "r1"), ("q2", "r2")]
    assert store.history("b") == [("other", "reply")]


def test_store_expires_trims_and_evicts():
    expired = ConversationStore(ttl_seconds=-1)
    expired.add("a", "q", "r")
    assert expired.history("a") == []
    small = ConversationStore(max_sessions=2)
    for session in ("a", "b", "c"):
        small.add(session, "q", "r")
    assert small.history("a") == [] and small.history("c") == [("q", "r")]
    long = ConversationStore()
    long.add("a", "x" * (MAX_CHARS + 100), "r")
    assert len(long.history("a")[0][0]) == MAX_CHARS


def test_history_reaches_classifier_and_answer_model():
    history = [("Avete posto dal 10 al 17 luglio?", "Sì, Ulivo è libero: €345.")]

    def handler(r):
        return classification() if r.name == "classify" else "Sì, anche con il cane: €345 più €15."

    assistant, fake = make(handler)
    response = assistant.run("E con un cane?", today=TODAY, history=history)

    classify_prompt = fake.calls("classify")[0].messages[0]["content"]
    assert "<previous_conversation>" in classify_prompt
    assert "dal 10 al 17 luglio" in classify_prompt
    decide = fake.calls("decide")[0].messages
    assert [m["role"] for m in decide] == ["user", "assistant", "user"]
    assert decide[1]["content"] == "Sì, Ulivo è libero: €345."
    assert "E con un cane?" in decide[2]["content"]
    assert "do not greet again" in decide[2]["content"]
    assert response.status == "answered"  # €345 is grounded by the earlier reply


def test_history_reaches_the_escalation_draft():
    def handler(r):
        if r.name == "classify":
            return classification("complaint")
        return EscalationDraft(owner_summary="s", priority="high", draft_reply="d", missing_info=[])

    assistant, fake = make(handler)
    assistant.run("E la doccia non va!", today=TODAY, history=[("Siamo in Ulivo", "Benvenuti!")])
    assert "Siamo in Ulivo" in fake.calls("escalate")[0].messages[0]["content"]


def test_api_remembers_by_session_id():
    def handler(r):
        return classification() if r.name == "classify" else "Sì, €15 a notte."

    fake = FakeLLM(handler)
    assistant = Assistant(fake, StubRetriever(), SETTINGS, Tracer(SETTINGS))

    class QuietNotifier:
        def send(self, *args, **kwargs):
            return True

    client = TestClient(create_app(lambda: assistant, settings=SETTINGS, notifier=QuietNotifier()))
    client.post("/chat", json={"message": "Accettate cani?", "session_id": "s1"})
    client.post("/chat", json={"message": "E gatti?", "session_id": "s1"})
    client.post("/chat", json={"message": "Ciao", "session_id": "s2"})
    client.post("/chat", json={"message": "Senza sessione"})

    prompts = [r.messages[0]["content"] for r in fake.calls("classify")]
    assert "<previous_conversation>" not in prompts[0]
    assert "Accettate cani?" in prompts[1] and "Sì, €15 a notte." in prompts[1]
    assert "<previous_conversation>" not in prompts[2]
    assert "<previous_conversation>" not in prompts[3]
