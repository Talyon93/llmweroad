from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "data"
KB_DIR = DATA_DIR / "kb"
STRUCTURED_DIR = DATA_DIR / "structured"
EVALS_DIR = ROOT_DIR / "evals"
INDEX_DIR = ROOT_DIR / ".chroma"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    anthropic_api_key: SecretStr | None = None

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    cheap_model: str = "claude-haiku-5-5"
    strong_model: str = "claude-opus-5-5"
    routing_enabled: bool = True
    chunking_strategy: Literal["headings", "fixed"] = "headings"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    retrieval_k: int = 4
    retrieval_query: Literal["original", "rewritten", "both"] = "both"
    max_tool_iterations: int = 4
    judge_model: str = "claude-opus-5-5"
    assistant_name: str = "Rocco"
    # Fictional owner of the demo knowledge base. For the real site set OWNER_NAME to the
    # person who handles requests, or to an empty string to refer to "the family".
    owner_name: str = "Giulia"
    # demo: fictional rooms and prices (evals, portfolio). slope: the real apartments, availability
    # from the CASA_ICAL_* calendars, no prices (they are dynamic, see booking_url).
    availability_source: Literal["demo", "slope"] = "demo"
    booking_url: str = ""
    # Knowledge base folder. Empty = the fictional demo KB (data/kb), refused in slope mode.
    kb_dir: str = ""

    @property
    def knowledge_base_dir(self) -> Path:
        if not self.kb_dir:
            return KB_DIR
        path = Path(self.kb_dir)
        return path if path.is_absolute() else ROOT_DIR / path

    # Public mode: /chat returns only the reply and status; internals go to the owner by email.
    expose_internals: bool = True
    allowed_origins: str = ""

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: SecretStr | None = None
    email_from: str = ""
    escalation_email_to: str = ""

    # Abuse protection. On Cloud Run set TRUST_FORWARDED_FOR=true (requests arrive from Google's
    # front end; the client IP is in X-Forwarded-For). DAILY_BUDGET_USD=0 disables the cap.
    rate_limit_per_10min: int = 20
    rate_limit_per_day: int = 150
    contact_limit_per_hour: int = 5
    daily_budget_usd: float = 1.0
    trust_forwarded_for: bool = False

    @property
    def email_enabled(self) -> bool:
        return bool(
            self.smtp_host and self.smtp_user and self.smtp_password and self.escalation_email_to
        )

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
