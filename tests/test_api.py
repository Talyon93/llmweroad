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


class FakeNotifier:
    def __init__(self, ok=True):
        self.ok = ok
        self.sent = []

    def send(self, subject, body, reply_to=None):
        self.sent.append({"subject": subject, "body": body, "reply_to": reply_to})
        return self.ok


def make_client(notifier=None, **settings):
    s = Settings(_env_file=None, langfuse_public_key=None, langfuse_secret_key=None, **settings)
    return TestClient(create_app(fake_assistant, settings=s, notifier=notifier or FakeNotifier()))


@pytest.fixture
def client():
    return make_client()


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

    client = TestClient(create_app(missing_key, settings=Settings(_env_file=None)))
    assert client.post("/chat", json={"message": "hi"}).status_code == 503
    assert client.get("/health").status_code == 200


def test_unexpected_error_returns_500_without_details():
    class Broken:
        def run(self, *args, **kwargs):
            raise RuntimeError("secret internal detail")

    client = TestClient(
        create_app(lambda: Broken(), settings=Settings(_env_file=None)),
        raise_server_exceptions=False,
    )
    response = client.post("/chat", json={"message": "hi"})
    assert response.status_code == 500
    assert "secret" not in response.text


def test_index_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "CasaVaiano" in response.text


def test_escalation_emails_the_owner_and_asks_for_contact():
    notifier = FakeNotifier()
    client = make_client(notifier)
    body = client.post(
        "/chat", json={"message": "La camera era sporca!", "session_id": "s-1"}
    ).json()
    assert body["owner_notified"] and body["needs_contact"]
    mail = notifier.sent[0]
    assert "HIGH" in mail["subject"]
    assert "La camera era sporca!" in mail["body"]
    assert "DRAFT REPLY" in mail["body"] and "s-1" in mail["body"]
    assert "Not given yet" in mail["body"]
    assert mail["reply_to"] is None


def test_escalation_with_contact_sets_reply_to():
    notifier = FakeNotifier()
    client = make_client(notifier)
    contact = {"name": "Anna", "email": "anna@example.com"}
    body = client.post(
        "/chat", json={"message": "La camera era sporca!", "contact": contact}
    ).json()
    assert not body["needs_contact"]
    assert notifier.sent[0]["reply_to"] == "anna@example.com"
    assert "Email: anna@example.com" in notifier.sent[0]["body"]


def test_answers_do_not_send_email():
    notifier = FakeNotifier()
    body = make_client(notifier).post("/chat", json={"message": "Accettate cani?"}).json()
    assert notifier.sent == []
    assert not body["needs_contact"]


def test_email_failure_still_answers_the_guest():
    body = (
        make_client(FakeNotifier(ok=False))
        .post("/chat", json={"message": "La camera era sporca!"})
        .json()
    )
    assert body["status"] == "escalated"
    assert not body["owner_notified"]


def test_public_mode_hides_internals():
    body = (
        make_client(expose_internals=False)
        .post("/chat", json={"message": "La camera era sporca!"})
        .json()
    )
    assert set(body) == {"status", "reply", "language", "needs_contact"}


def test_contact_endpoint():
    notifier = FakeNotifier()
    client = make_client(notifier)
    ok = client.post(
        "/contact",
        json={"session_id": "s-1", "contact": {"phone": "+39 333 000 0000"}, "note": "Sera"},
    )
    assert ok.status_code == 200
    assert "+39 333 000 0000" in notifier.sent[0]["body"]
    assert client.post("/contact", json={"session_id": "s-1", "contact": {}}).status_code == 422
    bad_email = {"session_id": "s-1", "contact": {"email": "not-an-email"}}
    assert client.post("/contact", json=bad_email).status_code == 422


def test_cors_only_for_configured_origins():
    client = make_client(allowed_origins="https://casavaiano.example")
    preflight = {
        "Origin": "https://casavaiano.example",
        "Access-Control-Request-Method": "POST",
    }
    ok = client.options("/chat", headers=preflight)
    assert ok.headers.get("access-control-allow-origin") == "https://casavaiano.example"
    other = client.options("/chat", headers=preflight | {"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_smtp_notifier_builds_and_sends_message(monkeypatch):
    from casavaiano.notify import SmtpNotifier

    sent = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            sent["server"] = (host, port)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def login(self, user, password):
            sent["login"] = (user, password)

        def send_message(self, msg):
            sent["msg"] = msg

    monkeypatch.setattr("smtplib.SMTP_SSL", FakeSMTP)
    settings = Settings(
        _env_file=None,
        smtp_host="smtps.example.com",
        smtp_user="bot@example.com",
        smtp_password="pw",
        escalation_email_to="owner@example.com",
    )
    assert settings.email_enabled
    assert SmtpNotifier(settings).send("Subject", "Body", reply_to="guest@example.com")
    assert sent["server"] == ("smtps.example.com", 465)
    assert sent["login"] == ("bot@example.com", "pw")
    assert sent["msg"]["To"] == "owner@example.com"
    assert sent["msg"]["Reply-To"] == "guest@example.com"
