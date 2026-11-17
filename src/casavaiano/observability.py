"""Thin Langfuse wrapper. Every call is a no-op when Langfuse keys are not configured."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from casavaiano.config import Settings, get_settings


class _NullObservation:
    def update(self, **_: Any) -> None:
        pass


class Tracer:
    def __init__(self, settings: Settings):
        self._client = None
        if settings.tracing_enabled:
            from langfuse import Langfuse

            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key.get_secret_value(),
                base_url=settings.langfuse_host,
            )

    @property
    def enabled(self) -> bool:
        return self._client is not None

    @contextmanager
    def trace(
        self,
        name: str,
        input: Any = None,
        session_id: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[Any]:
        """Root observation of one assistant run. Attributes propagate to every child span."""
        if not self.enabled:
            yield _NullObservation()
            return
        from langfuse import propagate_attributes

        string_metadata = {k: str(v) for k, v in (metadata or {}).items()}
        with (
            self._client.start_as_current_observation(
                name=name, as_type="agent", input=input
            ) as root,
            propagate_attributes(
                trace_name=name, session_id=session_id, tags=tags, metadata=string_metadata
            ),
        ):
            yield root

    @contextmanager
    def span(self, name: str, as_type: str = "span", **attributes: Any) -> Iterator[Any]:
        if not self.enabled:
            yield _NullObservation()
            return
        with self._client.start_as_current_observation(
            name=name, as_type=as_type, **attributes
        ) as observation:
            yield observation

    def current_trace_id(self) -> str | None:
        return self._client.get_current_trace_id() if self.enabled else None

    def trace_url(self, trace_id: str | None) -> str | None:
        if not (self.enabled and trace_id):
            return None
        return self._client.get_trace_url(trace_id=trace_id)

    def flush(self) -> None:
        if self.enabled:
            self._client.flush()


@lru_cache
def get_tracer() -> Tracer:
    return Tracer(get_settings())
