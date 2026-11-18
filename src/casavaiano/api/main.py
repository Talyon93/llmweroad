import logging
import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from casavaiano.agent.graph import Assistant
from casavaiano.agent.state import CallRecord, EscalationDraft, ToolRecord
from casavaiano.config import Settings, get_settings
from casavaiano.llm import LLMError
from casavaiano.notify import Contact, Notifier, contact_email, escalation_email, make_notifier
from casavaiano.observability import get_tracer

STATIC_DIR = Path(__file__).parent / "static"
MAX_MESSAGE_CHARS = 4000

log = logging.getLogger("casavaiano.api")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    session_id: str | None = Field(default=None, max_length=100)
    contact: Contact | None = None


class PublicChatResponse(BaseModel):
    """What a guest's browser receives in production."""

    status: str
    reply: str
    language: str
    needs_contact: bool


class ChatResponse(PublicChatResponse):
    """Demo mode adds everything the agent did."""

    intent: str
    escalation_reason: str | None
    escalation: EscalationDraft | None
    tools: list[ToolRecord]
    calls: list[CallRecord]
    sources: list[str]
    cost_usd: float
    latency_ms: float
    trace_url: str | None
    owner_notified: bool


class ContactRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    contact: Contact
    note: str | None = Field(default=None, max_length=1000)


def _default_assistant() -> Assistant:
    from casavaiano.llm.anthropic_client import default_client

    return Assistant(default_client())


def create_app(
    assistant_factory: Callable[[], Assistant] = _default_assistant,
    settings: Settings | None = None,
    notifier: Notifier | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    notifier = notifier or make_notifier(settings)
    app = FastAPI(title="CasaVaiano guest assistant", version="0.2.0")
    origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]
    if origins:
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["POST"], allow_headers=["*"]
        )
    state: dict[str, Assistant] = {}
    lock = threading.Lock()

    def assistant() -> Assistant:
        with lock:
            if "assistant" not in state:
                state["assistant"] = assistant_factory()
            return state["assistant"]

    @app.get("/health")
    def health() -> dict:
        return {
            "status": "ok",
            "routing": settings.routing_enabled,
            "cheap_model": settings.cheap_model,
            "strong_model": settings.strong_model,
            "tracing": get_tracer().enabled,
            "email": settings.email_enabled,
            "assistant_name": settings.assistant_name,
            "owner_name": settings.owner_name or None,
        }

    @app.post("/chat", response_model=None)
    def chat(request: ChatRequest) -> dict:
        try:
            agent = assistant()
        except LLMError as exc:
            raise HTTPException(503, "The assistant is not configured") from exc
        message = request.message.strip()
        try:
            result = agent.run(message, session_id=request.session_id)
        except Exception as exc:
            log.exception("assistant run failed")
            raise HTTPException(500, "Something went wrong, please try again") from exc

        trace_url = get_tracer().trace_url(result.trace_id)
        escalated = result.status == "escalated"
        notified = False
        if escalated:
            subject, body = escalation_email(
                message, result, request.session_id, request.contact, trace_url
            )
            reply_to = request.contact.email if request.contact else None
            notified = notifier.send(subject, body, reply_to=reply_to)
        public = PublicChatResponse(
            status=result.status,
            reply=result.reply,
            language=result.language,
            needs_contact=escalated and (request.contact is None or request.contact.empty),
        )
        if not settings.expose_internals:
            return public.model_dump(mode="json")
        return ChatResponse(
            **public.model_dump(),
            **result.model_dump(
                include={
                    "intent",
                    "escalation_reason",
                    "escalation",
                    "tools",
                    "calls",
                    "sources",
                    "cost_usd",
                    "latency_ms",
                }
            ),
            trace_url=trace_url,
            owner_notified=notified,
        ).model_dump(mode="json")

    @app.post("/contact")
    def contact(request: ContactRequest) -> dict:
        if request.contact.empty:
            raise HTTPException(422, "An email or a phone number is required")
        subject, body = contact_email(request.session_id, request.contact, request.note)
        sent = notifier.send(subject, body, reply_to=request.contact.email)
        return {"received": True, "owner_notified": sent}

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
