# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

FROM base AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /bin/uv
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY data ./data
COPY scripts/build_index.py ./scripts/
RUN uv sync --frozen --no-dev
# Bake the embedding model and the vector indexes (demo KB and real KB) into the image: no
# download and no indexing at startup.
RUN .venv/bin/python scripts/build_index.py \
    && KB_DIR=data/real/kb .venv/bin/python scripts/build_index.py

FROM base AS runtime
RUN useradd --create-home --uid 10001 app
COPY --from=build --chown=app:app /app /app
USER app
ENV PATH="/app/.venv/bin:$PATH" \
    PORT=8080
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health')"
CMD ["sh", "-c", "uvicorn casavaiano.api.main:app --host 0.0.0.0 --port ${PORT}"]
