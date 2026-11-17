from casavaiano.config import DATA_DIR, ROOT_DIR, Settings


def test_defaults_without_env(monkeypatch):
    for key in ("ANTHROPIC_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.cheap_model == "claude-haiku-5-5"
    assert settings.strong_model == "claude-opus-5-5"
    assert settings.routing_enabled
    assert not settings.tracing_enabled


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("ROUTING_ENABLED", "false")
    monkeypatch.setenv("CHUNKING_STRATEGY", "fixed")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    settings = Settings(_env_file=None)
    assert not settings.routing_enabled
    assert settings.chunking_strategy == "fixed"
    assert settings.tracing_enabled


def test_paths():
    assert (ROOT_DIR / "pyproject.toml").exists()
    assert DATA_DIR.parent == ROOT_DIR
