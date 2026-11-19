from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from casavaiano.agent.graph import Assistant
from casavaiano.agent.state import Classification
from casavaiano.api.limits import DailyBudget, RateLimiter, client_ip
from casavaiano.api.main import create_app
from casavaiano.config import Settings
from casavaiano.llm.fake import FakeLLM
from casavaiano.observability import Tracer
from casavaiano.rag.retriever import RetrievedChunk


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_rate_limiter_sliding_windows():
    clock = Clock()
    limiter = RateLimiter([(3, 10), (5, 100)], clock=clock)
    assert [limiter.hit("ip") for _ in range(3)] == [None, None, None]
    wait = limiter.hit("ip")
    assert wait is not None and 1 <= wait <= 11
    assert limiter.hit("other") is None
    clock.now += 11
    assert limiter.hit("ip") is None
    assert limiter.hit("ip") is None
    assert limiter.hit("ip") is not None  # 5 per 100 s reached


def test_daily_budget_resets_each_day():
    day = {"d": date(2027, 5, 1)}
    budget = DailyBudget(1.0, today=lambda: day["d"])
    budget.add(0.6)
    assert not budget.exceeded()
    budget.add(0.5)
    assert budget.exceeded()
    day["d"] = date(2027, 5, 2)
    assert not budget.exceeded() and budget.spent == 0
    unlimited = DailyBudget(0)
    unlimited.add(1000)
    assert not unlimited.exceeded()


def request_with(host, forwarded=None):
    headers = {"x-forwarded-for": forwarded} if forwarded else {}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_client_ip_uses_last_forwarded_entry_only_when_trusted():
    proxied = request_with("169.254.1.1", "6.6.6.6, 1.2.3.4")
    assert client_ip(proxied, trust_forwarded_for=True) == "1.2.3.4"
    assert client_ip(proxied, trust_forwarded_for=False) == "169.254.1.1"
    assert client_ip(request_with("10.0.0.1"), trust_forwarded_for=True) == "10.0.0.1"


class StubRetriever:
    def search(self, query, k=None):
        return [RetrievedChunk("p:1", "Dogs: €15 per night.", "policies", ("Pets",), 0.9)]


class QuietNotifier:
    def send(self, *args, **kwargs):
        return True


def client_with(**overrides):
    settings = Settings(
        _env_file=None, langfuse_public_key=None, langfuse_secret_key=None, **overrides
    )

    def handler(r):
        if r.name == "classify":
            return Classification(
                intent="pets",
                secondary_intents=[],
                language="it",
                confidence=0.9,
                risk_flags=[],
                group_size=None,
                search_query="dogs",
            )
        return "Sì, €15 a notte."

    assistant = Assistant(FakeLLM(handler), StubRetriever(), settings, Tracer(settings))
    app = create_app(lambda: assistant, settings=settings, notifier=QuietNotifier())
    return TestClient(app)


def test_chat_is_rate_limited_per_ip():
    client = client_with(rate_limit_per_10min=2, trust_forwarded_for=True)
    first = {"x-forwarded-for": "1.1.1.1"}
    assert client.post("/chat", json={"message": "a"}, headers=first).status_code == 200
    assert client.post("/chat", json={"message": "b"}, headers=first).status_code == 200
    blocked = client.post("/chat", json={"message": "c"}, headers=first)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    other = {"x-forwarded-for": "2.2.2.2"}
    assert client.post("/chat", json={"message": "d"}, headers=other).status_code == 200


def test_daily_budget_pauses_chat_but_not_contact():
    client = client_with(daily_budget_usd=0.0000001)
    assert client.post("/chat", json={"message": "a"}).status_code == 200
    paused = client.post("/chat", json={"message": "b"})
    assert paused.status_code == 503
    contact = {"session_id": "s", "contact": {"phone": "+39 333 0000000"}}
    assert client.post("/contact", json=contact).status_code == 200


def test_contact_is_rate_limited():
    client = client_with(contact_limit_per_hour=1)
    contact = {"session_id": "s", "contact": {"phone": "+39 333 0000000"}}
    assert client.post("/contact", json=contact).status_code == 200
    assert client.post("/contact", json=contact).status_code == 429
