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

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
