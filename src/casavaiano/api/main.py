import logging
import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from casavaiano.agent.graph import Assistant
from casavaiano.agent.state import CallRecord, EscalationDraft, ToolRecord
from casavaiano.config import get_settings
from casavaiano.llm import LLMError
from casavaiano.observability import get_tracer

STATIC_DIR = Path(__file__).parent / "static"
MAX_MESSAGE_CHARS = 4000

log = logging.getLogger("casavaiano.api")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    session_id: str | None = Field(default=None, max_length=100)


class ChatResponse(BaseModel):
    status: str
    reply: str
    intent: str
    language: str
    escalation_reason: str | None
    escalation: EscalationDraft | None
    tools: list[ToolRecord]
    calls: list[CallRecord]
    sources: list[str]
    cost_usd: float
    latency_ms: float
    trace_url: str | None


def _default_assistant() -> Assistant:
    from casavaiano.llm.anthropic_client import default_client

    return Assistant(default_client())


def create_app(assistant_factory: Callable[[], Assistant] = _default_assistant) -> FastAPI:
    app = FastAPI(title="CasaVaiano guest assistant", version="0.1.0")
    state: dict[str, Assistant] = {}
    lock = threading.Lock()

    def assistant() -> Assistant:
        with lock:
            if "assistant" not in state:
                state["assistant"] = assistant_factory()
            return state["assistant"]

    @app.get("/health")
    def health() -> dict:
        settings = get_settings()
        return {
            "status": "ok",
            "routing": settings.routing_enabled,
            "cheap_model": settings.cheap_model,
            "strong_model": settings.strong_model,
            "tracing": get_tracer().enabled,
            "assistant_name": settings.assistant_name,
            "owner_name": settings.owner_name or None,
        }

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        try:
            agent = assistant()
        except LLMError as exc:
            raise HTTPException(503, "The assistant is not configured") from exc
        try:
            result = agent.run(request.message.strip(), session_id=request.session_id)
        except Exception as exc:
            log.exception("assistant run failed")
            raise HTTPException(500, "Something went wrong, please try again") from exc
        return ChatResponse(
            **result.model_dump(
                include={
                    "status",
                    "reply",
                    "intent",
                    "language",
                    "escalation_reason",
                    "escalation",
                    "tools",
                    "calls",
                    "sources",
                    "cost_usd",
                    "latency_ms",
                }
            ),
            trace_url=get_tracer().trace_url(result.trace_id),
        )

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
