# CasaVaiano guest-inquiry assistant

A LangGraph agent that answers guest emails and chat messages (IT / EN / DE) for a family
agriturismo in Gambassi Terme, Tuscany. It classifies intent, answers from a knowledge base
(RAG), calls tools for availability and quotes, and escalates to a human when it should.

> Work in progress. Architecture, eval results and cost analysis will be documented here.

## Development

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Retrieval:

```bash
uv run python scripts/build_index.py        # build/refresh the Chroma index (both strategies)
uv run python scripts/compare_chunking.py   # retrieval metrics for headings vs fixed chunking
```

The first run downloads the embedding model (~220 MB) into `.cache/`.

Ask the assistant (needs `.env`):

```bash
uv run python scripts/ask.py --today 2026-11-17 "Accettate cani?"
```

Copy `.env.example` to `.env` and fill in the keys you need. `.env` is git-ignored.
Tests marked `live` call real APIs and are skipped by default (`uv run pytest -m live` to run them).
