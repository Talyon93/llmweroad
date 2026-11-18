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

    # Public mode: /chat returns only the reply and status; internals go to the owner by email.
    expose_internals: bool = True
    allowed_origins: str = ""

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: SecretStr | None = None
    email_from: str = ""
    escalation_email_to: str = ""

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
