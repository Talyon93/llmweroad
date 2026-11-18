"""Escalation emails to the owner over plain SMTP (works with Aruba, Gmail app passwords, etc.)."""

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Protocol

from pydantic import BaseModel, EmailStr, Field

from casavaiano.agent.state import AssistantResponse
from casavaiano.config import Settings

log = logging.getLogger("casavaiano.notify")


class Contact(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)

    @property
    def empty(self) -> bool:
        return not (self.email or self.phone)

    def lines(self) -> list[str]:
        return [
            f"{label}: {value}"
            for label, value in (("Name", self.name), ("Email", self.email), ("Phone", self.phone))
            if value
        ]


class Notifier(Protocol):
    def send(self, subject: str, body: str, reply_to: str | None = None) -> bool: ...


class NullNotifier:
    """Used when SMTP is not configured: escalations stay in the logs and traces."""

    def send(self, subject: str, body: str, reply_to: str | None = None) -> bool:
        log.warning("email not configured, escalation not sent: %s", subject)
        return False


class SmtpNotifier:
    def __init__(self, settings: Settings):
        self.settings = settings

    def send(self, subject: str, body: str, reply_to: str | None = None) -> bool:
        s = self.settings
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = s.email_from or s.smtp_user
        msg["To"] = s.escalation_email_to
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body)
        try:
            if s.smtp_port == 465:
                server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15)
                server.starttls()
            with server:
                server.login(s.smtp_user, s.smtp_password.get_secret_value())
                server.send_message(msg)
            return True
        except (smtplib.SMTPException, OSError):
            log.exception("escalation email failed: %s", subject)
            return False


def make_notifier(settings: Settings) -> Notifier:
    if settings.email_enabled:
        return SmtpNotifier(settings)
    return NullNotifier()


def escalation_email(
    message: str,
    response: AssistantResponse,
    session_id: str | None,
    contact: Contact | None,
    trace_url: str | None,
) -> tuple[str, str]:
    e = response.escalation
    priority = e.priority.upper() if e else "HIGH"
    subject = f"[CasaVaiano · Rocco] {priority} · {response.intent} · guest message to handle"
    contact_lines = contact.lines() if contact and not contact.empty else []
    body = "\n".join(
        [
            f"Priority: {priority}",
            f"Why: {response.escalation_reason}",
            f"Guest language: {response.language}",
            f"Received: {datetime.now():%Y-%m-%d %H:%M}",
            f"Conversation: {session_id or '-'}",
            "",
            "GUEST CONTACT",
            *(contact_lines or ["Not given yet. The guest was asked to leave an email or phone."]),
            "",
            "SUMMARY",
            e.owner_summary if e else "(automatic summary not available)",
            "",
            "GUEST MESSAGE",
            message,
            "",
            "DRAFT REPLY (edit before sending)",
            e.draft_reply if e and e.draft_reply else "(none)",
            "",
            "TO CHECK",
            *([f"- {item}" for item in e.missing_info] if e and e.missing_info else ["-"]),
            "",
            f"Trace: {trace_url or '-'}",
        ]
    )
    return subject, body


def contact_email(session_id: str, contact: Contact, note: str | None) -> tuple[str, str]:
    subject = f"[CasaVaiano · Rocco] Guest contact for conversation {session_id[:8]}"
    body = "\n".join(
        [
            "The guest left their contact details for a request Rocco passed to you.",
            f"Conversation: {session_id}",
            "",
            *contact.lines(),
            *(["", "Note from the guest:", note] if note else []),
        ]
    )
    return subject, body
